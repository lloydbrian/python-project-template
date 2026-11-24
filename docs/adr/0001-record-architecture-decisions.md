# ADR 0001: Record architecture decisions

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-23 |
| **Decided by** | LBD (template owner) |
## Context
The template encodes many choices (tools, thresholds, security controls). Without a record, each new developer has to re-derive why things are as they are, and good decisions get reverted by accident.

## Decision
Record every significant decision as a short Architecture Decision Record in `docs/adr/`, numbered, using this format: context, decision, alternatives considered, consequences. Generated projects get their own `docs/adr/` for project-level decisions.

## Consequences
- A change that reverses a decision must add a new ADR that supersedes the old one, not edit it silently.
- The READMEs link here instead of repeating long justifications.
