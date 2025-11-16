## Developer Workflow Vision: Branching, PRs, and AI‑Aware Tooling

This document captures how we think about branching, pull requests, CI/CD, and AI‑assisted workflows for this project. It’s meant to evolve alongside the codebase and community.  
For task‑level, “how to” documentation, see `DEV_SESSION_WORKFLOW.md`.

---

## 1. Current Workflow (Project‑Specific)

### 1.1 Branch Roles

- **`main`**  
  - Mirror of `upstream/main` (`blueplane-ai/bp-telemetry-core`).  
  - Never developed on directly.  
  - Kept in sync via `scripts/sync_upstream.sh`.

- **`develop`**  
  - Long‑lived integration branch for fork‑specific work (scripts, docs, telemetry experiments).  
  - Regularly updated from `main`.

- **`feature/*`**  
  - Medium‑lived branches for coherent work streams (e.g., new telemetry features, major refactors).  
  - Merge targets for daily session branches when doing multi‑day work.

- **`dev/session-*`**  
  - Short‑lived “session” branches created by `start_dev_session.sh`.  
  - Typically exist for a single focused work session.  
  - Merge back into either a feature branch or `develop`, then can be safely deleted.

### 1.2 Scripts (Current Behavior)

- **`sync_upstream.sh`**  
  - Safely syncs `main` with `upstream/main`.  
  - Supports dry‑run mode and merge vs reset semantics.

- **`start_dev_session.sh`** (v2)  
  - Steps:
    1. Ensures `main` is synced with upstream (with dry‑run + prompts).
    2. Ensures `develop` is updated from `main`.
    3. Optionally creates/checks out a **feature branch**:
       - `./scripts/start_dev_session.sh` → session from `develop`.
       - `./scripts/start_dev_session.sh my-feature` → session from `feature/my-feature`.
       - `./scripts/start_dev_session.sh my-feature session-name` → named session from that feature.
    4. Creates or reuses a **session branch** `dev/session-*` off the chosen base branch.
    5. Stores the base branch in git config: `branch.<session>.baseBranch` so that `end_dev_session.sh` knows where to merge.
    6. Shows current status and next‑step instructions.
  - Difference from v1:
    - v1 treated `develop` as the implicit merge target for all sessions.
    - v2 makes the base branch explicit (feature or `develop`) and records it for later.

- **`end_dev_session.sh`** (v2)  
  - Steps:
    1. Detects uncommitted changes and untracked files.
    2. Uses `llm` (if available) to classify untracked files as “junk” vs “important”.
    3. Offers junk file options: **ignore**, **leave alone** (default), **commit**, **abort**.
    4. Shows exactly which files will be committed (M/A list).
    5. Prompts to commit (default yes), with AI‑suggested commit message templates.
    6. Pushes the session branch (auto or with confirmation).
    7. Determines the **base branch** for this session:
       - Prefers `branch.<session>.baseBranch` from git config (set by `start_dev_session.sh`).
       - Otherwise infers a closest `feature/*` branch; falls back to `develop`.
    8. Prompts to merge session → base branch (default yes).
    9. Uses `llm` to generate a concise merge commit message for the session → base merge.
    10. Performs the merge and returns the working directory to the base branch.
  - Difference from v1:
    - v1 always assumed `develop` as the “safe home” for session branches.
    - v2 merges sessions back into the **correct base branch** (feature or `develop`), which more accurately models where the work conceptually belongs.

- **`resume_dev_session.sh`**  
  - Lists recent `dev/session-*` branches (local + remote), filtered to only those that have commits (non‑empty sessions).  
  - Sorts by commit date, shows relative time, and lets you pick one (default: most recent).  
  - Handles uncommitted changes (with stash option) and checks out the selected session branch.

### 1.3 AI Assistance in the Workflow

We already use AI in two places:

