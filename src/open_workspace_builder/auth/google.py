"""Google OAuth 2.0 flow for Sheets API access.

Follows the same pattern as volcanix-papers: OAuth InstalledAppFlow with
age-encrypted credential storage. Scoped to spreadsheets only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SHEETS_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def _token_path(config_dir: str) -> Path:
    """Resolve the Google OAuth token file path."""
    return Path(config_dir).expanduser() / "google-sheets-token.json"


def _secrets_path(config_dir: str) -> Path:
    """Resolve the secrets file path."""
    return Path(config_dir).expanduser() / "secrets.yaml"


def store_google_credentials(
    client_id: str,
    client_secret: str,
    config_dir: str,
    age_key_path: str,
) -> Path:
    """Encrypt and store Google OAuth client credentials.

    Returns the path to the secrets file.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError("PyYAML is required for credential storage.") from exc

    try:
        from pyrage import x25519
    except ImportError as exc:
        raise ImportError(
            "pyrage is required for encrypted credential storage.\n"
            "Install with: uv pip install open-workspace-builder[age]"
        ) from exc

    key_path = Path(age_key_path).expanduser()
    if not key_path.exists():
        raise FileNotFoundError(
            f"Age key file not found: {key_path}. Generate one with: age-keygen -o {key_path}"
        )

    # Encrypt values using the age identity.
    identity = x25519.Identity.from_str(_load_age_private_key(key_path))
    recipient = identity.to_public()
    encrypted_id = _age_encrypt(client_id, recipient)
    encrypted_secret = _age_encrypt(client_secret, recipient)

    secrets_file = _secrets_path(config_dir)
    secrets_file.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if secrets_file.exists():
        loaded = yaml.safe_load(secrets_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            existing = loaded

    updated = {
        **existing,
        "google_sheets": {
            "client_id": encrypted_id,
            "client_secret": encrypted_secret,
        },
    }
    secrets_file.write_text(yaml.dump(updated), encoding="utf-8")
    return secrets_file


def run_oauth_flow(config_dir: str, age_key_path: str) -> Path:
    """Run the Google OAuth consent flow and save the token.

    Opens a browser for user consent. Saves the resulting token
    to the config directory.

    Returns the path to the saved token file.
    """
    try:
        import yaml  # type: ignore[import-untyped]
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise ImportError(
            "Google Sheets auth requires additional packages.\n"
            "Install with: uv pip install open-workspace-builder[sheets,age]"
        ) from exc

    try:
        import pyrage  # noqa: F401 — verify availability before proceeding
    except ImportError as exc:
        raise ImportError(
            "pyrage is required for decrypting credentials.\n"
            "Install with: uv pip install open-workspace-builder[age]"
        ) from exc

    secrets_file = _secrets_path(config_dir)
    if not secrets_file.exists():
        raise FileNotFoundError("Google credentials not found. Run `owb auth google-store` first.")

    raw = yaml.safe_load(secrets_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "google_sheets" not in raw:
        raise ValueError(
            "Google Sheets credentials not found in secrets file. "
            "Run `owb auth google-store` first."
        )

    google_data = raw["google_sheets"]
    private_key = _load_age_private_key(Path(age_key_path).expanduser())

    client_id = _age_decrypt(google_data["client_id"], private_key)
    client_secret = _age_decrypt(google_data["client_secret"], private_key)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SHEETS_SCOPES)
    creds = flow.run_local_server(port=8080)

    token_file = _token_path(config_dir)
    token_file.parent.mkdir(parents=True, exist_ok=True)

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_uri": "https://oauth2.googleapis.com/token",
        "scopes": SHEETS_SCOPES,
    }
    token_file.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    return token_file


def load_credentials(config_dir: str) -> Any:
    """Load saved Google OAuth credentials for Sheets API.

    Returns a google.oauth2.credentials.Credentials object, or raises
    if no token exists or the token is invalid.
    """
    from google.oauth2.credentials import Credentials

    token_file = _token_path(config_dir)
    if not token_file.exists():
        raise FileNotFoundError(
            f"Google Sheets token not found at {token_file}. Run `owb auth google` to authenticate."
        )

    token_data = json.loads(token_file.read_text(encoding="utf-8"))
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        scopes=token_data.get("scopes", SHEETS_SCOPES),
    )
    return creds


def _load_age_private_key(key_path: Path) -> str:
    """Extract the private key from an age identity file."""
    for line in key_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("AGE-SECRET-KEY-"):
            return line
    raise ValueError(f"No private key found in {key_path}")


def _age_encrypt(plaintext: str, recipient: Any) -> str:
    """Encrypt a string with age and return base64-encoded ciphertext."""
    import base64

    from pyrage import encrypt

    ciphertext = encrypt(plaintext.encode("utf-8"), [recipient])
    return base64.b64encode(ciphertext).decode("ascii")


def _age_decrypt(ciphertext_b64: str, private_key_str: str) -> str:
    """Decrypt a base64-encoded age ciphertext."""
    import base64

    from pyrage import decrypt
    from pyrage import x25519

    identity = x25519.Identity.from_str(private_key_str)
    ciphertext = base64.b64decode(ciphertext_b64)
    return decrypt(ciphertext, [identity]).decode("utf-8")
