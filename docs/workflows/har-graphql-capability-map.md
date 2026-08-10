# HAR GraphQL capability map

`tools/map_har_graphql_capabilities.py` aggregates persisted GraphQL operations observed across one or more HAR captures into an observational capability map.

The map preserves:

- friendly operation name and `doc_id`;
- endpoint path and query/mutation classification;
- capture/observation counts;
- observed variable keys and schemas;
- candidate expansion axes such as `target_id`, `user_id`, `username`, pagination keys, and nested count/id selectors;
- setting/storage selector identifiers such as `account_privacy_setting` without retaining the user's current setting values;
- response-shape paths and HTTP statuses.

Example:

```bash
python tools/map_har_graphql_capabilities.py capture1.har capture2.har -o capability-map.json
```

The output is deliberately observational. A variable name seen in a legitimate browser request is evidence that the persisted operation accepted that variable shape in that capture; it is not proof that arbitrary values are authorized, stable, or semantically meaningful.

This workflow does not replay requests and does not export cookies, CSRF values, authorization headers, or setting values. It is intended to identify which already-delivered persisted operations and selectors are worth separate controlled verification.
