# Fork Sync Workflow

This document describes best practices for keeping your fork's `main` branch synchronized with the upstream repository.

## Overview

The `aculich/bp-telemetry-experimental` fork uses a branching strategy that keeps `main` as a mirror of `blueplane-ai/bp-telemetry-core`'s `main` branch, while maintaining fork-specific development on `develop`.

### Branch Structure

- **`main`**: Mirror of `upstream/main` - never commit directly here
- **`develop`**: Fork's main development branch - fork-specific features, scripts, and docs
- **`feature/*`**: Feature branches branched off `develop` for specific work

This ensures:
- `main` stays clean and always matches upstream
- Fork-specific work is organized on `develop`
- Feature work is isolated and can be easily rebased

## Quick Sync

Use the provided script for safe, automated syncing:

```bash
# Standard sync (reset to match upstream exactly)
./scripts/sync_upstream.sh

# Preview changes without making them
./scripts/sync_upstream.sh --dry-run

# Use merge instead of reset (preserves history but creates merge commits)
./scripts/sync_upstream.sh --merge
```

## Manual Sync Process

If you prefer to sync manually:

### 1. Ensure you're on main and have no uncommitted changes

```bash
git checkout main
git status  # Should show "working tree clean"
```

### 2. Fetch latest from upstream

```bash
git fetch upstream
```

### 3. Sync with upstream

**Option A: Reset (Recommended for exact mirror)**
```bash
# Reset local main to match upstream exactly
git reset --hard upstream/main

# Force push to origin
git push origin main --force
```

**Option B: Merge (Preserves local history)**
```bash
# Merge upstream into local main
git merge upstream/main --no-edit

# Push to origin
git push origin main
```

### 4. Verify sync

```bash
git log --oneline --graph upstream/main origin/main -10
```

## Best Practices

### ✅ DO

- **Always sync `main` before starting new work**: `./scripts/sync_upstream.sh`
- **Work on `develop` for fork-specific changes**: Scripts, docs, fork features
- **Branch off `develop` for features**: `git checkout -b feature/name develop`
- **Use `--dry-run` first**: Preview changes before applying them
- **Keep `main` clean**: It should always match upstream exactly
- **Merge `main` into `develop` regularly**: Keep `develop` up-to-date with upstream

### ❌ DON'T

- **Don't commit directly to `main`**: It's a mirror of upstream
- **Don't commit upstream features to `develop`**: Use `main` → `develop` merge instead
- **Don't force push without checking**: Always verify with `--dry-run` first
- **Don't sync with uncommitted changes**: Commit or stash first
- **Don't merge feature branches into `main`**: Keep `main` as upstream mirror

## Workflow Examples

### Starting New Feature Work

```bash
# 1. Sync main with upstream (if needed)
git checkout main
./scripts/sync_upstream.sh

# 2. Update develop with latest upstream changes
git checkout develop
git merge main  # or git rebase main for cleaner history

# 3. Create feature branch from develop
git checkout -b feature/my-feature

# 4. Make changes and commit
git add .
git commit -m "feat: add new feature"

# 5. Push feature branch
git push origin feature/my-feature

# 6. Create PR from feature branch to develop (or upstream if contributing back)
```

### Fork-Specific Development (Scripts, Docs, etc.)

```bash
# Work directly on develop for fork-specific changes
git checkout develop

# Make changes
git add .
git commit -m "docs: update fork workflow"

# Push to origin
git push origin develop
```

### Syncing After Upstream Changes

```bash
# 1. Sync main with upstream
git checkout main
./scripts/sync_upstream.sh

# 2. Update develop with latest upstream
git checkout develop
git merge main  # Brings upstream changes into develop

# 3. Continue development
git checkout -b feature/new-feature
```

## Safety Features

The sync script includes several safety checks:

1. **Branch check**: Ensures you're on `main`
2. **Clean working tree**: Prevents accidental loss of uncommitted changes
3. **Remote verification**: Confirms `upstream` remote exists
4. **Dry-run mode**: Preview changes before applying
5. **Status reporting**: Shows what will change before syncing

## Alternative: GitHub Actions (Future)

For automated syncing, consider setting up a GitHub Action that:
- Runs on a schedule (e.g., daily)
- Fetches from upstream
- Resets `main` to match upstream
- Force pushes to origin

Example workflow:
```yaml
name: Sync Upstream
on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight
  workflow_dispatch:  # Manual trigger

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: |
          git fetch upstream
          git checkout main
          git reset --hard upstream/main
          git push origin main --force
```

## Troubleshooting

### "upstream remote not found"
```bash
git remote add upstream https://github.com/blueplane-ai/bp-telemetry-core.git
```

### "You have uncommitted changes"
```bash
# Option 1: Commit them
git add .
git commit -m "WIP: my changes"

# Option 2: Stash them
git stash
./scripts/sync_upstream.sh
git stash pop
```

### "Must be on main branch"
```bash
git checkout main
./scripts/sync_upstream.sh
```

## Related Documentation

- [Worktree Management](./WORKTREE_MANAGEMENT.md) - Managing multiple worktrees
- [Architecture](./ARCHITECTURE.md) - Project architecture overview

