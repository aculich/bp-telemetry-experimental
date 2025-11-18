<!--
Copyright © 2025 Sierra Labs LLC
SPDX-License-Identifier: AGPL-3.0-only
License-Filename: LICENSE
-->

## Architecture Decision Records (ADRs)

> Lightweight, versioned records of important architecture decisions.

### What is an ADR?

An **Architecture Decision Record (ADR)** is a short document that captures a **single, significant technical decision** and its context.  
Each ADR answers four main questions:

- **Context**: What problem are we solving? What constraints or background matter?
- **Decision**: What did we choose, concretely?
- **Rationale**: Why this option over the alternatives?
- **Consequences**: What tradeoffs did we accept (positive and negative)?

ADRs are intentionally **small and focused**. They are not full design docs; think of them as an append-only log of “why we did it this way.”

### Why we use ADRs in Blueplane

- **Shared memory**: Future contributors can see *why* decisions were made, not just *what* the code does.
- **Change tracking**: When we revisit a decision, we can explicitly supersede an older ADR rather than silently drifting.
- **Scope clarity**: Each ADR is about **one decision**, which keeps discussions concrete and limited in blast radius.
- **Asynchronous communication**: ADRs are easy to review, link in issues/PRs, and reference in Slack.

Example in this repo:

- `0001-database-stack-sqlite-and-optional-duckdb.md` documents the choice to keep **SQLite** as the primary datastore and treat **DuckDB** as an optional analytical sink behind a feature flag.

### How ADRs are organized

- Location: `docs/adr/`
- Naming convention: `NNNN-short-title.md`, where:
  - `NNNN` is a zero-padded sequence number (`0001`, `0002`, …).
  - `short-title` is a kebab-case summary of the decision (e.g. `database-stack-sqlite-and-optional-duckdb`).
- Each ADR file should include:
  - **Status** (proposed, accepted, superseded, deprecated).
  - **Date**.
  - The four key sections: Context, Decision, Rationale, Consequences.
 - A reusable template is provided in `0000-template.md`.

### How to add a new ADR

1. **Pick the scope**
   - Choose one clear decision (e.g. “Where do we store embeddings?”, “How do we handle health monitoring?”).
2. **Create a new file**
   - Duplicate the template `docs/adr/0000-template.md` and rename it with the next sequence number, for example:
     - `cp docs/adr/0000-template.md docs/adr/0002-your-decision-title.md`
3. **Fill in the sections**
   - Keep it concise (1–2 screens of text is usually enough).
   - Link to supporting design docs or issues if needed.
4. **Reference it**
   - Link the ADR from relevant docs (`ARCHITECTURE.md`, feature docs) and from any GitHub issues/PRs that implement the decision.
5. **Evolve via new ADRs**
   - If you later change your mind, write a **new** ADR that explicitly says it *supersedes* an older one, rather than editing history.

### When to write an ADR vs a design doc

- **Use an ADR** when:
  - You are choosing between a few concrete options (e.g. SQLite vs DuckDB, feature flags vs config files).
  - The decision will be long-lived or hard to change later.
- **Use a design doc (under `docs/architecture/` or similar)** when:
  - You need to explain a whole subsystem, protocol, or workflow in detail.
  - You expect substantial iteration or research before deciding.

In practice, a larger design doc can link to **one or more ADRs** that capture its key, irreversible decisions.