- **File classification** in `end_dev_session.sh` to distinguish junk/temporary files from meaningful artifacts.
- **Commit / merge message generation** using `llm` to produce concise, conventional messages for merges.

This is an early form of an AI‑aware git workflow tailored to developer ergonomics.

---

## 2. Relationship to GitFlow and Modern Git Patterns

### 2.1 Classic GitFlow (High Level)

GitFlow (Vincent Driessen’s model) uses:

- Long‑lived: `master` (releases), `develop` (integration).
- Short‑lived: `feature/*`, `release/*`, `hotfix/*`, `support/*`.

It is well‑suited for:

- Multiple release lines (e.g., v1.x, v2.x maintained in parallel).
- Environments with very controlled release processes (on‑prem, regulated sectors).

### 2.2 How Our Workflow Differs

Similarities:

- `main` (mirror of upstream) and `develop` (integration) parallel GitFlow’s `master` + `develop`.
- `feature/*` is used for longer‑lived work streams.

Differences:

- `main` is **not** our release branch; it’s a strict mirror of upstream.
- No explicit `release/*` or `hotfix/*` branches (and no need for them today).
- We introduce **`dev/session-*`** as ultra‑short‑lived branches modeling “work sessions,” which GitFlow does not.
- We integrate **AI assistance** directly into routine git operations (classification + messages).

In practice we are closer to:

- **GitHub Flow** / **trunk‑based development**, with:
  - A stable `main` (mirror)
  - A long‑lived integration branch `develop`
  - Short‑lived feature and session branches

This is generally more aligned with modern continuous integration practices than full GitFlow for a project like ours.

---

## 3. Stacked PRs and Stacked Diffs

### 3.1 What Are Stacked PRs?

**Stacked PRs** (or stacked diffs) is a pattern where:

- You break a large change into a **sequence of small PRs**.
- Each PR is based on the previous one instead of all of them being based on `develop`/`main`.
- The stack looks like:
  - `feature/part-1` ← `feature/part-2` ← `feature/part-3` …
- Each PR is reviewable and mergeable on its own, but they build on each other.

Benefits:

- Smaller review units → better feedback and faster review cycles.
- Easier bisection and revert (failures are localized).
- Encourages *incremental design* instead of big‑bang changes.

### 3.2 Tools & Ecosystem

#### Graphite

- A SaaS and CLI tool that sits on top of GitHub.
- Focused on:
  - Creating and managing stacked PRs.
  - Visualizing the stack (dependency chain of PRs).
  - Keeping stacks rebased and in sync with base branches.
- Integrates with GitHub review workflows; you still use GitHub PRs, but Graphite helps orchestrate them.

#### GitHub “Stacked PR” Pattern (Without Extra Tools)

Even without Graphite, many teams use a stacked pattern manually:

- Use branches like:
  - `feature/base`
  - `feature/base-part-1` (from `feature/base`)
  - `feature/base-part-2` (from `feature/base-part-1`)
  - etc.
- Open PRs for each branch in sequence.
- As earlier PRs are merged, you rebase the later ones onto the updated base.

GitHub doesn’t yet have first‑class “stacked PR” primitives; it’s a **convention** plus branch discipline.

#### GitButler / Butler‑Style Tools

There is a new wave of tools (e.g. GitButler) that:

- Provide a **smart git client** with concepts like:
  - “Virtual branches” or “change sets” that can be stacked.
  - AI assistance for commit/branch organization.
  - Better visualization of ongoing work.
- Aim to:
  - Automatically split or group changes.
  - Help manage multiple in‑flight branches/PRs.

These are still emergent, but the direction overlaps strongly with what we are doing manually:

- Break work into small units.
- Keep them organized in a stack.
- Use AI to help with naming, classification, and messaging.

### 3.3 How Stacks Relate to Our Workflow

Our **session branches** are already “micro‑chunks” of work. We can combine this with stacking:

