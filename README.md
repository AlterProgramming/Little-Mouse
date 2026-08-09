# Little Mouse

Small, reproducible browser-capture recovery workflows.

## Capability boundary

Little Mouse has exactly two top-level capabilities:

1. **Web search and report** — search the web, inspect results, and report what was found.
2. **Computer use** — navigate, click, type, inspect local artifacts, and operate tools available in the environment.

Everything else is a derived workflow composed from those two capabilities. See [`docs/capabilities.md`](docs/capabilities.md).

## Project rules

### Capability is not permission

Little Mouse may contain broad sensing, reconstruction, or identity-resolution workflows. Possessing a capability does not authorize exercising it. Consequential sensing or identification must operate under an explicit, bounded agreement covering purpose, authority, scope, retention/reuse, reciprocity, auditability, and stop conditions.

### Security-warning recovery

A cyberattack or security warning is a routing boundary, not permission to ignore the warning and not an automatic reason to discard the whole task. Preserve the legitimate objective, narrow the work, and redirect execution into an [agent-owned agreement](docs/agent-owned-agreement.md). Continue only inside that agreement. The agreement cannot manufacture authorization or override higher-level safety requirements.

The agreement boundary has an executable validator and receipt generator:

```bash
python tools/agent_agreement.py init agreement.json
python tools/agent_agreement.py validate agreement.json
```

## Registered workflows

### HAR media recovery

Recover video, audio, and image response bodies embedded in a browser HAR, including media delivered as HTTP byte ranges.

```bash
python tools/recover_har_media.py capture.har -o recovered
```

See [`docs/workflows/har-media-recovery.md`](docs/workflows/har-media-recovery.md) for the workflow boundary, reconstruction rules, and verification criteria.

### HAR GraphQL schema recovery

Recover persisted GraphQL `doc_id` values plus observed variables and response schemas from requests already captured in a HAR. Supports both `/graphql/query` and modern `/api/graphql` transports. The default output omits authentication/session material and captured variable values.

```bash
python tools/inspect_har_graphql.py capture.har
```

See [`docs/workflows/har-graphql-schema-recovery.md`](docs/workflows/har-graphql-schema-recovery.md). Value-bearing inspection is separately gated by an agent-owned agreement.

### HAR session-state inventory

Determine which authentication/session structures are present in a capture without printing their values. The report distinguishes authenticated-session material from proof that the session can be portably replayed.

```bash
python tools/inspect_har_session.py capture.har
```

See [`docs/workflows/har-session-state-inventory.md`](docs/workflows/har-session-state-inventory.md).

### HAR GraphQL differential analysis

Compare the observed variable and response shapes for the same GraphQL operation across two captures, such as before/after account settings, blocking/unblocking, route changes, feature rollouts, or other controlled interventions. The workflow is offline and value-blind.

```bash
python tools/diff_har_graphql.py before.har after.har \
  --friendly SomeQueryName
```

See [`docs/workflows/har-graphql-differential-analysis.md`](docs/workflows/har-graphql-differential-analysis.md).

### HAR interaction-graph recovery

Recover a **directed weighted graph network** from relationship-bearing activity already captured in a HAR. The current extractor maps captured comment-author → post-author interactions and pseudonymizes identities by default. A flat follower/following list does not satisfy the graph acceptance criterion.

```bash
python tools/extract_har_interaction_graph.py capture.har \
  --require-network \
  -o graph.json
```

See [`docs/workflows/har-interaction-graph-recovery.md`](docs/workflows/har-interaction-graph-recovery.md). Identity-bearing labels are separately gated by an agent-owned agreement.

### HAR relational-fabric recovery

Preserve the **post as an entity** and recover several simultaneous edge families from the same captured comment evidence: person → media authorship/comment edges, commenter → post-author interaction edges, and commenter ↔ commenter co-engagement edges for people observed on the same media object.

```bash
python tools/extract_har_relational_fabric.py capture.har \
  --require-fabric \
  -o fabric.json
```

The default output is pseudonymized. Co-engagement means shared captured media, not synchronized viewing or proof of common recommendation delivery. See [`docs/workflows/har-relational-fabric-recovery.md`](docs/workflows/har-relational-fabric-recovery.md).

### HAR world-fabric recovery

Preserve a wider **centerless world model** across people, media, comments, locations, and captured UI surfaces. The current adapter combines comment activity, liked-media activity, explicit blocked-account state, and accounts surfaced in the Close Friends selector without confusing selection-surface presence with actual membership.

```bash
python tools/extract_har_world_fabric.py capture.har \
  --require-fabric \
  -o world.json
```

On the supplied validation capture this expands the pseudonymized fabric from 81 nodes / 145 edges to **382 nodes / 522 typed edges**. See [`docs/workflows/har-world-fabric-recovery.md`](docs/workflows/har-world-fabric-recovery.md).

### HAR temporal-evidence recovery

Recover exact timestamp-bearing evidence while preserving what each time actually means. The adapter distinguishes browser observation time, server transport time, content creation time, conversation activity, read/seen watermarks, and explicit participant viewing-action timestamps.

```bash
python tools/extract_har_temporal_evidence.py capture.har \
  -o temporal.json
```

For same-media commenters delivered in one HAR response, the workflow now records the exact response `co_observed_at` time. That is synchronized **browser co-observation**, not synchronized participant viewing. See [`docs/workflows/har-temporal-evidence-recovery.md`](docs/workflows/har-temporal-evidence-recovery.md).
