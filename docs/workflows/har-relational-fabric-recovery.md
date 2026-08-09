# HAR relational-fabric recovery workflow

Use this workflow when a browser HAR contains relationship-bearing interaction records and the goal is to preserve more of the underlying entity/edge structure before choosing a product-style projection.

The first adapter builds on Instagram activity-center comment records. Instead of reducing each observation immediately to `commenter -> post author`, it keeps the media object and emits several simultaneous edge types.

## Output model

The recovered graph is a heterogeneous multigraph with two current node types:

- `person`
- `media`

and four current relationship types:

- `commented_on_media`: person -> media
- `authored_media`: person -> media
- `commented_on_post_by`: commenter -> post author
- `co_commented_on_media`: undirected commenter <-> commenter projection when both appear on the same captured media object

This deliberately preserves both the content-centered path and the person-to-person projection. Future adapters can add other primitive entities and edges without replacing these observations.

## Co-engagement semantics

`co_commented_on_media` means only that two captured commenters appeared on at least one of the same media objects.

The edge exposes:

- `shared_media_count`: number of distinct captured media objects shared by the pair;
- `shared_capture_batch_count`: number of HAR response entries in which both commenters were observed together for the same media object.

A capture batch is **not a timestamp**. It is evidence that the records were delivered together in the browser capture.

## Inference boundary

The base relational-fabric extractor intentionally does not turn coarse UI time labels or capture batches into synchronized-viewing claims. The newer [world-fabric workflow](har-world-fabric-recovery.md) can preserve displayed relative-time buckets as additional evidence while still keeping exact timestamps, synchronization, shared recommendation delivery, and algorithmic causality unclaimed.

## Command

```bash
python tools/extract_har_relational_fabric.py capture.har \
  --require-fabric \
  -o fabric.json
```

The default output pseudonymizes both people and media IDs.

Identity-bearing output is separately gated:

```bash
python tools/extract_har_relational_fabric.py capture.har \
  --include-identities \
  --agreement agreement.json
```

The agreement must explicitly declare `extract_captured_relational_fabric_identities`.

## Validation criteria

A valid run should:

- preserve media nodes instead of collapsing the whole observation into person-to-person edges;
- produce multiple typed edge families from the same captured evidence;
- produce co-engagement edges only from distinct commenters sharing captured media;
- distinguish shared-media evidence from same-capture-batch evidence;
- emit no usernames, user IDs, media IDs, comment/post text, cookies, or tokens by default;
- make no synchronized-viewing, shared-ranking, or algorithmic-causality claim without stronger evidence.
