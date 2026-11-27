# ADR 0004. Portal history and explainable placement

**Status** Proposed in P1.1.

## Context

Teams need to review deployment impact, trace changes to a requester and understand placement. Existing GitHub history records merged configuration and the current ILP uses static scenario data. An App-authored PR cannot carry the full picture of actor authentication, denied requests or runtime status.

## Decision

Keep the Flask application a modular monolith. Use GitHub and Argo CD read evidence to reconstruct deployed revision history, with authenticated service RBAC, a request correlation ID and structured audit events. Start with a reviewed retained audit sink when its integrity meets requirements. Decide on a database only if durable events or idempotency cannot be guaranteed by the chosen sinks and GitHub contract. Keep the optimizer a versioned, snapshot-driven recommender. Git review owns configured constraints and the Kubernetes Scheduler binds Pods. [Portal and optimizer design](../ARCHITECTURE.md)

## Alternatives and consequences

A local SQLite ledger can support a demonstrated single-instance lab transactional need if storage and recovery are accepted. A shared data store becomes a separate decision when multi-replica writes, audit retention or consistency require it. Starting with microservices or a new managed database adds access and recovery responsibilities without evidence of current need. Direct cluster writes or a custom scheduler would bypass the existing review and runtime ownership boundaries.
