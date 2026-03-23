#!/usr/bin/env python3
"""
OSS Health Check — Evaluate open source project health against configurable health policy.

Queries GitHub API and package registries (npm, PyPI, crates.io) to collect
quantitative signals, then scores them Green/Yellow/Red per the thresholds
defined in code/oss-health-policy.md.

Usage:
    python health_check.py --repo pallets/flask --ecosystem pypi
    python health_check.py --repo expressjs/express --ecosystem npm
    python health_check.py --repo serde-rs/serde --ecosystem crates
    python health_check.py --repo some-org/some-repo  # auto-detect ecosystem
"""

import argparse
import json
import sys
import os
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote


# ---------------------------------------------------------------------------
# Thresholds — keep in sync with code/oss-health-policy.md
# ---------------------------------------------------------------------------

THRESHOLDS = {
    "maintenance": {
        "last_commit_days": {"green": 90, "yellow": 180},       # <90 green, 90-180 yellow, >180 red  (policy: 3mo/6mo/12mo, using conservative days)
        "last_release_days": {"green": 180, "yellow": 365},     # <6mo green, 6-12mo yellow, >12mo red
        "median_issue_response_days": {"green": 7, "yellow": 30},
        "pr_staleness_days": {"green": 14, "yellow": 30},
    },
    "bus_factor": {
        "contributors_with_merge": {"green": 3, "yellow": 2},   # >=3 green, 2 yellow, 1 red
        "top_contributor_pct": {"green": 70, "yellow": 90},      # <70 green, 70-90 yellow, >90 red
    },
    "community": {
        "stars": {"green": 1000, "yellow": 100},
        "weekly_downloads": {"green": 10000, "yellow": 1000},
        "dependent_packages": {"green": 100, "yellow": 10},
    },
    "security": {
        # Booleans — presence/absence
    },
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url, token=None, accept="application/vnd.github+json"):
    headers = {"Accept": accept, "User-Agent": "oss-health-check/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode()), dict(resp.headers)
    except HTTPError as e:
        if e.code == 404:
            return None, {}
        if e.code == 403:
            return {"error": "rate_limited"}, {}
        raise
    except (URLError, TimeoutError):
        return {"error": "network_error"}, {}


def _get_json(url, token=None):
    data, _ = _get(url, token)
    return data


# ---------------------------------------------------------------------------
# GitHub data collection
# ---------------------------------------------------------------------------

def get_repo_info(owner, repo, token=None):
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}"
    return _get_json(url, token)


def get_recent_commits(owner, repo, token=None, per_page=100):
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/commits?per_page={per_page}"
    return _get_json(url, token) or []


def get_releases(owner, repo, token=None, per_page=10):
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/releases?per_page={per_page}"
    return _get_json(url, token) or []


def get_contributors(owner, repo, token=None, per_page=30):
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/contributors?per_page={per_page}"
    return _get_json(url, token) or []


def get_open_issues_sample(owner, repo, token=None, per_page=30):
    """Get recent issues (not PRs) to estimate response times."""
    url = (
        f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/issues"
        f"?state=all&per_page={per_page}&sort=created&direction=desc"
    )
    items = _get_json(url, token) or []
    # Filter out pull requests (issues API includes PRs)
    return [i for i in items if "pull_request" not in i]


def get_open_prs(owner, repo, token=None, per_page=30):
    url = (
        f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/pulls"
        f"?state=open&per_page={per_page}&sort=created&direction=desc"
    )
    return _get_json(url, token) or []


def check_file_exists(owner, repo, path, token=None):
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/contents/{quote(path)}"
    data = _get_json(url, token)
    return data is not None and not isinstance(data, dict) or (isinstance(data, dict) and "error" not in data)


def get_community_profile(owner, repo, token=None):
    url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/community/profile"
    return _get_json(url, token)


