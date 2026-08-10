# Temporal evidence promotion

This workflow promotes evidence only when a later capture adds information. It does not reinterpret a single watermark as an exact action.

## Current evidence floor

The capture corpus already establishes exact browser observation times for same-response co-observation, server request/flush timestamps, conversation activity timestamps, read-through watermarks, story seen-through watermarks, and content creation timestamps. Those remain distinct semantic classes.

## Promotion ladder

1. `typed_timestamp` — normalized time with known field semantics.
2. `watermark` — actor/state has progressed through a timeline position.
3. `bounded_action_interval` — the same subject's watermark advances between two capture observations. The transition occurred after the earlier observation and no later than the later observation, but its exact event time and action semantics remain unknown.
4. `direct_media_action` — requires an explicit participant-action timestamp joined to the relevant participant and media/object.
5. `temporal_co_action` — requires two independent direct actions on the same object; retains `delta_ms`.
6. `synchronized_viewing_evidence` — only eligible when both direct actions have viewing semantics and the declared synchronization threshold is met.

## Reversibility

Promotions retain parent capture indices and source fingerprints. A non-monotonic watermark is emitted as a contradiction instead of being silently repaired. Derived intervals are therefore reproducible and reversible.

## New-capture rule

A new HAR is useful even when it contains no new timestamp field. If it repeats the same semantic watermark for the same pseudonymized subject, Little Mouse compares it with prior captures:

- unchanged state -> no action inferred;
- monotonic advance -> bounded interval emitted;
- regression -> contradiction emitted;
- explicit participant action field -> eligible for direct-action classification.

Exact HAR `startedDateTime` values provide the observation bounds. They remain observation times, not participant event times.

## CLI

First extract typed evidence from each HAR:

```bash
python tools/extract_har_temporal_evidence.py capture-1.har -o temporal-1.json
python tools/extract_har_temporal_evidence.py capture-2.har -o temporal-2.json
```

Then promote across captures in chronological order:

```bash
python tools/promote_temporal_evidence.py temporal-1.json temporal-2.json -o promoted.json
```

The output never claims synchronized viewing from watermarks or co-observation alone.
