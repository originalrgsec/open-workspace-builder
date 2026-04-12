# Sprint Workflow

This rule is optional and intended for teams using sprint-driven development
workflows. It does not interfere with ad-hoc usage patterns. Remove this file
if your project does not use sprints.

## Autonomous Sprint Mechanics

When the operator confirms a sprint plan (scope, story set, and order),
execute the full mechanical follow-through as one atomic unit. Do NOT
list these as "optional next steps" and ask permission for each one.

The sprint-kickoff unit of work:

1. **Write the sprint plan file** to the project's sprints directory with
   standard frontmatter: goal, theme, stories, definition of done, scope, risks.
2. **Cut the sprint branch** from `main` at the current release tag
   (`git checkout -b sprint-NN-<theme>`). Do not push until first commit.
3. **Update each story file's frontmatter**: `status: planned`,
   `sprint: NN`. Bump `updated` to today's date.
4. **Update `status.md`** with a new entry describing the sprint shape,
   sequencing rationale, and anything explicitly deferred.
5. **Update the project index**: add the sprint table row, flip any
   newly in-scope story rows, bump the project `updated` date.

## Rationale

Sprint planning is one task, not a menu of individual approvals. The
operator has already made the load-bearing decisions (scope, story
selection, order, deferrals) at confirmation time. Everything after
that is mechanical bookkeeping: new branch from main, frontmatter
bumps, status log entry, index updates. Asking for each step wastes
context and signals uncertainty that isn't there.

## Execution Phase Contract

Once a sprint is confirmed and kicked off, the entire lifecycle runs
autonomously: setup, story implementation, repo management, and sprint
closeout. All questions are resolved during sprint planning and story
writing. Do not re-ask during execution.

### What this overrides during sprint execution

- **"Ask clarifying questions before any non-trivial task"** — stories
  were scoped during planning. Do not re-ask before implementing a
  planned story.
- **"Plan First" and "Research & Reuse"** — skip these steps when the
  story file already contains acceptance criteria and an implementation
  approach. Run them only if a story explicitly says "research spike"
  or has no implementation section.
- **Policy re-reads** — policies were consulted during sprint planning.
  Do not re-read policy documents before each story unless the story
  involves a new dependency or a policy-governed decision not covered
  by the existing story scope.
- **Security and code quality checklists** — run these as silent
  self-checks before commits. Do not prompt the operator to confirm
  each checklist item.

### Actions that remain gated (always ask before executing)

- Force push, history rewrite, deleting committed work
- Merging the sprint branch back to main before the sprint-completion
  checklist runs
- Tagging a release
- Pushing to any remote other than the project's own origin
- Deleting or renaming branches that contain uncommitted work

### Actions that are default-yes throughout the sprint

- Creating the sprint branch locally
- Writing/editing project files in the sprint's scope
- Updating story frontmatter within the confirmed sprint scope
- Updating project index entries for the active sprint
- Implementing stories per their acceptance criteria (TDD, code, tests)
- Running code review and security review agents (silently, no prompt)
- Committing and pushing to the sprint branch
- Running the sprint-close checklist (verification, not confirmation)
- Writing session logs at session end
