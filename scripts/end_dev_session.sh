#!/bin/bash
# End Development Session
# Standardized workflow for ending a development session
#
# Usage:
#   ./scripts/end_dev_session.sh [--push] [--no-commit]
#
# Options:
#   --push         Automatically push changes (default: ask)
#   --no-commit    Skip committing changes (default: ask if uncommitted)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

AUTO_PUSH=false
SKIP_COMMIT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            AUTO_PUSH=true
            shift
            ;;
        --no-commit)
            SKIP_COMMIT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--push] [--no-commit]"
            exit 1
            ;;
    esac
done

echo "🏁 Ending Development Session"
echo "================================"
echo ""

# Step 1: Check current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "📋 Current branch: $CURRENT_BRANCH"

if [[ "$CURRENT_BRANCH" == "main" ]]; then
    echo "   ⚠️  Warning: You're on main branch. This script is for feature branches."
    echo "   Exiting without changes."
    exit 0
fi

if [[ "$CURRENT_BRANCH" == "develop" ]]; then
    # Check if develop has uncommitted changes or unpushed commits
    HAS_UNCOMMITTED=$(git diff-index --quiet HEAD --; echo $?)
    LOCAL_COMMITS=$(git rev-list --count origin/develop..HEAD 2>/dev/null || echo "0")
    
    if [[ "$HAS_UNCOMMITTED" -eq 1 ]] || [[ "$LOCAL_COMMITS" -gt 0 ]]; then
        # There's work to save, so it makes sense to continue
        echo "   ℹ️  On develop branch with work to save. Continuing..."
    else
        # No work to save, probably accidental - ask
        echo "   ⚠️  Warning: You're on develop branch with no uncommitted changes or unpushed commits."
        read -p "   Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "   Aborted."
            exit 0
        fi
    fi
fi

# Step 2: Check for uncommitted changes and untracked files
echo ""
echo "📋 Step 1: Checking for uncommitted changes and untracked files..."

# Check for uncommitted changes (modified tracked files)
HAS_UNCOMMITTED=$(git diff-index --quiet HEAD --; echo $?)

# Check for untracked files
UNTRACKED_FILES=$(git ls-files --others --exclude-standard)
HAS_UNTRACKED=false
if [[ -n "$UNTRACKED_FILES" ]]; then
    HAS_UNTRACKED=true
fi

if [[ "$HAS_UNCOMMITTED" -eq 1 ]] || [[ "$HAS_UNTRACKED" == "true" ]]; then
    echo "   ⚠️  You have changes:"
    git status --short
    
    if [[ "$SKIP_COMMIT" == "false" ]]; then
        # Analyze files to determine if they should be ignored
        FILES_TO_IGNORE=()
        FILES_TO_COMMIT=()
        
        if [[ "$HAS_UNTRACKED" == "true" ]]; then
            # Use llm CLI if available for intelligent file classification
            if command -v llm >/dev/null 2>&1; then
                echo "   🤖 Analyzing files with AI..."
                
                # Build file list with basic info
                FILE_INFO=""
                while IFS= read -r file; do
                    if [[ -f "$file" ]]; then
                        SIZE=$(wc -c < "$file" 2>/dev/null || echo "0")
                        FIRST_LINE=$(head -n 3 "$file" 2>/dev/null | head -c 200 || echo "")
                        FILE_INFO+="File: $file (size: ${SIZE} bytes)\nPreview: ${FIRST_LINE}\n---\n"
                    elif [[ -d "$file" ]]; then
                        FILE_INFO+="Directory: $file\n---\n"
                    fi
                done <<< "$UNTRACKED_FILES"
                
                # Ask llm to classify files
                PROMPT="You are analyzing untracked git files. For each file, determine if it should be:
1. IGNORED (temporary files, junk, test files, OS files, etc.) - respond with 'IGNORE: filename'
2. COMMITTED (source code, documentation, config files, etc.) - respond with 'COMMIT: filename'

Files to analyze:
${FILE_INFO}

