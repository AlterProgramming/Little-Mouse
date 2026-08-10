# HAR frontier manifest

## Purpose

Turn identifiers already recovered from one or more authorized HAR captures into an explicit **expansion frontier** that can be consumed by later web-search or computer-use workflows.

This workflow closes the gap between a finite capture fabric and iterative observation. The HAR is the seed, not the permanent boundary; however, provenance must remain visible so newly observed public evidence is never rewritten as if it existed in the original capture.

## Command

```bash
python tools/extract_har_frontier_manifest.py capture.har \
  --target-nodes 10000 \
  -o frontier.json
```

The default output is pseudonymous. It reports which captured entities have resolvable frontier shape without emitting usernames, stable platform IDs, shortcodes, or public locator URLs.

Identity-bearing resolvers are separately gated:

```bash
python tools/extract_har_frontier_manifest.py capture.har \
  --target-nodes 10000 \
  --include-identities \
  --agreement agreement.json \
  -o frontier-identities.json
```

The agreement must declare `extract_captured_frontier_manifest_identities`.

## What is preserved

The manifest recovers and joins, when present:

- stable Instagram user IDs;
- observed usernames as aliases rather than identity keys;
- media IDs;
- media shortcodes / media codes;
- comment IDs;
- capture name, HAR entry index, and browser observation time;
- captured relationship families such as `authored_comment`, `comment_on_media`, `commented_on_media`, `authored_media`, and `commented_on_post_by`.

The extractor also scans captured response maps for media IDs/codes beyond the liked-media screen, so media discovered through comment/post payloads can become resolvable frontier objects.

## Frontier semantics

A frontier item means: **this captured entity has enough locator material to attempt a later public observation**.

For identity-bearing output, current locators include:

- `instagram_profile` from an observed username;
- `instagram_media` from an observed media shortcode.

A locator does not prove that the target is still public, still exists, or still has the same visible state. It is only a resolver seed.

Frontier priority is currently based on captured graph degree. That is an expansion heuristic, **not** a claim of friendship, social closeness, recommendation rank, or intent.

## Iterative expansion model

The intended loop is:

```text
captured fabric
  -> enumerate every exposed frontier
  -> observe authorized/public frontier objects
  -> append newly observed entities and edges with source/time provenance
  -> merge stable identifiers and aliases
  -> discover new frontiers
  -> repeat until a stop condition fires
```

This preserves the centerless architecture: no ego node is required. A viewer may choose a temporary navigation center, but the expansion plan itself operates over all open boundaries.

## Node targets are budgets, not promises

`--target-nodes 10000` is a resource/coverage budget. The tool never invents nodes to reach it.

The manifest records:

- current captured node count;
- open frontier count;
- nodes remaining to the requested budget;
- `target_is_budget_not_promise: true`.

Expansion stops when any of these occurs:

- target node budget reached;
- no open frontier remains;
- authorization boundary reached;
- resource or rate cap reached;
- source is no longer publicly observable.

## Provenance rule

Edges recovered from the HAR are `captured` evidence. Later web/computer observations must be appended as `newly_observed` evidence with their own timestamp and source.

A later absence must not delete historical capture evidence. Likewise, a newly observed alias does not rewrite older alias observations.

## Safety and permission boundary

Capability is not permission. The identity-bearing frontier manifest only exposes identifiers already present in authorized captures and only under the declared agreement action. The workflow does not replay authenticated requests, export session secrets, bypass access controls, or silently widen to unrelated targets.

A future live-expansion executor must enforce its own authorization, resource/rate limits, retention policy, and stop conditions; the manifest alone does not authorize live collection.
