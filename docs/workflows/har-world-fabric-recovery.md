# HAR world-fabric recovery workflow

Use this workflow when the goal is to expand a browser capture into a richer relational model **before** choosing a profile-, post-, activity-, search-, or recommendation-style projection.

The workflow builds on the existing interaction and relational-fabric extractors, then preserves additional primitive entities and evidence families already present in the HAR.

## Current entity types

The current adapter can preserve:

- `person`
- `media`
- `comment`
- `location`
- `ui_surface`
- a synthetic `capture_actor` only when the capture owner cannot be resolved from authorized activity evidence

## Current edge families

From captured comment activity:

- `authored_comment`: person -> comment
- `comment_on_media`: comment -> media
- `commented_on_media`: person -> media
- `authored_media`: person -> media
- `commented_on_post_by`: commenter -> post author
- `co_commented_on_media`: commenter <-> commenter when both appear on at least one captured media object

From captured liked-media activity:

- `activity_owner_liked_media`: capture owner -> media
- `media_observed_at_location`: media -> location when the liked-media record includes a location name

From captured settings surfaces:

- `surface_contains_person`: close-friends selector surface -> person
- `activity_owner_blocked_person`: capture owner -> blocked person

## Preserve evidence, not guesses

The extractor intentionally distinguishes a captured relationship from a product-surface observation.

A person appearing in the Close Friends selector is represented as `surface_contains_person`. It is **not** automatically represented as `close_friend_of`; the capture proves that the account was surfaced in that selection UI, not that membership was selected.

Likewise, comments may include coarse relative-time labels such as `3w`. When two commenters on the same media have the same displayed relative-time label, the co-engagement edge can record `same_relative_time_label_count`. This is a coarse UI bucket, **not an exact event timestamp and not evidence of synchronized viewing**.

The workflow explicitly leaves these claims false unless a stronger future adapter has direct evidence:

- close-friends membership
- synchronized viewing
- shared recommendation delivery
- algorithmic causality
- exact timestamps derived from relative-time labels

## Command

```bash
python tools/extract_har_world_fabric.py capture.har \
  --require-fabric \
  -o world.json
```

Default output pseudonymizes people, media, comments, and location names.

Identity-bearing output is separately gated:

```bash
python tools/extract_har_world_fabric.py capture.har \
  --include-identities \
  --agreement agreement.json
```

The agreement must explicitly declare `extract_captured_world_fabric_identities`.

## Real-capture validation

On the supplied Instagram HAR, the workflow recovered:

- **249 person nodes**
- **69 media nodes**
- **61 comment nodes**
- **2 location nodes**
- **1 UI-surface node**
- **382 total nodes**
- **522 typed edges**
- **10 edge families**
- **27 liked-media observations**
- **223 Close Friends selector account observations**
- **3 blocked-account observations**
- **11 unique co-engagement person-pair edges**
- **1 weakly connected component containing all 382 nodes**

Compared with the previous 81-node / 145-edge relational fabric, this is approximately **371.6% more nodes** and **260.0% more edges** while remaining pseudonymized by default.

## Verification criteria

A valid run should:

- preserve comments as entities rather than only collapsing them into person-to-person edges;
- preserve liked media and location observations when captured;
- model UI selection candidates as surface observations rather than asserted social relationships;
- preserve explicit blocked-account relationships from the capture owner;
- deduplicate known person identities internally before pseudonymization;
- aggregate repeated co-engagement by person pair and expose shared-media weight;
- emit no usernames, user IDs, media IDs, comment IDs, location names, comment text, cookies, or tokens by default;
- keep synchronization, recommendation, and stronger membership interpretations explicitly unclaimed without stronger evidence.
