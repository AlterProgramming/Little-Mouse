# HAR GraphQL differential-analysis workflow

Use this workflow when two browser captures contain the same GraphQL operation under different conditions and the task is to determine **what changed in the observed request/response shape**.

Typical conditions include before/after account settings, blocking/unblocking, route changes, feature rollouts, or other controlled interventions.

This is a **computer-use** workflow under the Little Mouse two-capability model. It is a derived browser-capture analysis workflow, not a new top-level capability.

## Boundary

The workflow is offline and value-blind. It compares only GraphQL requests and responses already captured in the supplied HAR files. It does not:

- replay authenticated requests;
- reuse cookies or tokens;
- emit captured variable values;
- bypass privacy or access-control decisions;
- infer causality merely because two captures differ.

The result is an observed schema differential. Experimental interpretation remains a separate reasoning step and must account for confounders.

## Supported GraphQL paths

Little Mouse recognizes both common captured forms:

- `/graphql/query`
- `/api/graphql`

Operations can be filtered by `fb_api_req_friendly_name`, persisted `doc_id`, or both.

## Command

Compare one operation by friendly name:

```bash
python tools/diff_har_graphql.py before.har after.har \
  --friendly PolarisProfilePageContentQuery
```

Compare by persisted query ID:

```bash
python tools/diff_har_graphql.py before.har after.har \
  --doc-id 38611279431804694
```

The output reports:

- matching-entry counts in each capture;
- added schema paths;
- removed schema paths;
- changed leaf types/shapes;
- separate request-variable and response-schema differentials;
- `values_emitted: false`.

## Verification

A valid run should:

- inspect only captured GraphQL entries;
- merge repeated observations of the selected operation within each capture;
- expose no captured request values or authentication material;
- preserve the distinction between field omission, field addition, and type/shape change;
- make no automatic claim that a changed field was caused by the intervention.