Respond with one line per file in format 'IGNORE: filename' or 'COMMIT: filename'. Only list the files provided."
                
                LLM_RESPONSE=$(echo "$PROMPT" | llm --model gpt-4o-mini 2>/dev/null || echo "")
                
                # Parse llm response
                if [[ -n "$LLM_RESPONSE" ]]; then
                    while IFS= read -r file; do
                        # Check llm classification for this file
                        FILE_BASENAME=$(basename "$file")
                        if echo "$LLM_RESPONSE" | grep -qi "IGNORE.*${FILE_BASENAME}"; then
                            FILES_TO_IGNORE+=("$file")
                        elif echo "$LLM_RESPONSE" | grep -qi "COMMIT.*${FILE_BASENAME}"; then
                            FILES_TO_COMMIT+=("$file")
                        else
                            # Fallback: if llm didn't mention it, use simple heuristics
                            FILENAME=$(basename "$file")
                            if [[ "$FILENAME" =~ ^(\.DS_Store|\._.*|.*\.log|.*\.tmp|.*\.swp|.*~|.*\.bak|.*\.poo)$ ]] || \
                               [[ "$FILENAME" =~ ^(somestuff|junk|temp|scratch)$ ]]; then
                                FILES_TO_IGNORE+=("$file")
                            else
                                FILES_TO_COMMIT+=("$file")
                            fi
                        fi
                    done <<< "$UNTRACKED_FILES"
                else
                    # llm failed, fall back to simple heuristics
                    echo "   ⚠️  llm command failed, using simple heuristics..."
                    while IFS= read -r file; do
                        FILENAME=$(basename "$file")
                        if [[ "$FILENAME" =~ ^(\.DS_Store|\._.*|.*\.log|.*\.tmp|.*\.swp|.*~|.*\.bak|.*\.poo)$ ]] || \
                           [[ "$FILENAME" =~ ^(somestuff|junk|temp|scratch)$ ]] || \
                           [[ -d "$file" && "$FILENAME" =~ ^(node_modules|__pycache__|\.pytest_cache|\.venv|venv|env)$ ]]; then
                            FILES_TO_IGNORE+=("$file")
                        else
                            FILES_TO_COMMIT+=("$file")
                        fi
                    done <<< "$UNTRACKED_FILES"
                fi
            else
                # No llm command, use simple heuristics
                while IFS= read -r file; do
                    FILENAME=$(basename "$file")
                    if [[ "$FILENAME" =~ ^(\.DS_Store|\._.*|.*\.log|.*\.tmp|.*\.swp|.*~|.*\.bak|.*\.poo)$ ]] || \
                       [[ "$FILENAME" =~ ^(somestuff|junk|temp|scratch)$ ]] || \
                       [[ -d "$file" && "$FILENAME" =~ ^(node_modules|__pycache__|\.pytest_cache|\.venv|venv|env)$ ]]; then
                        FILES_TO_IGNORE+=("$file")
                    else
                        FILES_TO_COMMIT+=("$file")
                    fi
                done <<< "$UNTRACKED_FILES"
            fi
        fi
        
        # Handle files that should be ignored
        if [[ ${#FILES_TO_IGNORE[@]} -gt 0 ]]; then
            echo ""
            echo "   📋 Files detected that should probably be ignored:"
            for file in "${FILES_TO_IGNORE[@]}"; do
                echo "      - $file"
            done
            read -p "   Add these to .gitignore? (Y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                for file in "${FILES_TO_IGNORE[@]}"; do
                    # Add pattern to .gitignore
                    if [[ -f "$file" ]]; then
                        echo "$(basename "$file")" >> .gitignore
                    elif [[ -d "$file" ]]; then
                        echo "$(basename "$file")/" >> .gitignore
                    fi
                done
                echo "   ✅ Added to .gitignore"
                # Commit .gitignore update
                git add .gitignore
                git commit -m "chore: add files to .gitignore" >/dev/null 2>&1 || true
            fi
        fi
        
        # Check if there are still files to commit
        if [[ "$HAS_UNCOMMITTED" -eq 1 ]] || [[ ${#FILES_TO_COMMIT[@]} -gt 0 ]]; then
            # Generate a useful commit message based on changes
            COMMIT_MSG=""
            if [[ "$HAS_UNCOMMITTED" -eq 1 ]]; then
                # Try to generate a meaningful commit message from diff
                MODIFIED_FILES=$(git diff --name-only HEAD)
                if echo "$MODIFIED_FILES" | grep -q "\.py$"; then
                    COMMIT_MSG="refactor: update Python code"
                elif echo "$MODIFIED_FILES" | grep -q "\.sh$"; then
                    COMMIT_MSG="refactor: update scripts"
                elif echo "$MODIFIED_FILES" | grep -q "\.md$"; then
                    COMMIT_MSG="docs: update documentation"
                elif echo "$MODIFIED_FILES" | grep -q "\.json$\|\.yaml$\|\.yml$"; then
                    COMMIT_MSG="config: update configuration"
                else
                    COMMIT_MSG="chore: update files"
                fi
            elif [[ ${#FILES_TO_COMMIT[@]} -gt 0 ]]; then
                # New files - try to infer type
                FIRST_FILE="${FILES_TO_COMMIT[0]}"
                if [[ "$FIRST_FILE" =~ \.(py)$ ]]; then
                    COMMIT_MSG="feat: add Python module"
                elif [[ "$FIRST_FILE" =~ \.(md)$ ]]; then
                    COMMIT_MSG="docs: add documentation"
                elif [[ "$FIRST_FILE" =~ \.(sh)$ ]]; then
                    COMMIT_MSG="feat: add script"
                else
                    COMMIT_MSG="chore: add files"
                fi
            fi
            
            # Auto-commit by default (Y), but allow override
            read -p "   Commit these changes? (Y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                echo "   📝 Enter commit message (or press Enter for default):"
                echo "   Default: $COMMIT_MSG"
                read -r USER_COMMIT_MSG
                if [[ -z "$USER_COMMIT_MSG" ]]; then
                    USER_COMMIT_MSG="$COMMIT_MSG"
                fi
                
                git add -A
                git commit -m "$USER_COMMIT_MSG"
                echo "   ✅ Changes committed"
            else
                echo "   ⚠️  Skipping commit. Changes remain uncommitted/untracked."
            fi
        fi
    else
        echo "   ⚠️  Skipping commit (--no-commit flag)"
    fi
    
    # Check if there are still unresolved files after handling
    REMAINING_UNCOMMITTED=$(git diff-index --quiet HEAD --; echo $?)
    REMAINING_UNTRACKED=$(git ls-files --others --exclude-standard)
    
    if [[ "$REMAINING_UNCOMMITTED" -eq 1 ]] || [[ -n "$REMAINING_UNTRACKED" ]]; then
        echo ""
        echo "   ⚠️  Warning: You still have unresolved changes in your working directory:"
        git status --short
        echo ""
        echo "   The session will end, but these changes will remain uncommitted/untracked."
        read -p "   Continue ending session? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            echo "   ❌ Session end cancelled. Resolve changes and run again."
            exit 1
        fi
        echo "   ⚠️  Continuing with unresolved changes..."
    fi
else
    echo "   ✅ No uncommitted changes or untracked files"
fi

# Step 3: Check if branch needs pushing
echo ""
echo "📋 Step 2: Checking branch status..."
LOCAL_COMMITS=$(git rev-list --count origin/"$CURRENT_BRANCH"..HEAD 2>/dev/null || echo "0")
HAS_REMOTE=$(git ls-remote --heads origin "$CURRENT_BRANCH" | wc -l)

if [[ "$LOCAL_COMMITS" -gt 0 ]]; then
    echo "   📤 Branch has $LOCAL_COMMITS local commit(s) not pushed"
    
    # Auto-push by default (most common case)
    if [[ "$AUTO_PUSH" == "true" ]]; then
        PUSH_ANSWER="y"
    else
        # Check if we can push (network available, etc.)
        if git ls-remote --heads origin >/dev/null 2>&1; then
            # Remote is accessible, auto-push
            echo "   📤 Pushing to origin (auto)..."
            PUSH_ANSWER="y"
        else
            # Remote not accessible, ask
            read -p "   Push to origin? (Y/n): " -n 1 -r
            echo
            PUSH_ANSWER="$REPLY"
        fi
    fi
    
    if [[ ! "$PUSH_ANSWER" =~ ^[Nn]$ ]]; then
        echo "   📤 Pushing to origin..."
        git push -u origin "$CURRENT_BRANCH" 2>&1 || {
            echo "   ❌ Push failed. Check your git configuration and try again."
            exit 1
        }
        echo "   ✅ Pushed to origin"
    else
        echo "   ⚠️  Skipping push. Remember to push later!"
    fi
elif [[ "$HAS_REMOTE" -eq 0 ]]; then
    echo "   📤 Branch doesn't exist on remote"
    
    # Auto-push new branches by default
    if [[ "$AUTO_PUSH" == "true" ]]; then
        PUSH_ANSWER="y"
    else
        # Check if remote is accessible
        if git ls-remote --heads origin >/dev/null 2>&1; then
            echo "   📤 Pushing to origin (auto)..."
            PUSH_ANSWER="y"
        else
            read -p "   Push to origin? (Y/n): " -n 1 -r
            echo
            PUSH_ANSWER="$REPLY"
        fi
    fi
    
    if [[ ! "$PUSH_ANSWER" =~ ^[Nn]$ ]]; then
        echo "   📤 Pushing to origin..."
        git push -u origin "$CURRENT_BRANCH"
        echo "   ✅ Pushed to origin"
    fi
else
    echo "   ✅ Branch is up to date with remote"
fi

# Step 4: Show summary
echo ""
echo "📋 Step 3: Session Summary"
echo "================================"
echo "   Branch: $CURRENT_BRANCH"
echo "   Status: $(git status -sb | head -1 | cut -d' ' -f2-)"
echo ""

# Step 5: Optional - switch back to develop
echo "📋 Step 4: Cleanup"

# Auto-switch to develop if:
# 1. We're on a feature branch (not develop/main)
# 2. All work is committed and pushed
# 3. No uncommitted changes

if [[ "$CURRENT_BRANCH" =~ ^(dev/|feature/) ]] && git diff-index --quiet HEAD --; then
    # Check if branch is pushed
    if git rev-parse --verify "origin/$CURRENT_BRANCH" >/dev/null 2>&1 || \
       [[ "$LOCAL_COMMITS" -eq 0 ]] || [[ "$AUTO_PUSH" == "true" ]]; then
        echo "   🔄 Switching back to develop (auto)..."
        git checkout develop
        echo "   ✅ Switched to develop branch"
    else
        # Branch not pushed, ask
        read -p "   Switch back to develop branch? (Y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            git checkout develop
            echo "   ✅ Switched to develop branch"
        fi
    fi
else
    # On develop or has uncommitted changes - ask
    read -p "   Switch back to develop branch? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        git checkout develop
        echo "   ✅ Switched to develop branch"
    fi
fi

echo ""
echo "✅ Development session ended!"
echo ""
echo "Summary:"
echo "   - Branch: $CURRENT_BRANCH"
echo "   - All changes committed and pushed"
echo "   - Ready for next session"
echo ""

