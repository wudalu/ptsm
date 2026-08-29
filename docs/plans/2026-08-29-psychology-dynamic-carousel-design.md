# Psychology Dynamic Carousel Design

## Goal

Let `modern_psychology_post` choose its carousel page count from the approved
content instead of a fixed product range. A single Xiaohongshu image post may
contain 1–18 pages. Content that cannot fit within 18 bounded semantic pages
must stop before image generation or publishing and ask the operator to shorten
the content or confirm a separate-post workflow.

All image-visible psychology copy is normalized to remove unsupported emoji.
Every rendered page keeps a visible `NN / TT` page counter and bottom progress
bar so the recipient can recover the intended order even if an external client
reorders individual image messages.

## Scope

- Ordinary automatic `modern_psychology_post` text carousels.
- Current builtin and newly confirmed psychology learning-series curricula.
- Guide, prompt, renderer, manifest, delivery receipt, wrapper skill, tests, and
  active source-of-truth documentation.
- Historical learning templates remain byte-for-byte reconstructible.

## Non-goals

- Automatically publishing multiple Xiaohongshu posts when one lesson needs
  more than 18 pages.
- Treating independent images as a carousel batch.
- Adding a manual page-count CLI flag.
- Changing non-psychology playbooks or provider-image behavior.
- Claiming that a local `ready` receipt proves recipient delivery.

## Page-count contract

`PsychologyCarouselPlan` accepts one topic with 1–18 contiguous pages. The first
page is always `cover_hook`; inner pages keep the existing bounded semantic role
and visible-text contracts. There is no target count and no character-count
pagination. Ordinary model-backed drafting decides how many semantic pages the
content needs, while deterministic paths construct pages from their semantic
units.

The guide advertises `page_count.min=1`, `page_count.max=18`, and explains that
the final count is content-derived. It does not promise a particular number,
author page copy, or introduce a count flag.

When a candidate contains more than 18 pages, normalization fails with a stable
page-limit diagnostic. The workflow must not render, ledger, publish, or expose
a relay-ready receipt. It may retry ordinary model drafting within its existing
bounded reflection loop, but it may not silently create multiple posts.

## Learning-series versioning

Historical contracts remain frozen:

- custom template v1: historic single-card contract;
- builtin curriculum v1 and custom template v2: historic carousel;
- builtin curriculum v2 and custom template v3: historic seven-page editorial
  carousel.

The current builtin curriculum advances to v3 and newly confirmed custom
curricula use controlled template v4. Template v4 deterministically creates
content-derived pages from catalog-approved units. It preserves every approved
scene, concept, explanation, exercise, scope, professional-support boundary,
and comment prompt. Short compatible units can share a page; long units split
only at catalog-authored punctuation into additional pages. No model is called
to paginate or rewrite a lesson.

The exact page count and ordered roles returned for a selected lesson are
derived from that frozen lesson and template. Catalog receipts and evaluators
remain version-bound.

## Emoji normalization

Image-visible `headline` and `body_lines` remove unsupported emoji codepoints
before ordinary safety and density validation. Emoji-only fields remain
invalid, and removal must not bypass locator, unsafe-claim, instruction-leakage,
line-length, or page-density checks. Learning template v4 uses the same
normalization; existing custom copy compaction continues to strip emoji before
freezing a new catalog.

Historical templates are not mutated. Their already accepted copy is rebuilt
under their original controlled-template version.

## Ordering and delivery

The final normalized page array is the only canonical order. Rendering assigns
each page the final total and draws `order / page_count`; the manifest records
the same contiguous order, page hash, and PNG hash. The delivery receipt exposes
the complete `attachments` list only after the immutable set and asset ledger
are complete.

An external relay must:

1. iterate `attachments` by canonical `order`, never by path or filename;
2. prefer one ordered multi-image message when the channel supports it;
3. otherwise send sequentially and wait for sender acknowledgement before the
   next image;
4. record `set_id`, `manifest_sha256`, attachment order, file hash, and sender
   message ID;
5. call the set delivered only after every expected order is acknowledged;
6. retry the same immutable files without regeneration or reordering.

PTSM owns the local ready receipt, not the external sender or recipient state.
Visible page numbers are a user-facing recovery aid, while relay ACK records are
the delivery truth.

## Verification

- Domain tests cover 1 page, 18 pages, 19-page rejection, contiguous order, and
  emoji removal including emoji-only rejection.
- Runtime/application tests cover dynamic guide bounds, ordinary draft gates,
  exact learning-template versioning, manifest/receipt order, and no ready
  handoff on overflow.
- Renderer tests assert dynamic `NN / TT` counters and progress for different
  totals.
- Wrapper/docs tests lock the 1–18 content-derived contract and sequential relay
  fallback.
- Deterministic dry-runs visually inspect at least two different page counts.
- Full pytest, docs-sync, doctor, and harness-check run before merge.

