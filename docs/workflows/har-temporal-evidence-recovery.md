# HAR temporal-evidence recovery

Use this workflow when a browser capture contains relational co-observation plus timestamp-bearing fields and the goal is to determine **what can actually be placed on a time axis** without confusing transport time, content time, watermarks, and participant action time.

```bash
python tools/extract_har_temporal_evidence.py capture.har \
  -o temporal.json
```

## The negative space this fills

A shared HAR response batch can be timestamped precisely when the entry has `startedDateTime`. For comment co-engagement, Little Mouse now records the exact `co_observed_at` capture timestamp for distinct commenters observed on the same media in the same response entry.

That is an upgrade from an untimed batch counter to an exact **browser co-observation time**. It is still not the time either participant commented, opened the post, or viewed it.

The workflow therefore keeps two statements separate:

- `same response batch at 2026-...Z` can be supported by HAR timing;
- `the participants viewed the media together at that time` cannot be supported unless the capture supplies participant action timestamps with that semantic meaning.

## Current exact timestamp classes

The adapter currently recognizes these timestamp families when present:

| Captured field | Semantic class | Role | What it does not prove |
| --- | --- | --- | --- |
| HAR `startedDateTime` | `capture_observation` | browser observation time | participant event time |
| `extensions.server_metadata.request_start_time_ms` | `server_request_start` | server transport time | user interaction time |
| `extensions.server_metadata.time_at_flush_ms` | `server_response_flush` | server transport time | user interaction time |
| direct-thread `last_activity_timestamp_ms` | `thread_last_activity` | conversation activity time | a viewing action |
| `slide_read_receipts[].watermark_timestamp_ms` | `read_through_watermark` | read-through timeline position | the wall-clock instant a participant read |
| story tray `seen` / `reel_media_seen_timestamp` | `story_seen_through_watermark` | seen-through media position | the wall-clock instant a story was watched |
| story tray `latest_reel_media` | `story_latest_media` | content creation time | viewing time |
| media `taken_at` | `media_taken_at` | content creation time | engagement time |
| caption `created_at` / `created_at_utc` | `caption_created_at` | content creation time | engagement time |

The output normalizes recognized numeric timestamps to UTC ISO timestamps while retaining their original precision and semantic role.

## Direct viewing-action timestamps

The synchrony boundary is deliberately narrow. Only explicit participant-action fields such as `viewed_at`, `viewed_at_ms`, `view_timestamp`, or `view_timestamp_ms` are classified as `view_action` by this adapter. `seen`, story seen-watermarks, read-watermarks, request times, and response times are never promoted into that class.

Even when a direct viewing-action timestamp is present, this extractor only marks it as capable of supporting a synchrony analysis. It does not automatically claim synchronized viewing.

## Same-response co-observation

For captured comment records, the temporal adapter reuses the existing relationship extractor and preserves only pseudonymous fingerprints. Each same-media/same-entry pair can include:

- two participant fingerprints;
- one media fingerprint;
- capture entry index;
- exact `co_observed_at` timestamp;
- timestamp precision;
- `participant_event_time: false`;
- `synchronized_viewing_claimed: false`.

No usernames, user IDs, media IDs, comment text, cookies, or session secrets are emitted.

## Current-capture result

The supplied Instagram captures already contain exact millisecond/second temporal material in several independent channels, including HAR observation times, GraphQL server timing, direct-thread activity/read watermarks, story seen-through watermarks, and media creation times.

In the activity-center comment capture, the existing 61 comment evidence records produce **10 same-media / same-response commenter-pair co-observations across 3 exact HAR response moments**. Those observations now have exact `co_observed_at` values rather than only batch counts.

The same capture still contains no explicit per-participant view-action timestamp for those comments/media, and its comment ages remain coarse UI labels. Therefore `exact_view_action_timestamps_available` and `synchronized_viewing_claimed` remain false. This is now a specific missing field class rather than an unimplemented temporal-analysis gap.

## Verification criteria

A valid run should:

- decode ordinary and base64-serialized JSON response bodies;
- normalize only known timestamp fields with known units;
- preserve the semantic role of every timestamp;
- pseudonymize identifier-bearing context;
- attach exact HAR observation time to same-response co-observation;
- never treat a read/seen watermark as a participant action time;
- never treat capture observation time as a participant event time;
- keep `synchronized_viewing_claimed: false` unless a separately validated inference layer has compatible direct action evidence.
