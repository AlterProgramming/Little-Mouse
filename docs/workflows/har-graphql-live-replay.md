# HAR GraphQL live replay

`tools/replay_har_graphql.py` bridges Little Mouse's offline GraphQL analysis into a deliberately bounded live verification path.

The workflow reuses browser-session material already present in an authorized HAR, keeps that material in memory, and replays one captured Instagram GraphQL request after substituting only a target identifier that was itself observed in the authorized HAR corpus.

## Boundary

Live replay is narrower than the offline capability map:

- destination must remain HTTPS on `instagram.com` / `*.instagram.com`;
- request path must remain `/graphql/query` or `/api/graphql`;
- the operation must already exist in the selected capture;
- the replacement target must already occur as a target selector in one of the authorized HARs;
- an agreement must explicitly declare `replay_captured_graphql_with_observed_target`;
- cookies, CSRF/session headers, raw target identifiers, and returned response values are never emitted by the tool;
- output contains transport status and response field paths/classes only.

The default starter agreement remains offline-only. Live replay therefore requires a deliberate task-specific agreement rather than silently broadening existing capture analysis.

## Why the HAR can be enough

A browser HAR commonly preserves the request URL, form body, request headers, and either a `Cookie` header or structured cookies. For a still-valid captured session, those fields may be sufficient to reproduce the same authenticated request. Session expiry, anti-replay checks, changed persisted-query identifiers, or other server-side controls can still cause a replay to fail.

## Enumerate observed targets without exposing IDs

```bash
python tools/replay_har_graphql.py capture.har \
  --corpus-har other.har \
  --list-observed-targets
```

This prints stable fingerprints, observed selector keys, and observation counts. It does not print the underlying IDs/usernames.

## Controlled replay

Create a task-specific agreement whose `allowed_actions` includes:

```text
replay_captured_graphql_with_observed_target
```

Then select one captured operation and one observed target fingerprint:

```bash
python tools/replay_har_graphql.py capture.har \
  --corpus-har other.har \
  --agreement replay-agreement.json \
  --friendly PolarisProfileSuggestedUsersWithPreloadableQuery \
  --target-key target_id \
  --target-fingerprint <fingerprint>
```

A successful or denied server response is retained as evidence. HTTP errors are not collapsed into transport failures: a 401/403/400 response is itself useful verification that the substituted request reached the server and was rejected.

## Output

The live result reports:

- whether a request was actually sent;
- HTTP status or network-failure class;
- whether the substituted variable was in the request body or URL query;
- response field-path counts;
- lexical field classes (`public_target`, `viewer_target`, `target_private_candidate`, `unknown`);
- the replacement target's non-reversible display fingerprint.

It deliberately does not report response values. `target_private_candidate` remains a triage label, not a claim that another person's private data was disclosed.
