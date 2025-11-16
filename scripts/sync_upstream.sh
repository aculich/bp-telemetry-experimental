#!/bin/bash
# Sync fork's main branch with upstream/main
# This script ensures origin/main stays in sync with upstream/main
#
# Usage:
#   ./scripts/sync_upstream.sh [--dry-run] [--merge]
#
# Options:
#   --dry-run    Show what would happen without making changes
#   --merge      Use merge instead of reset (preserves history but creates merge commits)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DRY_RUN=false
USE_MERGE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --merge)
            USE_MERGE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--merge]"
            exit 1
            ;;
    esac
done

cd "$REPO_ROOT"

# Safety checks
echo "🔍 Checking repository state..."

# Check if we're on main branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    echo "❌ Error: Must be on 'main' branch. Currently on: $CURRENT_BRANCH"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo "❌ Error: You have uncommitted changes. Please commit or stash them first."
    git status --short
    exit 1
fi

# Check if upstream remote exists
if ! git remote | grep -q "^upstream$"; then
    echo "❌ Error: 'upstream' remote not found."
    echo "Add it with: git remote add upstream https://github.com/blueplane-ai/bp-telemetry-core.git"
    exit 1
fi

# Fetch latest from upstream
echo "📥 Fetching latest from upstream..."
if [[ "$DRY_RUN" == "false" ]]; then
    git fetch upstream
fi

# Get current commit hashes
CURRENT_COMMIT=$(git rev-parse HEAD)
UPSTREAM_COMMIT=$(git rev-parse upstream/main)
ORIGIN_COMMIT=$(git rev-parse origin/main 2>/dev/null || echo "none")

echo ""
echo "📊 Current state:"
echo "   Local main:    $CURRENT_COMMIT ($(git log -1 --oneline HEAD))"
echo "   Upstream main: $UPSTREAM_COMMIT ($(git log -1 --oneline upstream/main))"
echo "   Origin main:   $ORIGIN_COMMIT ($(git log -1 --oneline origin/main 2>/dev/null || echo "unknown"))"
echo ""

# Check if already in sync
if [[ "$CURRENT_COMMIT" == "$UPSTREAM_COMMIT" ]]; then
    echo "✅ Already in sync with upstream/main"
    
    # Check if origin needs updating
    if [[ "$ORIGIN_COMMIT" != "$UPSTREAM_COMMIT" ]]; then
        echo "⚠️  Origin/main is out of sync. Updating..."
        if [[ "$DRY_RUN" == "false" ]]; then
            git push origin main --force
            echo "✅ Pushed to origin/main"
        else
            echo "   [DRY RUN] Would run: git push origin main --force"
        fi
    else
        echo "✅ Everything is in sync!"
    fi
    exit 0
fi

# Show what will change
echo "📋 Commits that will be added:"
git log --oneline "$CURRENT_COMMIT".."$UPSTREAM_COMMIT" | head -10
if [[ $(git rev-list --count "$CURRENT_COMMIT".."$UPSTREAM_COMMIT") -gt 10 ]]; then
    echo "   ... and $(( $(git rev-list --count "$CURRENT_COMMIT".."$UPSTREAM_COMMIT") - 10 )) more"
fi

echo ""
echo "📋 Commits that will be removed (if any):"
LOCAL_ONLY=$(git log --oneline "$UPSTREAM_COMMIT".."$CURRENT_COMMIT" 2>/dev/null || true)
if [[ -n "$LOCAL_ONLY" ]]; then
    echo "$LOCAL_ONLY"
    echo ""
    echo "⚠️  Warning: These commits will be lost from main (but preserved in backup branches)"
else
    echo "   (none)"
fi

if [[ "$DRY_RUN" == "true" ]]; then
    echo ""
    echo "🔍 DRY RUN MODE - No changes will be made"
    if [[ "$USE_MERGE" == "true" ]]; then
        echo "   Would run: git merge upstream/main"
        echo "   Would run: git push origin main"
    else
        echo "   Would run: git reset --hard upstream/main"
        echo "   Would run: git push origin main --force"
    fi
    exit 0
fi

# Perform sync
echo ""
if [[ "$USE_MERGE" == "true" ]]; then
    echo "🔄 Merging upstream/main into main..."
    git merge upstream/main --no-edit
    echo "✅ Merged upstream/main"
    
    echo "📤 Pushing to origin..."
    git push origin main
    echo "✅ Pushed to origin/main"
else
    echo "🔄 Resetting main to match upstream/main exactly..."
    git reset --hard upstream/main
    echo "✅ Reset local main to upstream/main"
    
    echo "📤 Force pushing to origin..."
    git push origin main --force
    echo "✅ Force pushed to origin/main"
fi

echo ""
echo "✅ Sync complete! origin/main is now in sync with upstream/main"

