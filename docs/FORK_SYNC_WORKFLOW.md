# Fork Sync Workflow

This document describes best practices for keeping your fork's `main` branch synchronized with the upstream repository.

## Overview

The `aculich/bp-telemetry-experimental` fork maintains `main` as a mirror of `blueplane-ai/bp-telemetry-core`'s `main` branch. All feature work should be done on separate branches.

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

- **Always sync before starting new work**: `./scripts/sync_upstream.sh`
- **Work on feature branches**: Never commit directly to `main`
- **Use `--dry-run` first**: Preview changes before applying them
- **Keep `main` clean**: It should always match upstream exactly
- **Backup important commits**: The script preserves commits in backup branches

### ❌ DON'T

- **Don't commit directly to `main`**: Use feature branches instead
- **Don't force push without checking**: Always verify with `--dry-run` first
- **Don't sync with uncommitted changes**: Commit or stash first
- **Don't merge feature branches into `main`**: Keep `main` as upstream mirror

## Workflow Example

```bash
# 1. Start new feature work
./scripts/sync_upstream.sh  # Sync first
git checkout -b feature/my-feature

# 2. Make changes and commit
git add .
git commit -m "feat: add new feature"

# 3. Push feature branch
git push origin feature/my-feature

# 4. Create PR from feature branch (not main)

# 5. After PR is merged upstream, sync again
./scripts/sync_upstream.sh
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