- Use `feature/*` branches as **stack roots**.
- For a feature that is too big for a single PR:
  - Create multiple session branches that merge into the same feature branch in sequence.
  - Or explicitly create stacked feature branches:
    - `feature/cursor-markdown-base`
    - `feature/cursor-markdown-phase-1`
    - `feature/cursor-markdown-phase-2`
  - Each phase can be a separate PR upstream.

Our scripts can be extended later to:

- Understand stack relationships (e.g., store `branch.<session>.parentBranch`).
- Offer commands like “start next stacked session from this feature branch.”
- Generate PR descriptions that reference the stack ordering (e.g., “This is part 2 of N”).

For this project as it grows, stacked PRs are attractive because:

- We’ll add complex telemetry features that touch many layers (capture, processing, dashboards).
- Stacks let us land these in **safe, incremental slices** while keeping upstream contributions reviewable.

---

## 4. Tight CI/CD Loops and Small Changes

### 4.1 Principles

Modern CI/CD best practices emphasize:

- **Small, frequent changes**:
  - Easier to review.
  - Easier to revert.
  - Reduce risk per deploy.

- **Fast feedback**:
  - Tests and linting run automatically on each PR.
  - Developers get results in minutes, not hours.

- **Continuous integration into a stable branch**:
  - Changes are merged quickly after passing checks.
  - Avoid long‑lived diverging branches when possible.

- **Continuous delivery or deployment**:
  - Optionally deploy automatically after merging to `main`/release branch.

### 4.2 How This Applies to This Project

This repo is both:

- A **telemetry system** for dev tools (Cursor, Claude, etc.).
- A **reference implementation** for developer workflows.

This makes small, testable increments and reliable CI particularly strategic:

- Telemetry features can be introduced in small slices:
  - “Add capture of X metadata.”
  - “Add markdown rendering for Y field.”
  - “Add a new query for cursorDiskKV.”
- Each slice can be:
  - Implemented in a session branch.
  - Merged into a feature branch.
  - Tested and documented.

As the open source community grows, tight CI/CD will:

- Give external contributors rapid feedback on their PRs.
- Reduce the burden on maintainers to manually validate complex changes.

### 4.3 Concrete Next Steps for CI/CD

We can incrementally build:

1. **GitHub Actions CI**:
   - Run:
     - `python -m compileall` or `ruff`/`flake8`/`black` checks.
     - Unit tests (where they exist).
   - Trigger on:
     - Pull requests to `develop` or `feature/*`.

2. **Telemetry‑Aware CI**:
   - As the telemetry pipeline stabilizes, add tests that:
     - Spin up a local Cursor/Claude environment (or simulated events).
     - Verify that expected events land in the database and markdown artifacts.

3. **Automated checks for workflow scripts**:
   - Basic shell linting (e.g., `shellcheck`) on `scripts/*.sh`.
   - Guard rails to keep the workflow scripts themselves reliable.

4. **Optional: Release automation** (later):
   - On merges to `main` in upstream, build and publish Docker images or packages.
   - For this fork, we may instead:
     - Tag key milestones (e.g., `telemetry-v1`, `telemetry-v2`).

---

## 5. How This Positions the Project as a “Telemetry + Workflow” Leader

Because this project is about **developer telemetry** and **AI tooling instrumentation**, our workflow choices are themselves part of the product story:

- We are:
  - Using **session branches** and **feature branches** to model realistic developer behavior.
  - Using **AI** to assist with:
    - File classification (junk vs meaningful).
    - Commit and merge messages.
  - Moving toward **stacked, incremental changes** rather than monolithic PRs.
  - Planning for **tight CI/CD loops** to validate telemetry changes quickly.

This creates opportunities:

- Our telemetry can:
  - Observe how developers actually branch, commit, and merge across tools like Cursor and Claude.
  - Correlate workflow patterns (e.g., stacked PR usage, session duration) with outcomes (e.g., fewer regressions).

