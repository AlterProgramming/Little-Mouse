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

The machine-readable inventory of currently registered derived workflows is [`../capabilities/registry.json`](../capabilities/registry.json).

## Negative-space expansion rule

Little Mouse grows primarily by reducing the **negative space between the two top-level capabilities and concrete reproducible workflows**.

A new derived workflow is appropriate when all of the following are true:

1. the underlying power is already expressible as web search/report and/or computer use;
2. the missing behavior is a repeatable procedure rather than a new authority class;
3. its inputs, outputs, verification criteria, and stop conditions can be made explicit;
4. it preserves the distinction between observing captured state and exercising live authority;
5. consequential value-bearing or identity-bearing variants remain separately gated when needed.

This means the project should prefer a growing library of narrow, evidence-producing workflows over adding broad new top-level capability labels.

Current browser-capture negative-space coverage includes:

- HAR media/body reconstruction;
- GraphQL persisted-query and runtime-schema recovery;
- GraphQL capture support across `/graphql/query` and `/api/graphql`;
- value-blind HAR session/authentication-state inventory;
- before/after GraphQL response-shape differential analysis;
- recommendation-batch extraction with pseudonymous candidates by default;
- response-projection equivalence analysis using hashed target selectors.

The next adjacent negative space is intentionally smaller now:

- browser-state / Relay-store inspection of data already delivered to the local page;
- controlled live replay, but only under a separately authorized execution boundary with request/target confinement and audit receipts.

## Evidence classes

Derived browser-capture workflows should distinguish these evidence classes rather than collapsing them:

- **executed capture evidence** — a request/response actually exists in the HAR;
- **multi-target executed evidence** — the same operation is observed against multiple target selectors;
- **declared route/template evidence** — a client route definition exposes a generic request shape without proving execution;
- **local browser-state evidence** — data exists in Relay/React/browser state but may not correspond one-to-one with a network request;
- **live execution evidence** — a request is actively sent under current authorization; this is outside the default offline HAR-analysis boundary.

Projection equivalence and recommendation extraction operate only on executed capture evidence. They do not promote route templates or inferred fields into observed response truth.

## Security-warning routing

A cyberattack or security warning does not create a new capability and does not erase the legitimate objective. It routes execution into the agent-owned agreement boundary. The agent narrows the action, records the allowed scope, and continues only when the requested action fits that agreement.
