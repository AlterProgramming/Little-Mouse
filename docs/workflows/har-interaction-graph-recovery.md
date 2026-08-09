# HAR interaction-graph recovery workflow

Use this workflow when a browser HAR contains captured relationship-bearing activity and the required output is a **graph network**, not a flat account list.

This is a **computer-use** workflow under the Little Mouse two-capability model. It reads only captured response bodies and does not replay requests.

## Current relationship source

The first extractor recognizes Instagram Bloks activity-center comment records containing both:

- `comment_author_username`
- `post_author_username`

Each unique captured comment becomes relationship evidence from the comment author to the post author. Repeated interactions are aggregated into a weighted directed edge of type `commented_on_post_by`.

The workflow intentionally does **not** treat a follower/following array by itself as proof that a graph network was obtained.

## Default privacy boundary

The default graph is pseudonymized. It preserves:

- node topology;
- directed edges;
- edge type;
- aggregate interaction weight;
- capture-entry evidence range;
- weak-component statistics.

It does not emit usernames, user IDs, comment text, post text, cookies, tokens, or request secrets.

Identity-bearing graph labels are a separate action and require an agent-owned agreement that explicitly declares `extract_captured_interaction_graph_identities`.

## Command

```bash
python tools/extract_har_interaction_graph.py capture.har \
  --require-network \
  -o graph.json
```

`--require-network` makes the validation boundary executable: the command exits nonzero unless the capture yields at least two nodes and one relationship edge.

## Output contract

The graph JSON reports:

- `representation: directed_weighted_graph`;
- `relation_types`;
- `node_count`;
- `edge_count`;
- `interaction_evidence_count`;
- `weak_component_count`;
- `largest_weak_component_nodes`;
- `network_obtained`;
- pseudonymized `nodes`;
- typed weighted `edges`.

## Validation criteria

A valid result must obtain graph structure from captured relationship evidence:

1. `node_count >= 2`;
2. `edge_count >= 1`;
3. every edge has a declared relationship type and direction;
4. `network_obtained == true`;
5. a flat follower/following list without relationship-edge evidence does not satisfy the criterion;
6. the default output contains no identity labels or content text.

The validation is structural. It does not claim that the graph is a complete social graph, only that a real interaction network was reconstructed from evidence present in the capture.
