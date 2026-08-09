# HAR recommendation batch extraction

Use this workflow when a browser HAR already contains recommendation or suggested-user GraphQL responses and the task is to recover the observed batches, rank order, and ranking-context field presence.

This is an offline **computer-use** workflow. It reads only the supplied HAR and does not refresh, dismiss, replay, or trigger recommendations.

## Default boundary

The default output is pseudonymous:

- candidate identities are replaced by stable fingerprints;
- rank is retained;
- `social_context` and `display_reason` are reported as present/absent rather than emitted verbatim;
- request cookies, authorization headers, CSRF values, and other session material are never emitted.

```bash
python tools/extract_har_recommendations.py capture.har
```

## Value-bearing inspection

Raw candidate identifiers and captured ranking-context values require an agent-owned agreement that explicitly declares:

```text
inspect_captured_recommendation_values
```

Then run:

```bash
python tools/extract_har_recommendations.py capture.har \
  --include-values \
  --agreement agreement.json
```

This does not infer why an account was recommended. It reports only fields already delivered in the captured response.

## Verification

A valid run should:

- inspect only captured GraphQL response bodies;
- preserve observed candidate order;
- emit stable pseudonymous fingerprints by default;
- avoid treating rank or `display_reason` as proof of a hidden user action;
- fail closed when raw values are requested without the declared agreement action.
