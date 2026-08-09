# Little Mouse

Small, reproducible browser-capture recovery workflows.

## Capability boundary

Little Mouse has exactly two top-level capabilities:

1. **Web search and report** — search the web, inspect results, and report what was found.
2. **Computer use** — navigate, click, type, inspect local artifacts, and operate tools available in the environment.

Everything else is a derived workflow composed from those two capabilities. See [`docs/capabilities.md`](docs/capabilities.md) and the machine-readable [`capabilities/registry.json`](capabilities/registry.json).

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

Compare the observed variable and response shapes for the same GraphQL operation across two captures, such as before/after a controlled setting or relationship-state change. The workflow is offline and value-blind.

```bash
python tools/diff_har_graphql.py before.har after.har \
  --friendly SomeQueryName
```

See [`docs/workflows/har-graphql-differential-analysis.md`](docs/workflows/har-graphql-differential-analysis.md).

### HAR recommendation batch extraction

Recover candidate batches, observed rank order, and the presence of ranking-context fields from recommendation responses already captured in a HAR. The default report replaces candidate identities with stable fingerprints and does not emit `social_context` or `display_reason` values.

```bash
python tools/extract_har_recommendations.py capture.har
```

See [`docs/workflows/har-recommendation-batch-extraction.md`](docs/workflows/har-recommendation-batch-extraction.md). Raw captured candidate/context values require a separately declared agreement action.

### HAR GraphQL projection-equivalence analysis

Group captured GraphQL operations by a stable fingerprint of their target selector and compare shared versus projection-specific response field paths. This makes it possible to distinguish rich-profile, hover-card, badge, note, highlight, and recommendation projections without exposing the raw target selector value.

```bash
python tools/analyze_har_projections.py capture.har
```

See [`docs/workflows/har-graphql-projection-equivalence.md`](docs/workflows/har-graphql-projection-equivalence.md).