def get_dependabot_status(owner, repo, token=None):
    """Check for .github/dependabot.yml or similar CI security scanning."""
    for path in ["dependabot.yml", ".github/dependabot.yml", ".github/dependabot.yaml"]:
        url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/contents/{quote(path)}"
        data = _get_json(url, token)
        if data and isinstance(data, dict) and "error" not in data:
            return True
    return False


# ---------------------------------------------------------------------------
# Package registry data collection
# ---------------------------------------------------------------------------

def get_npm_stats(package_name):
    """Get npm weekly downloads and dependent count."""
    dl_url = f"https://api.npmjs.org/downloads/point/last-week/{quote(package_name)}"
    dl_data = _get_json(dl_url)
    weekly_downloads = dl_data.get("downloads", 0) if dl_data else 0

    # Dependent packages count from npm search
    pkg_url = f"https://registry.npmjs.org/{quote(package_name)}"
    pkg_data = _get_json(pkg_url)
    dependents = 0  # npm doesn't expose this directly via API easily

    return {"weekly_downloads": weekly_downloads, "dependent_packages": dependents, "ecosystem": "npm"}


def get_pypi_stats(package_name):
    """Get PyPI download stats. Uses pypistats.org API for recent downloads."""
    # PyPI JSON API for package metadata
    pkg_url = f"https://pypi.org/pypi/{quote(package_name)}/json"
    pkg_data = _get_json(pkg_url)
    if not pkg_data:
        return {"weekly_downloads": 0, "dependent_packages": 0, "ecosystem": "pypi"}

    # pypistats.org for download counts (last month, divide by ~4 for weekly)
    stats_url = f"https://pypistats.org/api/packages/{quote(package_name)}/recent"
    stats_data = _get_json(stats_url)
    monthly_downloads = 0
    if stats_data and "data" in stats_data:
        monthly_downloads = stats_data["data"].get("last_month", 0)
    weekly_downloads = monthly_downloads // 4

    return {"weekly_downloads": weekly_downloads, "dependent_packages": 0, "ecosystem": "pypi"}


def get_crates_stats(package_name):
    """Get crates.io download stats."""
    url = f"https://crates.io/api/v1/crates/{quote(package_name)}"
    headers = {"User-Agent": "oss-health-check/1.0 (open-workspace-builder)"}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (HTTPError, URLError, TimeoutError):
        return {"weekly_downloads": 0, "dependent_packages": 0, "ecosystem": "crates"}

    crate = data.get("crate", {})
    recent_downloads = crate.get("recent_downloads", 0)  # last 90 days
    weekly_downloads = recent_downloads // 13  # ~13 weeks in 90 days

    return {"weekly_downloads": weekly_downloads, "dependent_packages": 0, "ecosystem": "crates"}


def get_package_stats(ecosystem, package_name):
    if ecosystem == "npm":
        return get_npm_stats(package_name)
    elif ecosystem == "pypi":
        return get_pypi_stats(package_name)
    elif ecosystem == "crates":
        return get_crates_stats(package_name)
    return {"weekly_downloads": 0, "dependent_packages": 0, "ecosystem": ecosystem or "unknown"}


# ---------------------------------------------------------------------------
# Ecosystem auto-detection
# ---------------------------------------------------------------------------

def detect_ecosystem(owner, repo, token=None):
    """Guess ecosystem from repo contents."""
    checks = [
        ("package.json", "npm"),
        ("setup.py", "pypi"),
        ("pyproject.toml", "pypi"),
        ("setup.cfg", "pypi"),
        ("Cargo.toml", "crates"),
    ]
    for filename, eco in checks:
        url = f"https://api.github.com/repos/{quote(owner)}/{quote(repo)}/contents/{quote(filename)}"
        data = _get_json(url, token)
        if data and isinstance(data, dict) and "error" not in data:
            return eco
    return None


# ---------------------------------------------------------------------------
# Rating logic
# ---------------------------------------------------------------------------

