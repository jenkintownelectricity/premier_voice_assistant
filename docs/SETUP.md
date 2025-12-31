# GitHub Repository Setup Guide

This guide helps you configure your GitHub repository settings for optimal branch management.

---

## 🎯 Initial Setup Checklist

### 1. Set Default Branch

**Action:** Ensure `main` is set as the default branch

**Steps:**
1. Go to GitHub.com → Your Repository
2. Click **Settings** tab
3. Click **Branches** in left sidebar
4. Under "Default branch", ensure `main` is selected
5. If not, click the switch icon and change to `main`

**Why:** This ensures all new PRs target `main` by default

---

### 2. Enable Branch Protection

**Action:** Protect the `main` branch from accidental changes

**Steps:**
1. Go to **Settings** → **Branches**
2. Click **Add branch protection rule**
3. Branch name pattern: `main`
4. Enable these settings:
   - ✅ **Require a pull request before merging**
     - Required approvals: 0 (or 1 if you have a team)
   - ✅ **Require status checks to pass before merging** (if you have CI/CD)
   - ✅ **Require branches to be up to date before merging**
   - ✅ **Do not allow bypassing the above settings**
5. Disable these:
   - ❌ Allow force pushes
   - ❌ Allow deletions
6. Click **Create** or **Save changes**

**Why:** Prevents accidental direct commits to main and enforces PR workflow

---

### 3. Configure Auto-Delete Branches

**Action:** Automatically delete branches after PR merge

**Steps:**
1. Go to **Settings** → **General**
2. Scroll to "Pull Requests" section
3. Enable: ✅ **Automatically delete head branches**

**Why:** Keeps repository clean without manual intervention

---

### 4. Set Up Branch Naming Rules (Optional)

**Action:** Enforce branch naming conventions

**Steps:**
1. Go to **Settings** → **Branches**
2. Under "Branch name pattern", add rules:
   - Pattern: `claude/*` → Allow (for Claude Code)
   - Pattern: `feature/*` → Allow (for features)
   - Pattern: `fix/*` → Allow (for bug fixes)
   - Pattern: `hotfix/*` → Allow (for urgent fixes)

**Why:** Maintains consistent naming across team

---

## 🔧 Recommended Settings

### Repository Settings

**General Settings:**
```
✅ Template repository: Off
✅ Require contributors to sign off on web-based commits: Off (unless you need DCO)
✅ Allow merge commits: On
✅ Allow squash merging: On (recommended)
✅ Allow rebase merging: On
✅ Automatically delete head branches: On
✅ Allow auto-merge: On (optional, useful for automation)
```

**Pull Request Settings:**
```
✅ Allow merge commits: On
✅ Allow squash merging: On (recommended for clean history)
✅ Allow rebase merging: On
✅ Always suggest updating pull request branches: On
✅ Automatically delete head branches: On
```

---

## 🚀 Advanced Configuration

### 1. Add CODEOWNERS (Optional)

Create `.github/CODEOWNERS` to automatically request reviews:

```
# Default owner for everything
* @your-github-username

# Frontend code
/web/ @frontend-team

# Backend code
/backend/ @backend-team

# Infrastructure
/supabase/ @devops-team
/.github/ @devops-team
```

### 2. Add Pull Request Template

Create `.github/pull_request_template.md`:

```markdown
## Summary
<!-- Brief description of changes -->

## Changes
- [ ] Change 1
- [ ] Change 2
- [ ] Change 3

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Test Plan
<!-- How did you test these changes? -->

## Screenshots
<!-- If applicable, add screenshots -->

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Commits are signed off (if required)
```

### 3. Add Issue Templates

Create `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug Report
about: Report a bug
title: '[BUG] '
labels: bug
assignees: ''
---

## Description
<!-- Clear description of the bug -->

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior
<!-- What should happen -->

## Actual Behavior
<!-- What actually happens -->

## Environment
- OS: [e.g., macOS, Windows, Linux]
- Browser: [e.g., Chrome, Safari, Firefox]
- Version: [e.g., 1.0.0]

## Screenshots
<!-- If applicable -->
```

### 4. Set Up GitHub Actions (Optional)

Create `.github/workflows/ci.yml` for automated testing:

```yaml
name: CI

on:
  pull_request:
    branches: [ main ]
  push:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements.txt

    - name: Run tests
      run: |
        python -m pytest tests/

    - name: Lint
      run: |
        python -m flake8 backend/
```

---

## 📊 Monitoring & Insights

### Enable Insights

**Steps:**
1. Go to **Insights** tab
2. Review these sections regularly:
   - **Pulse** - Recent activity
   - **Contributors** - Who's contributing
   - **Traffic** - Repository visits
   - **Network** - Branch visualization

### Useful Insights

**Network Graph:**
- Shows all branches and their relationships
- Helpful for visualizing merge history
- Access: Insights → Network

**Branch Comparison:**
```
Compare branches:
https://github.com/YOUR_USERNAME/premier_voice_assistant/compare/main...feature/branch-name
```

---

## 🛠️ Maintenance Tasks

### Weekly Tasks
- [ ] Review open pull requests
- [ ] Check for stale branches (>7 days old)
- [ ] Review security alerts (if any)

### Monthly Tasks
- [ ] Run branch cleanup script
- [ ] Review branch protection rules
- [ ] Check repository insights
- [ ] Archive completed milestones

### Quarterly Tasks
- [ ] Review and update documentation
- [ ] Audit access permissions
- [ ] Review GitHub Actions usage
- [ ] Plan repository improvements

---

## 🔒 Security Settings

### 1. Enable Security Features

**Steps:**
1. Go to **Settings** → **Security & analysis**
2. Enable these features:
   - ✅ **Dependabot alerts** - Get notified of vulnerabilities
   - ✅ **Dependabot security updates** - Auto-create PRs for security fixes
   - ✅ **Secret scanning** - Detect committed secrets

### 2. Add .gitignore

Ensure `.gitignore` includes:

```
# Environment files
.env
.env.local
.env.*.local

# API keys
**/secrets/
**/credentials/

# Dependencies
node_modules/
__pycache__/
*.pyc

# Build outputs
dist/
build/
.next/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

---

## 📋 Current Repository Status

### Default Branch
✅ `main` (verified and set)

### Protected Branches
⚠️ Not yet configured (recommended to set up)

### Auto-Delete
⚠️ Not yet configured (recommended to enable)

### Documentation
✅ Branch workflow guide created
✅ Branch organization document created
✅ Cleanup script available

---

## 🆘 Need Help?

### Resources
- **GitHub Docs:** https://docs.github.com
- **Git Docs:** https://git-scm.com/doc
- **Branch Workflow:** See `.github/BRANCH_WORKFLOW.md`
- **Cleanup Script:** Run `./scripts/cleanup_old_branches.sh`

### Common Issues

**Issue:** Can't push to main
**Solution:** Push to a branch and create a PR instead

**Issue:** Branch protection blocking PR
**Solution:** Ensure all required checks pass

**Issue:** Too many branches
**Solution:** Run cleanup script regularly

---

**Last Updated:** 2025-11-22
