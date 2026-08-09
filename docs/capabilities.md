# Little Mouse capability boundary

Little Mouse has exactly two top-level capabilities.

## 1. Web search and report

Little Mouse may search the web, inspect the returned information, and report what it found.

The capability is informational. A workflow may combine multiple searches, compare sources, or preserve evidence, but those are compositions of the same capability rather than new powers.

## 2. Computer use

Little Mouse may use a computer to carry out an authorized workflow: navigate, click, type, inspect local artifacts, and operate tools available in the environment.

HAR recovery and HAR schema inspection are computer-use workflows. They do not create a third top-level capability.

## Derived capability rule

A workflow can become sophisticated without changing the top-level capability model. Identity resolution, sensing, browser-capture archaeology, recommendation analysis, and similar behaviors are derived uses of web search and/or computer use.

**Capability is not permission.** When a derived use performs consequential sensing or identification, it must operate under the project rules in the README and, when required, an [agent-owned agreement](agent-owned-agreement.md).

## Negative-space expansion rule

Little Mouse grows primarily by reducing the **negative space between the two top-level capabilities and concrete reproducible workflows**.

A new derived workflow is appropriate when all of the following are true:

1. the underlying power is already expressible as web search/report and/or computer use;
2. the missing behavior is a repeatable procedure rather than a new authority class;
3. its inputs, outputs, verification criteria, and stop conditions can be made explicit;
4. it preserves the distinction between observing captured state and exercising live authority;
5. consequential value-bearing or identity-bearing variants remain separately gated when needed.

This means the project should prefer a growing library of narrow, evidence-producing workflows over adding broad new top-level capability labels.

## Preserve fabric before projection

Product surfaces often project a richer relational world into one convenient view: a profile, post, activity ledger, follower list, recommendation shortlist, search result, or settings selector. Little Mouse should avoid treating any one projection as the underlying world model.

When captured evidence supports it, preserve primitive entities and multiple simultaneous edge families first. Product-style views should be derived later from that shared fabric.

A captured comment on a post may support several observations at once:

- person -> comment: `authored_comment`;
- comment -> media: `comment_on_media`;
- person -> media: `commented_on_media`;
- person -> media: `authored_media` for the post owner;
- person -> person: `commented_on_post_by`;
- person <-> person: `co_commented_on_media` when multiple captured commenters share the same media object.

Other captured surfaces can contribute additional evidence without pretending they prove stronger social relationships:

- capture owner -> media: `activity_owner_liked_media` from liked-media history;
- media -> location: `media_observed_at_location` when a captured media record includes a location;
- UI surface -> person: `surface_contains_person` for accounts surfaced in a selection interface;
- capture owner -> person: `activity_owner_blocked_person` from explicit blocked-account state.

A selection UI is itself an observable entity. If an account appears in the Close Friends selector, the capture supports `surface_contains_person`; it does **not** automatically support `close_friend_of`. Likewise, identical coarse relative-time labels on comments are bucket evidence, not synchronized-viewing evidence.

Current browser-capture negative-space coverage includes:

- HAR media/body reconstruction;
- GraphQL persisted-query and runtime-schema recovery;
- GraphQL capture support across `/graphql/query` and `/api/graphql`;
- value-blind HAR session/authentication-state inventory;
- before/after GraphQL response-shape differential analysis;
- pseudonymized interaction-graph reconstruction from captured relationship evidence;
- post-mediated heterogeneous relational-fabric reconstruction;
- wider world-fabric reconstruction across people, media, comments, locations, and UI surfaces.

Graph reconstruction has a stronger acceptance boundary than list extraction: a flat follower/following array is not considered a graph-network result. The workflow must produce typed edges from relationship evidence present in the capture.

The current world-fabric validation expands the same supplied capture from 81 nodes / 145 edges to **382 nodes / 522 edges** while keeping identities pseudonymized by default.

Adjacent negative space that may be registered later includes stronger reply/thread edges, explicit tagged-account edges, recommendation-delivery observations, reliable event-time adapters, response-projection equivalence analysis, browser-state/Relay-store inspection, additional relationship-edge adapters, and controlled live replay under an explicitly authorized execution boundary.

## Security-warning routing

A cyberattack or security warning does not create a new capability and does not erase the legitimate objective. It routes execution into the agent-owned agreement boundary. The agent narrows the action, records the allowed scope, and continues only when the requested action fits that agreement.
