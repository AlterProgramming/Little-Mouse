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

Recover persisted GraphQL `doc_id` values plus observed variables and response schemas from requests already captured in a HAR. The default output omits authentication/session material and captured variable values.

```bash
python tools/inspect_har_graphql.py capture.har
```

See [`docs/workflows/har-graphql-schema-recovery.md`](docs/workflows/har-graphql-schema-recovery.md). Value-bearing inspection is separately gated by an agent-owned agreement.
