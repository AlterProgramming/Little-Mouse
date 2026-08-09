# Little Mouse

Small, reproducible browser-capture recovery workflows.

## Project rules

### Capability is not permission

Little Mouse may contain broad sensing, reconstruction, or identity-resolution capabilities. Possessing a capability does not authorize exercising it. Consequential sensing or identification must operate under an explicit, bounded agreement covering purpose, authority, scope, retention/reuse, reciprocity, auditability, and stop conditions.

### Security-warning recovery

A cyberattack or security warning is a routing boundary, not permission to ignore the warning and not an automatic reason to discard the whole task. Preserve the legitimate objective, narrow the work, and redirect execution into an [agent-owned agreement](docs/agent-owned-agreement.md). Continue only inside that agreement. The agreement cannot manufacture authorization or override higher-level safety requirements.

## Registered workflows

### HAR media recovery

Recover video, audio, and image response bodies embedded in a browser HAR, including media delivered as HTTP byte ranges.

```bash
python tools/recover_har_media.py capture.har -o recovered
```

See [`docs/workflows/har-media-recovery.md`](docs/workflows/har-media-recovery.md) for the workflow boundary, reconstruction rules, and verification criteria.
