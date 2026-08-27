---
title: Psychology Learning Editorial Polish Design
status: active
owner: ptsm
last_verified: 2026-08-27
source_of_truth: false
related_paths:
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/psychology_carousel.py
  - src/ptsm/infrastructure/images/note_card_backend.py
  - src/ptsm/skills/builtin/psychology_style/SKILL.md
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
---

# Psychology Learning Editorial Polish Design

## Goal

Make psychology learning carousels arrive in their canonical page order, remove
emoji that the local font stack cannot render, and improve both the reader copy
and card typography toward a warm, restrained editorial style.

## Confirmed User Experience

- A lesson remains one complete seven-page carousel.
- The first image is visibly page 1 and the external relay consumes the exact
  `carousel_delivery.attachments` order from PTSM.
- Image-visible copy contains no emoji or unsupported emoji presentation
  sequences.
- Headlines are shorter and calmer; body copy feels conversational and
  spacious without adding psychology facts, diagnoses, treatment claims, or
  promises.
- Cards use clearer hierarchy, more deliberate line spacing and whitespace,
  restrained color, and explicit page counters.

## Chosen Architecture

Use a versioned content upgrade instead of rewriting frozen lessons in place.
Historic custom template v1/v2 snapshots remain reconstructable. The existing
builtin curriculum version remains available for old artifacts, while a new
builtin curriculum version and newly confirmed custom catalogs use controlled
template v3. Template v3 may recompose only catalog-approved fields; it cannot
invent course evidence or claims.

Keep emoji exclusion at the psychology carousel domain boundary. Ordinary model
drafts with emoji in `headline` or `body_lines` fail validation and can be
retried. Template v3 removes emoji while constructing new controlled catalog
copy and then validates the final image plan. Historical material is not
silently mutated; a historical catalog that cannot satisfy the image contract
fails closed and requires a new immutable revision.

Upgrade the existing local `psychology_text_card_v1` renderer rather than add a
provider or generic image schema. The style identifier and 1080x1440 contract
stay stable, while rendering changes are captured by new PNG hashes and a new
content-addressed committed set.

PTSM continues to own only the local ordered receipt. The external wrapper must
relay the complete attachment list in ascending `order`, verify page/file
hashes, and require acknowledgements for all expected pages before describing
delivery as complete. The repository wrapper and installed Codex skill mirror
must be byte-identical at handoff.

## Rejected Alternatives

- Renderer-only changes do not improve reader copy.
- Removing emoji only while drawing makes visible PNG content diverge from the
  reviewed page contract and receipt.
- Rewriting v1/v2 snapshots in place breaks immutable catalog and artifact
  reconstruction.
- Reordering file paths at the sender without using canonical attachments treats
  a downstream symptom and can still detach paths from their hashes.

## Error Handling

- Any emoji-bearing ordinary slide fails before rendering.
- Any unsupported or tampered controlled-template version fails closed.
- A missing, duplicate, reordered, or hash-mismatched attachment never becomes
  a relay-ready complete set.
- A partial sender acknowledgement remains external relay `partial`, never PTSM
  or user delivery success.
- No real publishing is added or performed by this feature without an explicit
  user instruction naming the target operation.

## Verification

- Domain tests for emoji ranges, variation selectors, keycaps, and ordinary
  punctuation/symbol compatibility.
- Exact reconstruction tests for historic builtin/custom content and new v3
  builtin/custom drafts.
- Renderer tests for text hierarchy, counter placement, bounds, and absence of
  emoji in drawn strings.
- Guide/run/eval/metrics regression coverage for curriculum and controlled
  template versions.
- Wrapper/docs tests plus an exact installed-mirror comparison.
- Deterministic learning-series dry-run with a complete committed carousel,
  manifest-order inspection, visual PNG review, full pytest, docs-sync, doctor,
  and harness-check.
