# HAR media recovery workflow

Use this workflow when a browser HAR contains media response bodies, especially when a site delivered the media in HTTP byte ranges.

## Boundary

This workflow reconstructs **only bytes already captured inside the HAR**. It does not replay authenticated requests, reuse cookies, bypass access controls, or depend on a CDN URL remaining valid.

## Procedure

1. Load the HAR JSON and enumerate `log.entries`.
2. Select responses whose `response.content.mimeType` is media (`video/*`, `audio/*`, or `image/*`).
3. Require an embedded `response.content.text` body. Decode Base64 when `response.content.encoding == "base64"`.
4. Determine each chunk's byte offset from `Content-Range` or byte-range query parameters such as `bytestart` / `byteend`.
5. Normalize the media URL by removing only byte-range selectors. This groups multiple range requests that belong to one underlying asset while preserving the rest of the asset identity.
6. Sort chunks by starting byte.
7. Reconstruct an asset only when coverage begins at byte 0 and is contiguous. Overlapping chunks are checked for conflicting bytes.
8. Write recovered media and a `manifest.csv` containing chunk counts, recovered byte size, SHA-256, gaps, and overlap-conflict status.
9. Keep source URLs out of the manifest by default. `--write-urls` is opt-in because captured media URLs may be signed or temporary.

## Command

```bash
python tools/recover_har_media.py capture.har -o recovered
```

For MP4 video only:

```bash
python tools/recover_har_media.py capture.har -o recovered --mime video/mp4
```

To also record normalized source URLs:

```bash
python tools/recover_har_media.py capture.har -o recovered --write-urls
```

## Verification

A valid recovery run should report:

- the number of HAR entries inspected;
- the number of unique media assets with embedded bodies;
- the number of contiguous assets written;
- a SHA-256 for every written asset in `manifest.csv`.

Do not infer that a HAR contains the full remote asset merely because a request URL points to a complete resource. The recovered file is valid only to the extent that the captured byte ranges provide contiguous coverage from byte 0.
