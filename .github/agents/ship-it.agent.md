---
description: Commit, push, create a PR, and merge the current branch into main. Always uses a regular merge (never squash). Presents PR title and body for user review before creating.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Workflow

### 1. Gather Context

- Run `git branch --show-current` to get the current branch name.
- Run `git status --short` to see changed/untracked files.
- Run `git log main..HEAD --oneline` to see commits not yet on main.
- Run `git remote -v` to confirm the remote name (usually `origin`).
- Extract the GitHub owner and repo from the remote URL.

**Guard rails:**
- If on `main`, STOP and tell the user: "You are on main. Switch to a feature branch first."
- If there are no changes AND no commits ahead of main, STOP: "Nothing to ship."

### 2. Stage and Commit

- If there are uncommitted changes (modified or untracked files):
  - Run `git add -A` to stage everything.
  - Generate a conventional-commit message summarizing the changes.
    - Use `feat:` for new features, `fix:` for bug fixes, `chore:` for maintenance.
    - Keep the subject line under 72 characters.
    - Add a body with bullet points for significant changes if there are many files.
  - Run `git commit -m "<message>"`.
- If there are no uncommitted changes, skip this step.

### 3. Push to GitHub

- Run `git push -u origin <branch>` to push the branch.

### 4. Propose PR Details

Before creating the PR, present the following to the user for review:

```
PR Title: <proposed title>

PR Body:
<proposed body in markdown>
```

The PR body should include:
- A summary of what the branch accomplishes
- Key changes organized by category (features, fixes, refactors)
- Any noteworthy implementation details

**Wait for user approval before proceeding.** The user may edit the title or body.

### 5. Create Pull Request

- Use the GitHub MCP to create a pull request:
  - Base: `main`
  - Head: `<current branch>`
  - Title and body as approved by the user
- Report the PR number and URL to the user.

### 6. Merge Pull Request

- Use the GitHub MCP to merge the pull request:
  - **Merge method: `merge`** (NEVER use `squash` or `rebase`)
- Confirm the merge was successful.
- Report the final status.

### 7. Post-Merge Cleanup (Optional)

- If the user's input includes "cleanup" or "clean", also:
  - Run `git checkout main && git pull` to update local main.
  - Run `git branch -d <branch>` to delete the local feature branch.
- Otherwise, skip cleanup and inform the user they can do it manually.
