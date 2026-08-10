# HAR GraphQL capability map

`tools/map_har_graphql_capabilities.py` aggregates persisted GraphQL operations observed across one or more HAR captures into an observational capability map.

The map preserves:

- friendly operation name and `doc_id`;
- endpoint path and query/mutation classification;
- capture/observation counts;
- observed variable keys and schemas;
- candidate expansion axes such as `target_id`, `user_id`, `username`, pagination keys, and nested count/id selectors;
- setting/storage selector identifiers such as `account_privacy_setting` without retaining the user's current setting values;
- response-shape paths and HTTP statuses;
- for operations with an explicit person/account target axis, conservative response-field triage into `public_target`, `viewer_target`, `target_private_candidate`, and `unknown`.

Example:

```bash
python tools/map_har_graphql_capabilities.py capture1.har capture2.har -o capability-map.json
```

`target_response_field_classes` is lexical triage only. For example, a path containing `followed_by_viewer` is treated as viewer-relative, while a path such as `is_bestie` is flagged as a `target_private_candidate` that requires semantic verification. The latter label does not claim that another user's private value is disclosed; it means the field name is privacy-sensitive enough to warrant a controlled follow-up.

The output is deliberately observational. A variable name seen in a legitimate browser request is evidence that the persisted operation accepted that variable shape in that capture; it is not proof that arbitrary values are authorized, stable, or semantically meaningful.

This workflow does not replay requests and does not export cookies, CSRF values, authorization headers, setting values, or response values. It is intended to identify which already-delivered persisted operations, selectors, and response fields are worth separate controlled verification.
