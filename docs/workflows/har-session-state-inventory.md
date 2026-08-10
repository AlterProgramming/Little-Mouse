# HAR session-state inventory workflow

Use this workflow when a browser HAR came from an authenticated or partially authenticated session and the task is to determine **what kinds of session-bearing material are present** without exposing the captured values.

This is a **computer-use** workflow under the Little Mouse two-capability model. It expands the derived browser-capture archaeology surface without creating a new top-level capability.

## Boundary

The workflow is offline and value-blind. It reads only the supplied HAR and reports names/counts for session-bearing structures. It does not:

- emit cookie values;
- emit authorization values;
- emit CSRF or form-token values;
- replay captured requests;
- test whether captured credentials remain valid;
- infer that a capture is portable merely because session scaffolding is present.

The distinction matters: an authenticated capture can contain substantial request state while still omitting the portable cookie/session material needed to recreate that authentication elsewhere.

## What is reported

The inventory records:

- authentication-like request header names and occurrence counts;
- session/scaffolding header names and occurrence counts;
- session/form parameter names and occurrence counts;
- whether HAR request-cookie objects are populated;
- whether responses contain `Set-Cookie` headers;
- which GraphQL endpoint paths occur (`/graphql/query`, `/api/graphql`);
- whether some authenticated-session material is present;
- an explicit `portable_authentication_replay_proven: false` default.

No captured values are printed.

## Command

```bash
python tools/inspect_har_session.py capture.har
```

Write the report to disk:

```bash
python tools/inspect_har_session.py capture.har -o session-shape.json
```

## Verification

A valid run should:

- remain completely offline;
- contain no cookie, token, authorization, or CSRF values;
- distinguish value presence from replayability;
- report endpoint and parameter **names** rather than captured secret material.