def rate(value, green_threshold, yellow_threshold, lower_is_better=True):
    """
    Rate a numeric value as green/yellow/red.
    lower_is_better=True: value < green → green, < yellow → yellow, else red
    lower_is_better=False: value >= green → green, >= yellow → yellow, else red
    """
    if lower_is_better:
        if value <= green_threshold:
            return "GREEN"
        elif value <= yellow_threshold:
            return "YELLOW"
        return "RED"
    else:
        if value >= green_threshold:
            return "GREEN"
        elif value >= yellow_threshold:
            return "YELLOW"
        return "RED"


def days_since(iso_date_str):
    if not iso_date_str:
        return 9999
    try:
        dt = datetime.fromisoformat(iso_date_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except (ValueError, TypeError):
        return 9999


def compute_median_issue_response(issues):
    """Compute median first-response time in days from a sample of issues."""
    response_times = []
    for issue in issues:
        created = issue.get("created_at")
        comments = issue.get("comments", 0)
        if comments > 0 and created:
            # We don't have the first comment timestamp from the list endpoint,
            # so use updated_at as a rough proxy for first activity
            updated = issue.get("updated_at")
            if updated and updated != created:
                days = days_since(created) - days_since(updated)
                if days >= 0:
                    response_times.append(abs(days))
    if not response_times:
        return None
    response_times.sort()
    mid = len(response_times) // 2
    return response_times[mid]


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate(owner, repo, ecosystem=None, package_name=None, token=None):
    now = datetime.now(timezone.utc)
    report = {
        "project": f"{owner}/{repo}",
        "github_url": f"https://github.com/{owner}/{repo}",
        "evaluated_at": now.isoformat(),
        "categories": {},
        "overall_rating": "GREEN",
        "recommendation": "",
        "human_review_needed": [],
    }

    errors = []

    # ---- Repo info ----
    repo_info = get_repo_info(owner, repo, token)
    if not repo_info or "error" in (repo_info if isinstance(repo_info, dict) else {}):
        return {"error": f"Could not fetch repository {owner}/{repo}. Check the name and try again."}

    stars = repo_info.get("stargazers_count", 0)
    open_issues_count = repo_info.get("open_issues_count", 0)  # includes PRs
    has_wiki = repo_info.get("has_wiki", False)
    license_info = repo_info.get("license", {})
    archived = repo_info.get("archived", False)
    default_branch = repo_info.get("default_branch", "main")

    if archived:
        report["overall_rating"] = "RED"
        report["recommendation"] = "Repository is archived. Do not adopt."
        report["categories"]["maintenance"] = {
            "rating": "RED",
            "signals": {"archived": True},
            "note": "Repository is archived — no further development expected."
        }
        return report

    # ---- Maintenance Activity ----
    commits = get_recent_commits(owner, repo, token, per_page=50)
    last_commit_date = commits[0]["commit"]["committer"]["date"] if commits else None
    last_commit_days = days_since(last_commit_date)

    releases = get_releases(owner, repo, token, per_page=5)
    last_release_date = releases[0].get("published_at") if releases else None
    last_release_days = days_since(last_release_date) if last_release_date else 9999

    issues_sample = get_open_issues_sample(owner, repo, token, per_page=30)
    median_response = compute_median_issue_response(issues_sample)

    open_prs = get_open_prs(owner, repo, token, per_page=30)
    # Use median PR age instead of oldest — one stale PR shouldn't tank the rating
    pr_ages = []
    if open_prs:
        for pr in open_prs:
            pr_date = pr.get("created_at")
            if pr_date:
                pr_ages.append(days_since(pr_date))
    if pr_ages:
        pr_ages.sort()
        median_pr_age = pr_ages[len(pr_ages) // 2]
    else:
        median_pr_age = 0

    maint_signals = {
        "last_commit_days": last_commit_days,
        "last_commit_date": last_commit_date,
        "last_release_days": last_release_days if last_release_date else "no_releases",
        "last_release_date": last_release_date,
        "median_issue_response_days": median_response,
        "median_open_pr_age_days": median_pr_age,
        "open_pr_count": len(open_prs),
        "open_issues_count": open_issues_count,
    }

    maint_ratings = {
        "last_commit": rate(last_commit_days, 90, 180, lower_is_better=True),
    }
    if last_release_date:
        maint_ratings["release_cadence"] = rate(last_release_days, 180, 365, lower_is_better=True)
    if median_response is not None:
        maint_ratings["issue_response"] = rate(median_response, 7, 30, lower_is_better=True)
    if pr_ages:
        # Low open PR count is itself a positive signal — the project keeps things clean.
        # Don't penalize a project with 3 stale community PRs the same as one with 30.
        if len(pr_ages) <= 5:
            # With few open PRs, cap at YELLOW regardless of age
            raw = rate(median_pr_age, 14, 30, lower_is_better=True)
            maint_ratings["pr_staleness"] = "YELLOW" if raw == "RED" else raw
        else:
            maint_ratings["pr_staleness"] = rate(median_pr_age, 14, 30, lower_is_better=True)

    # Overall maintenance rating: worst of sub-ratings
    maint_values = list(maint_ratings.values())
    if "RED" in maint_values:
        maint_overall = "RED"
    elif "YELLOW" in maint_values:
        maint_overall = "YELLOW"
    else:
        maint_overall = "GREEN"

    report["categories"]["maintenance"] = {
        "rating": maint_overall,
        "signals": maint_signals,
        "sub_ratings": maint_ratings,
    }

    # ---- Bus Factor / Contributor Health ----
    contributors = get_contributors(owner, repo, token, per_page=30)
    if isinstance(contributors, list) and len(contributors) > 0:
        total_contributions = sum(c.get("contributions", 0) for c in contributors)
        top_contributor_pct = (contributors[0].get("contributions", 0) / max(total_contributions, 1)) * 100
        num_significant = sum(1 for c in contributors if c.get("contributions", 0) >= total_contributions * 0.05)
    else:
        top_contributor_pct = 100
        num_significant = 1

    # GitHub doesn't expose "merge access" via public API, so we use
    # contributors with >= 5% of total commits as a proxy
    bus_signals = {
        "total_contributors": len(contributors) if isinstance(contributors, list) else 0,
        "significant_contributors": num_significant,
        "top_contributor_pct": round(top_contributor_pct, 1),
    }

    bus_ratings = {
        "contributor_count": rate(num_significant, 3, 2, lower_is_better=False),
        "concentration": rate(top_contributor_pct, 70, 90, lower_is_better=True),
    }

    bus_values = list(bus_ratings.values())
    if "RED" in bus_values:
        bus_overall = "RED"
    elif "YELLOW" in bus_values:
        bus_overall = "YELLOW"
    else:
        bus_overall = "GREEN"

    report["categories"]["bus_factor"] = {
        "rating": bus_overall,
        "signals": bus_signals,
        "sub_ratings": bus_ratings,
    }

    # ---- Community & Adoption ----
    if not ecosystem:
        ecosystem = detect_ecosystem(owner, repo, token)
    if not package_name:
        package_name = repo  # default guess

    pkg_stats = {"weekly_downloads": 0, "dependent_packages": 0, "ecosystem": "unknown"}
    if ecosystem:
        pkg_stats = get_package_stats(ecosystem, package_name)

    community_signals = {
        "stars": stars,
        "weekly_downloads": pkg_stats.get("weekly_downloads", 0),
        "dependent_packages": pkg_stats.get("dependent_packages", 0),
        "ecosystem": pkg_stats.get("ecosystem", ecosystem or "unknown"),
        "package_name": package_name,
    }

    community_ratings = {
        "stars": rate(stars, 1000, 100, lower_is_better=False),
    }
    if pkg_stats.get("weekly_downloads", 0) > 0:
        community_ratings["weekly_downloads"] = rate(
            pkg_stats["weekly_downloads"], 10000, 1000, lower_is_better=False
        )

    comm_values = list(community_ratings.values())
    if "RED" in comm_values:
        comm_overall = "RED"
    elif "YELLOW" in comm_values:
        comm_overall = "YELLOW"
    else:
        comm_overall = "GREEN"

    report["categories"]["community"] = {
        "rating": comm_overall,
        "signals": community_signals,
        "sub_ratings": community_ratings,
    }

    # ---- Funding ----
    # GitHub API doesn't expose funding model directly. Check for FUNDING.yml
    funding_file = check_file_exists(owner, repo, ".github/FUNDING.yml", token)
    has_sponsors = repo_info.get("has_sponsorships", False) if isinstance(repo_info, dict) else False

    # Check if org-owned vs user-owned
    owner_type = repo_info.get("owner", {}).get("type", "User")
    is_org = owner_type == "Organization"

    funding_signals = {
        "funding_file_present": funding_file,
        "owner_type": owner_type,
        "is_organization": is_org,
    }

    # Rough heuristic: org-backed + funding file = green; funding file only = yellow; neither = red
    if is_org and funding_file:
        funding_overall = "GREEN"
    elif funding_file or is_org:
        funding_overall = "YELLOW"
    else:
        funding_overall = "RED"

    report["categories"]["funding"] = {
        "rating": funding_overall,
        "signals": funding_signals,
        "note": "Funding assessment is approximate. Human review recommended for accuracy.",
    }
    report["human_review_needed"].append("Funding model: verify corporate sponsorship or foundation backing manually.")

    # ---- Documentation & API Stability ----
    # We can check for presence of key files but not quality
    community_profile = get_community_profile(owner, repo, token) or {}
    files = community_profile.get("files", {})

    has_readme = files.get("readme") is not None if files else True  # almost all repos have one
    has_contributing = files.get("contributing") is not None if files else False
    has_changelog = any(
        check_file_exists(owner, repo, f, token)
        for f in ["CHANGELOG.md", "CHANGES.md", "CHANGES.rst", "CHANGELOG.rst", "CHANGELOG",
                  "HISTORY.md", "HISTORY.rst", "History.md", "Changes.md", "Changelog.md"]
    )
    has_code_of_conduct = files.get("code_of_conduct") is not None if files else False

    doc_signals = {
        "has_readme": has_readme,
        "has_contributing": has_contributing,
        "has_changelog": has_changelog,
        "has_code_of_conduct": has_code_of_conduct,
        "description": repo_info.get("description", ""),
        "homepage": repo_info.get("homepage", ""),
    }

    doc_score = sum([has_readme, has_contributing, has_changelog, bool(repo_info.get("homepage"))])
    if doc_score >= 3:
        doc_overall = "GREEN"
    elif doc_score >= 2:
        doc_overall = "YELLOW"
    else:
        doc_overall = "RED"

    report["categories"]["documentation"] = {
        "rating": doc_overall,
        "signals": doc_signals,
        "note": "Documentation quality and semver discipline require human review.",
    }
    report["human_review_needed"].extend([
        "Documentation quality: verify docs are comprehensive and current.",
        "Semver discipline: check changelog for breaking changes without major bumps.",
        "Migration guides: verify presence for major version upgrades.",
    ])

    # ---- Security Posture ----
    has_security_md = any(
        check_file_exists(owner, repo, f, token)
        for f in ["SECURITY.md", "SECURITY.rst", "SECURITY", ".github/SECURITY.md"]
    )
    has_security_policy = (files.get("security") is not None) if files else False
    has_dependabot = get_dependabot_status(owner, repo, token)
    # If security policy detected via community profile, that counts
    has_security_md = has_security_md or has_security_policy

    sec_signals = {
        "has_security_md": has_security_md,
        "has_security_policy": has_security_policy,
        "has_dependabot": has_dependabot,
    }

    # Security rating logic:
    # GREEN: both disclosure process AND dependency scanning present
    # YELLOW: one of the two present, OR neither present but project has strong
    #         community signals (org-backed, high stars) suggesting security is
    #         handled at org level rather than per-repo
    # RED: reserved for known unpatched CVEs (requires human review) — the script
    #      cannot detect this, so we cap automated assessment at YELLOW minimum
    has_disclosure = has_security_md or has_security_policy
    sec_score = sum([has_disclosure, has_dependabot])
    if sec_score >= 2:
        sec_overall = "GREEN"
    elif sec_score >= 1:
        sec_overall = "YELLOW"
    elif is_org or stars > 1000:
        # Large org-backed or popular projects likely handle security at org level
        sec_overall = "YELLOW"
        sec_signals["note"] = "No per-repo security policy found, but org backing suggests security may be handled at organization level."
    else:
        sec_overall = "YELLOW"
        sec_signals["note"] = "No security policy or dependency scanning detected. Manual CVE check strongly recommended."

    report["categories"]["security"] = {
        "rating": sec_overall,
        "signals": sec_signals,
        "note": "CVE response time and audit history require human review.",
    }
    report["human_review_needed"].append("Security: check for known unpatched CVEs and third-party audit history.")

    # ---- Overall Rating ----
    all_ratings = [cat["rating"] for cat in report["categories"].values()]
    red_categories = [name for name, cat in report["categories"].items() if cat["rating"] == "RED"]
    yellow_categories = [name for name, cat in report["categories"].items() if cat["rating"] == "YELLOW"]

    if "RED" in [report["categories"].get("maintenance", {}).get("rating"),
                  report["categories"].get("security", {}).get("rating")]:
        report["overall_rating"] = "RED"
        report["recommendation"] = (
            f"REJECT. Red flag in critical category: {', '.join(c for c in red_categories if c in ('maintenance', 'security'))}. "
            "Find an alternative dependency."
        )
    elif red_categories:
        report["overall_rating"] = "RED"
        report["recommendation"] = (
            f"Strong caution. Red flag in: {', '.join(red_categories)}. "
            "Document justification via ADR if no alternative exists."
        )
    elif len(yellow_categories) >= 2:
        report["overall_rating"] = "YELLOW"
        report["recommendation"] = (
            f"Closer evaluation needed. Yellow flags in: {', '.join(yellow_categories)}. "
            "Document risk assessment before adopting."
        )
    elif yellow_categories:
        report["overall_rating"] = "YELLOW"
        report["recommendation"] = (
            f"Generally healthy with minor concerns in: {', '.join(yellow_categories)}. "
            "Acceptable for adoption with awareness."
        )
    else:
        report["overall_rating"] = "GREEN"
        report["recommendation"] = "Adopt with confidence. All quantitative signals are healthy."

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OSS Health Check")
    parser.add_argument("--repo", required=True, help="GitHub owner/repo (e.g., pallets/flask)")
    parser.add_argument("--ecosystem", choices=["npm", "pypi", "crates"], default=None,
                        help="Package ecosystem for download stats")
    parser.add_argument("--package", default=None, help="Package name if different from repo name")
    parser.add_argument("--github-token", default=None, help="GitHub personal access token")
    args = parser.parse_args()

    # Also check environment variable
    token = args.github_token or os.environ.get("GITHUB_TOKEN")

    parts = args.repo.strip("/").split("/")
    if len(parts) != 2:
        print(json.dumps({"error": f"Invalid repo format '{args.repo}'. Expected owner/repo."}))
        sys.exit(1)

    owner, repo = parts
    result = evaluate(owner, repo, ecosystem=args.ecosystem, package_name=args.package, token=token)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
