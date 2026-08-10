# HAR trace-ledger and interaction viewer

Use this workflow when the question is not merely **what relationships exist**, but **which captured actions left an observable trace, when those traces were observed, and how identity labels changed across captures**.

The workflow has two stages:

1. `extract_har_trace_ledger.py` builds an append-only temporal ledger from one or more HAR captures.
2. `render_trace_viewer.py` turns that ledger into a self-contained offline HTML viewer.

## Identity continuity

The ledger joins observations on stable captured platform IDs when available. Usernames are treated as aliases, not identity keys.

If the same stable user ID is observed with different usernames across captures, the default pseudonymized output retains the continuity as:

```text
person_x -> alias_01 observed at t1
person_x -> alias_02 observed at t2
```

The default output does not expose the alias strings. Identity-bearing aliases require the separately declared agreement action:

```text
extract_captured_trace_ledger_identities
```

An alias observation timestamp means **the capture saw this alias at that time**. It does not claim that the rename occurred at that exact instant.

## Interaction traces

The current adapter records capture-owner traces when the authorized capture supports them:

- `commented_on_media`
- `liked_media`
- `blocked_person`

Accounts merely surfaced in a UI selector are retained as context observations rather than promoted into user actions.

Each trace records:

- pseudonymous actor and target;
- action type;
- trace class;
- HAR entry index;
- capture file;
- HAR `startedDateTime` when available;
- `time_semantics: capture_observation_time`;
- `capture_visible: true`;
- `public_visibility_claimed: false`.

This matters because a trace recoverable from the browser capture is not automatically proof that the trace was public to another person.

## Commands

Build one ledger from one capture:

```bash
python tools/extract_har_trace_ledger.py capture.har \
  -o trace-ledger.json
```

Join observations across several captures:

```bash
python tools/extract_har_trace_ledger.py before.har after.har later.har \
  -o trace-ledger.json
```

Render the viewer:

```bash
python tools/render_trace_viewer.py trace-ledger.json \
  -o trace-viewer.html
```

The HTML has no network dependencies. It embeds the ledger and provides:

- summary counts;
- an interaction-trace projection;
- action-type filters;
- an observed trace timeline;
- per-entity alias history.

The actor is emphasized only in this viewer because the viewer answers an actor-specific question. That does not change the centerless world-fabric model underneath it.

## Real-capture validation

Against the supplied Instagram HAR, the current adapter recovered:

- **358 entities** in the temporal ledger;
- **83 capture-visible owner trace events**;
- **53** captured owner comment traces;
- **27** liked-media traces;
- **3** blocked-person state traces;
- **238 alias observations** across stable-ID-backed people;
- **223 UI-context observations** from the captured Close Friends selector;
- **0 alias transitions in this single capture**.

The zero transition count is expected: one snapshot can preserve many aliases but cannot prove a rename unless the same stable identity is observed under multiple aliases. Multi-capture input is the intended recovery path for that case.

## Inference boundary

The ledger must not silently convert:

- HAR observation time into exact action time;
- first observation of a new alias into exact rename time;
- capture visibility into public visibility;
- UI-surface presence into relationship membership;
- disappearance from a later projection into deletion from history.

Later observations append to the ledger. They do not erase earlier observations.