- We can publish:
  - Best practice guides (this document, `DEV_SESSION_WORKFLOW.md`, `FORK_SYNC_WORKFLOW.md`).
  - Example workflows that show how AI + telemetry + git scripts can create a **smoother, safer development experience**.

Over time, this markdown can grow to include:

- Concrete “stacked session” patterns and examples.
- CI/CD pipeline diagrams and status.
- Telemetry‑driven insights about which workflows actually work best for the community.

---

## 6. Open Questions and Future Enhancements

Some areas we can explore next:

- **Deeper stacked PR support**:
  - Scripted helpers to create/visualize stacks.
  - PR description templates that reference stack ordering.

- **Automatic session branch deletion**:
  - Once a session is merged and pushed, offer to delete the branch locally and remotely.

- **Tighter Cursor integration**:
  - Cursor commands or extensions that:
    - Invoke `start_dev_session`, `resume_dev_session`, and `end_dev_session`.
    - Surface session/feature information in the editor UI.

- **Telemetry‑driven workflow tuning**:
  - Use our own telemetry to:
    - See how often sessions are short vs long.
    - See where merges fail/conflict.
    - See which branches tend to accumulate too many changes — and adjust guidance accordingly.

This document is the place to capture those ideas and decisions as they solidify.

---

## 7. Workflow History / Changelog

This section tracks how the workflow and scripts have evolved over time. It’s intentionally high‑level; see git history for exact diffs.

### v0 – Manual Git, No Session Scripts

- **State**:
  - `main` tracked this fork’s own changes, not strictly upstream.
  - No standardized scripts; ad‑hoc branching and syncing.
- **Pain points**:
  - Hard to keep `main` aligned with upstream.
  - No consistent pattern for starting/ending work sessions.

### v1 – Upstream‑Mirrored `main` and Basic Session Scripts

- **Key changes**:
  - Introduced `sync_upstream.sh`:
    - `main` became a **mirror of `upstream/main`**.
    - Force‑sync supported with safety checks and dry‑run mode.
  - Established `develop` as the fork’s main integration branch.
  - Introduced `start_dev_session.sh` and `end_dev_session.sh`:
    - Session branches named `dev/session-{timestamp}` created from `develop`.
    - `end_dev_session.sh`:
      - Checked for uncommitted changes.
      - Committed and pushed work.
      - Optionally switched back to `develop`.
  - Documented in early versions of `FORK_SYNC_WORKFLOW.md` and `DEV_SESSION_WORKFLOW.md`.

### v2 – Feature‑Aware Sessions and AI‑Assisted End‑of‑Session Flow

- **Key changes (current behavior)**:
  - `start_dev_session.sh`:
    - Still syncs `main` ← `upstream/main` and merges into `develop`.
    - Now accepts an optional **feature name** and optional **session name**:
      - `./scripts/start_dev_session.sh` → session from `develop`.
      - `./scripts/start_dev_session.sh my-feature` → session from `feature/my-feature`.
      - `./scripts/start_dev_session.sh my-feature session-name` → named session from that feature.
    - Creates session branches `dev/session-*` and records the base branch in git config:
      - `branch.dev/session-... .baseBranch = feature/my-feature` or `develop`.
  - `end_dev_session.sh`:
    - Uses `llm` to classify untracked files (junk vs important).
    - Presents junk file options (ignore / leave alone / commit / abort).
    - Shows exactly which files will be committed, then prompts with a sensible default commit message.
    - Determines the correct **base branch** for the session:
      - Uses `branch.<session>.baseBranch` if present.
      - Otherwise infers the closest `feature/*` branch, falling back to `develop`.
    - Merges the session branch into that base branch with an AI‑generated merge message.
    - Leaves you on the base branch (feature or `develop`), not on the temporary session branch.
  - `resume_dev_session.sh`:
    - Lists recent `dev/session-*` branches with commits.
    - Lets you easily resume a session (default: most recent).
  - Documentation:
    - `DEV_SESSION_WORKFLOW.md` updated to describe v2 behavior and usage.
    - `DEV_WORKFLOW_VISION.md` (this file) added to capture the conceptual model and future direction.

