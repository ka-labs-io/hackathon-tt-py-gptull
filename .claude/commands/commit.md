Create an atomic conventional commit for the current staged or unstaged changes.

Usage examples:
- `/commit` — commit all changes, split by concern if needed
- `/commit --push` — commit and then push to the remote branch
- `/commit src/foo.py src/bar.py` — commit only the specified files
- `/commit src/foo.py --push` — commit specified files and push

## Steps

1. Parse `$ARGUMENTS` for:
   - `--push` flag: if present, push after all commits are made
   - File/path arguments: if present, restrict staging to only those paths
2. Run `git status` and `git diff HEAD` (scoped to any specified paths) to understand what has changed.
3. Determine what to stage:
   - If specific paths were given, stage only those: `git add <paths>`
   - Otherwise, stage all changed tracked files with `git add -u`, plus any untracked files clearly belonging to the change
4. Analyze the diff and identify the smallest logical unit of change. If the diff spans multiple unrelated concerns, group related files and commit them separately — one commit per concern.
5. Write a conventional commit message following this format:
   ```
   <type>(<optional scope>): <short imperative summary>
   ```
   - Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `style`, `ci`, `build`
   - Scope: optional, use the module/area affected (e.g. `runner`, `cli`, `scoring`)
   - Summary: lowercase, imperative mood, no trailing period, ≤72 chars
   - Be precise and descriptive — name the actual thing changed, not a vague category
     - Bad: `fix: update runner logic`
     - Good: `fix(runner): skip empty lines before scoring pass`
   - No filler words ("various", "some", "minor", "improvements", "updates")
   - Add a body only if the *why* is non-obvious — keep it one sentence, direct and factual
6. Run the commit. Do not use `--no-verify`.
7. If pre-commit hooks fail, fix the issue and retry as a new commit — never amend to work around hooks.
8. If `--push` was given, push the current branch to its remote tracking branch after all commits succeed. Confirm before force-pushing; never force-push to main/master.
9. Report each commit hash and message, and the push result if applicable.

## Rules

- One concern per commit — never bundle unrelated changes.
- Do not commit files that likely contain secrets (`.env`, credentials, tokens).
- Do not push unless `--push` is explicitly passed.
