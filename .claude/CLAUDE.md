# ReaTuMe — Project Rules

## Git workflow
- **Always work on the `development` branch.** Never commit directly to `main`. The workflow is: commit on `development` → push → checkout `main` → `git merge --ff-only development` → push main → checkout `development`.
- **Always `git pull` before editing files or merging branches.** Remote changes may have been pushed from another session or machine.
- All git commits must be authored as James's user — do not configure or override `user.name` / `user.email`. The system gitconfig is already correct.
- Never commit release tarballs or built packages to git. They go on the GitHub Releases page only.

## Development process
- Unless explicitly told to take an action, ask first. Do not anticipate or act on assumptions.
- Always run the QA agent after making code changes, before telling the user the code is ready to run.