### Notes on Backward Compatibility

- Older branches and sessions created under v1:
  - May lack `branch.<session>.baseBranch` config entries.
  - v2 scripts handle this by inferring the base branch from git history and defaulting to `develop`.
- New work should follow the v2 pattern:
  - Use `start_dev_session.sh` with or without a feature name.
  - Let `end_dev_session.sh` decide where the session merges based on the stored/inferred base branch.


---

## 8. Worktrees, Cursor, and Multi‑Workspace Setups

This section describes how our workflow interacts with git worktrees and multi‑window / multi‑workspace usage in tools like Cursor.

### 8.1 Git Worktrees Basics

- Git worktrees allow multiple checked‑out branches of the same repository to exist in different directories at the same time.
- All worktrees share the same `.git` object database but have separate working trees and indexes.
- **Important constraint**: a given branch can only be checked out in one worktree at a time.  
  If `main` or `develop` is already checked out in one worktree, `git checkout main` in another worktree will fail.

### 8.2 Interaction with Our Scripts

- `start_dev_session.sh`:
  - Always runs from the current working directory (`$REPO_ROOT`).
  - Assumes it can:
    - `git checkout main` → sync from upstream.
    - `git checkout develop` → merge from `main`.
  - If `main` or `develop` is already checked out in **another worktree** from the same `.git`, these checkouts can fail.

- `end_dev_session.sh` and `resume_dev_session.sh`:
  - Operate entirely within the current worktree.
  - They don’t directly manage or interact with other worktrees.

### 8.3 Recommended Usage with Cursor and Worktrees

For now, the simplest, least surprising pattern is:

- **Use one primary “session workspace” per clone**:
  - Treat the current clone + directory (where you run the scripts) as the canonical session workspace.
  - Let `start_dev_session.sh` control switching between `main`, `develop`, feature branches, and `dev/session-*` within that workspace.

- **Avoid checking out `main` or `develop` in other worktrees from the same clone**:
  - Doing so can cause `start_dev_session.sh` to fail when it tries to switch back to `main`/`develop`.

- **If you want parallel views of different branches in Cursor**:
  - Prefer using **multiple clones** of the repository rather than multiple worktrees from a single `.git`.
  - Each clone:
    - Has its own `main`/`develop`/feature branches.
    - Can run the session scripts independently without colliding over which branch is checked out where.

In practice, this looks like:

```bash
# Clone 1: primary session workspace
~/projects/bp-telemetry-experimental/
  ./scripts/start_dev_session.sh my-feature
  ./scripts/end_dev_session.sh

# Clone 2: possibly read‑only or for reviewing another branch
~/projects/bp-telemetry-experimental-review/
  git checkout develop
  # Use Cursor here to read/compare without running the session scripts
```

This approach plays well with Cursor’s multi‑window usage:

- Each Cursor window points to a different clone (or the same clone at different times).
- Our scripts run in a predictable environment without cross‑worktree branch checkout conflicts.

### 8.4 Future Worktree‑Aware Enhancements (Not Implemented Yet)

Long‑term, we may want tighter integration with git worktrees, especially for power users:

- A “session worktree manager” script that:
  - Creates a dedicated worktree per session branch under a known directory (e.g., `.worktrees/dev/session-*`).
  - Optionally prints instructions or triggers an editor open (e.g., Cursor) in that worktree.

- Worktree‑aware merge logic:
  - Detect that the base branch for a session lives in another worktree and run merges in that worktree’s directory.

These are deliberately not implemented yet; for now we prefer to keep the behavior simple and robust with a single “session workspace” per clone. This section is here to capture how worktrees fit into the *vision* so we can revisit as Cursor 2.x and our own habits evolve.

