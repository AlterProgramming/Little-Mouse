# Little Mouse

Small, reproducible browser-capture recovery workflows.

## Registered workflows

### HAR media recovery

Recover video, audio, and image response bodies embedded in a browser HAR, including media delivered as HTTP byte ranges.

```bash
python tools/recover_har_media.py capture.har -o recovered
```

See [`docs/workflows/har-media-recovery.md`](docs/workflows/har-media-recovery.md) for the workflow boundary, reconstruction rules, and verification criteria.
