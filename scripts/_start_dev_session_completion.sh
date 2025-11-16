#!/bin/bash
# Bash completion for start_dev_session.sh
# 
# To enable, add to your ~/.zshrc or ~/.bashrc:
#   source /path/to/scripts/_start_dev_session_completion.sh

_start_dev_session_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    
    # Get list of feature branches
    if command -v git >/dev/null 2>&1; then
        local feature_branches
        feature_branches=$(git for-each-ref --format='%(refname:short)' refs/heads/feature/* refs/remotes/origin/feature/* 2>/dev/null | \
            sed 's|^origin/||' | \
            sed 's|^feature/||' | \
            sort -u)
        
        # Complete feature branch names (without feature/ prefix)
        if [[ ${cur} != -* ]]; then
            COMPREPLY=( $(compgen -W "${feature_branches}" -- ${cur}) )
        fi
    fi
    
    return 0
}

complete -F _start_dev_session_completion start_dev_session.sh
complete -F _start_dev_session_completion ./scripts/start_dev_session.sh

