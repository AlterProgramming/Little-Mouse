# Evidence Contract

Little Mouse is not required to produce a finding.

A run may terminate successfully with:

```text
NO_RESULT
```

This is preferable to manufacturing significance from weak or merely adjacent evidence.

## Evidence levels

### OBSERVATION
A fact literally present in the authorized capture or another declared source.

Examples: a username appears in a response; a media identifier is present; a watermark value is returned; two comment records reference the same media object.

### DERIVATION
A deterministic consequence of one or more observations. A derivation must retain explicit support references.

Examples: two observations share the same media identifier; a watermark advanced between two exact capture observations; two records resolve to the same pseudonymized subject.

### HYPOTHESIS
An explanatory model worth testing. A hypothesis is not a finding and may exist with `result_status = NO_RESULT`.

Examples: repeated cross-surface proximity may reflect latent affinity; a content cluster may influence a recommendation projection.

### CLAIM
A statement promoted beyond deterministic derivation. A claim requires explicit supporting evidence and must preserve contradiction/retraction paths.

## Delivery rule

There is no evidence-layer delivery obligation. If no observation, derivation, or supported claim materially answers the question, return `NO_RESULT` and retain the raw evidence.

Do not generate a replacement hypothesis merely to make the run feel useful.

## Human-facing reports

Reports should answer the human question first. Implementation vocabulary belongs underneath the answer, not in place of it.

For each reported person, cluster, or temporal event, separate:

1. what was observed;
2. what was deterministically derived;
3. what remains a hypothesis;
4. what is not supported;
5. contradictions or later evidence that could retract the interpretation.

A co-comment, shared media node, same response batch, recommendation appearance, or watermark is not automatically evidence of profile viewing, personal interest, synchronized behavior, or recommendation causality.

## Promotion rule

Promotion must be earned by new semantics or independent evidence, not by repeated wording of the same observation. Lower-level evidence is retained when a higher-level statement is created.
