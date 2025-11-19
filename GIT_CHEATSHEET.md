# Git Cheatsheet

## Basic Workflow

### Check Status
```bash
git status                    # See changed files
git log --oneline -10         # Recent commits
git branch -a                 # List all branches
git remote -v                 # Show remotes
```

### Stage & Commit
```bash
git add .                     # Stage all changes
git add <file>                # Stage specific file
git commit -m "message"       # Commit with message
git commit --amend            # Edit last commit
```

### Push & Pull
```bash
git push origin <branch>      # Push to remote
git push -u origin <branch>   # Push & set upstream
git pull origin <branch>      # Pull from remote
git fetch origin              # Fetch without merge
```

---

## Branching

### Create & Switch
```bash
git branch <name>             # Create branch
git checkout <name>           # Switch to branch
git checkout -b <name>        # Create & switch
git switch <name>             # Switch (newer)
git switch -c <name>          # Create & switch (newer)
```

### Merge
```bash
git checkout main             # Switch to main
git merge <feature-branch>    # Merge feature into main
git merge --no-ff <branch>    # Merge with commit
```

### Delete
```bash
git branch -d <name>          # Delete local (safe)
git branch -D <name>          # Delete local (force)
git push origin --delete <name>  # Delete remote
```

---

## Merging to Main & Deploy

### Standard Workflow
```bash
# 1. Fetch latest
git fetch origin main

# 2. Switch to main
git checkout main
git pull origin main

# 3. Merge feature branch
git merge <feature-branch>

# 4. Push to main
git push origin main

# 5. Delete feature branch (optional)
git branch -d <feature-branch>
git push origin --delete <feature-branch>
```

### If Conflicts Occur
```bash
# After merge attempt shows conflicts:
git status                    # See conflicted files
# Edit files to resolve conflicts
git add .                     # Stage resolved files
git commit                    # Complete merge
```

---

## Undo & Reset

### Discard Changes
```bash
git checkout -- <file>        # Discard file changes
git restore <file>            # Discard (newer)
git restore --staged <file>   # Unstage file
git reset HEAD <file>         # Unstage (older)
```

### Reset Commits
```bash
git reset --soft HEAD~1       # Undo commit, keep changes staged
git reset --mixed HEAD~1      # Undo commit, keep changes unstaged
git reset --hard HEAD~1       # Undo commit, DELETE changes
```

### Revert (Safe)
```bash
git revert <commit>           # Create undo commit
```

---

## Stash

```bash
git stash                     # Save changes temporarily
git stash pop                 # Restore & remove from stash
git stash apply               # Restore & keep in stash
git stash list                # List all stashes
git stash drop                # Delete latest stash
git stash clear               # Delete all stashes
```

---

## View History

```bash
git log --oneline             # Compact log
git log --graph --oneline     # Visual branch graph
git log -p <file>             # File change history
git blame <file>              # Who changed each line
git diff                      # Unstaged changes
git diff --staged             # Staged changes
git diff <branch1> <branch2>  # Compare branches
```

---

## Remote Operations

```bash
git remote add origin <url>   # Add remote
git remote set-url origin <url>  # Change remote URL
git push --force origin <branch>  # Force push (CAREFUL!)
git push --force-with-lease   # Safer force push
```

---

## Tags

```bash
git tag v1.0.0                # Create tag
git tag -a v1.0.0 -m "msg"    # Annotated tag
git push origin v1.0.0        # Push tag
git push origin --tags        # Push all tags
git tag -d v1.0.0             # Delete local tag
```

---

## Configuration

```bash
git config --global user.name "Name"
git config --global user.email "email@example.com"
git config --list             # Show all config
```

---

## Common Scenarios

### Oops, committed to wrong branch
```bash
git log --oneline -1          # Note commit hash
git reset --soft HEAD~1       # Undo commit
git stash                     # Stash changes
git checkout <correct-branch>
git stash pop                 # Apply changes
git commit -m "message"
```

### Update feature branch with main
```bash
git checkout <feature-branch>
git merge main                # Or: git rebase main
```

### See what changed in a commit
```bash
git show <commit>
git show <commit> --stat      # Just file names
```

### Find which commit broke something
```bash
git bisect start
git bisect bad                # Current is broken
git bisect good <commit>      # This was working
# Git will checkout commits for you to test
git bisect reset              # Done
```

---

## Vercel Deploy Branches

### Deploy from specific branch
```bash
# If Vercel deploys from 'deploy' branch:
git checkout deploy
git merge main
git push origin deploy
```

### Change Vercel production branch
1. Vercel Dashboard → Project → Settings
2. Git → Production Branch
3. Change to `main` or desired branch

---

## Quick Reference

| Action | Command |
|--------|---------|
| New branch | `git checkout -b name` |
| Switch branch | `git checkout name` |
| Stage all | `git add .` |
| Commit | `git commit -m "msg"` |
| Push | `git push origin branch` |
| Pull | `git pull origin branch` |
| Merge | `git merge branch` |
| Stash | `git stash` |
| Unstash | `git stash pop` |
| Undo last commit | `git reset --soft HEAD~1` |
| Discard changes | `git restore file` |

---

*Print tip: Use landscape orientation for better readability*
