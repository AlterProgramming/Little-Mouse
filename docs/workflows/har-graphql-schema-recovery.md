# HAR GraphQL schema recovery workflow

Use this workflow when a browser HAR already contains GraphQL requests and responses and the task is to recover the observed persisted-query identifier, variables shape, or response shape.

This is a **computer-use** workflow under the Little Mouse two-capability model. It does not add a new top-level capability.

## Boundary

The workflow reads only data already present in the HAR. It does not replay requests, reuse cookies, export authentication/session headers, bypass access controls, or depend on the captured session still being valid.

The output describes **observed runtime shapes**, not the server's authoritative GraphQL type declarations. Optional and union-like shapes are inferred only from values actually present in the capture.

## Supported captured endpoints

Little Mouse recognizes both observed GraphQL transport forms:

- `/graphql/query`
- `/api/graphql`

The second form is important for modern Meta/Comet captures that submit persisted GraphQL operations directly to `/api/graphql`.

## Default output

For each captured GraphQL request, the tool reports:

- HAR entry index and timestamp;
- request method and endpoint path;
- `fb_api_req_friendly_name` when present;
- persisted-query `doc_id` when present;
- the observed variables schema;
- the observed response schema.

Raw request headers, cookies, CSRF values, authorization material, and response values are not emitted.

## Command

```bash
python tools/inspect_har_graphql.py capture.har
```

Filter by friendly name:

```bash
python tools/inspect_har_graphql.py capture.har --friendly SomeQueryName
```

Filter by persisted query ID:

```bash
python tools/inspect_har_graphql.py capture.har --doc-id 1234567890
```

Search the extracted metadata/schema for a term:

```bash
python tools/inspect_har_graphql.py capture.har --contains follower
```

## Value-bearing inspection

Observed GraphQL variable **values** are intentionally a separate action. They are emitted only when an agent-owned agreement explicitly declares `inspect_captured_graphql_values`:

```bash
python tools/inspect_har_graphql.py capture.har \
  --include-values \
  --agreement agreement.json
```

Create a starter agreement with:

```bash
python tools/agent_agreement.py init agreement.json
```

The starter allows schema and session-shape inspection only. Add `inspect_captured_graphql_values` to `allowed_actions` deliberately if the authorized objective requires captured values, then validate the agreement before use.

## Verification

A valid run should:

- inspect only HAR entries whose request path contains `/graphql/query` or `/api/graphql`;
- recover `doc_id` and variables only from captured request parameters;
- construct response shape only from embedded response JSON;
- emit no authentication headers or cookies;
- fail closed when `--include-values` is requested without an agreement that declares the corresponding action.
