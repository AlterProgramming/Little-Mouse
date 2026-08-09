# HAR GraphQL projection-equivalence analysis

Use this workflow when one HAR contains multiple GraphQL operations that may target the same captured account/object through selectors such as `id`, `userID`, `user_id`, `target_id`, `target_user_id`, `igid`, or `username`.

The workflow answers a narrow question: **which response field paths are shared across observed operations for the same captured target fingerprint, and which fields are projection-specific?**

```bash
python tools/analyze_har_projections.py capture.har
```

## Privacy and authority boundary

Target selector values are never printed. The tool hashes each observed selector value into a stable fingerprint and groups operations only when those fingerprints match.

It does not:

- replay a request;
- resolve a target fingerprint back to an identity;
- claim that matching fields imply identical server authorization;
- infer fields that were not present in the captured responses;
- export cookies, authorization headers, CSRF values, or other session material.

## Output

For each target fingerprint with at least two captured operations, the report includes:

- operation names / persisted query IDs;
- selector names used by each operation;
- observed response field counts;
- field paths common to every operation in the group;
- response field paths unique to one projection.

This is useful for distinguishing a rich profile projection from narrower hover-card, badge, note, highlight, or recommendation projections without treating a client route definition as proof that a corresponding request was executed.
