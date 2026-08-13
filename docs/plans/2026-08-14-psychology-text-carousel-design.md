# Psychology Text Carousel Design

**Date:** 2026-08-14

**Status:** approved

## Goal

Allow `modern_psychology_post` to express one psychology topic as an ordered
carousel of locally rendered 3:4 text cards. The capability applies to ordinary
scene posts and to builtin or user-confirmed psychology learning-series lessons.

The feature must preserve psychology safety, keep learning-series material bound
to its frozen catalog, and publish either the complete ordered carousel or no
generated images at all.

## User-visible behavior

- Psychology posts may carry a structured text-carousel plan instead of only a
  single cover plan.
- Ordinary psychology carousels contain 4–7 pages chosen from these semantic
  roles: cover hook, concrete scene, light mechanism/reframe, saveable tool,
  scope or professional-help boundary, and comment prompt.
- Learning-series carousels are catalog-owned and contain the approved cover,
  scene, concept, explanation, micro-practice, scope/professional-help boundary,
  and comment prompt without model-authored additions.
- The cover remains low density. Inner pages may carry several short text blocks,
  but never a whole body paragraph, hashtags, source material, diagnosis,
  treatment promises, or medication advice.
- Existing single-image behavior remains available for non-carousel image plans
  and explicit ordinary-post overrides. Learning-series image overrides remain
  forbidden.

## Chosen approach

Extend `final_content.image_plan` with an ordered, validated `slides` collection.
Generate that plan together with ordinary psychology content and reconstruct it
deterministically from a frozen catalog for learning-series content. Render each
slide locally using a dedicated `psychology_text_card_v1` style.

This is preferred over mechanically splitting body text because semantic page
boundaries must remain intact. It is also preferred over a second model call
because a post-render rewrite could drift from the validated draft or add unsafe
psychology claims.

## Carousel contract

The parent image plan keeps the compatible fields already consumed by the image
pipeline and adds carousel metadata:

```json
{
  "backend": "local_social_screenshot",
  "style": "psychology_text_card",
  "role": "text_carousel",
  "text_density": "medium",
  "carousel_style": "psychology_text_card_v1",
  "slides": [
    {
      "slide_id": "cover",
      "order": 1,
      "role": "cover_hook",
      "headline": "他没回消息，我先想到了分手",
      "body_lines": ["先别急着给沉默下结论"]
    }
  ]
}
```

Contract rules:

- 4–7 slides, contiguous one-based order, unique stable `slide_id` values.
- The first slide is `cover_hook` and has one headline plus at most one short
  supporting line.
- Inner slides have one short headline plus one to four short lines.
- Allowed roles are a small psychology-specific allowlist; unknown fields or
  roles fail closed.
- All visible slide text is scanned by the same psychology-safety and provenance
  boundaries as title, cover text, and body.
- An ordinary carousel may be model-authored but must pass structural and safety
  validation before rendering or publishing.
- A learning carousel is reconstructed from the controlled lesson template and
  must exactly match it at executor, reflector, finalize, artifact, image, and
  offline receipt boundaries.

## Runtime data flow

For an ordinary psychology post:

1. `guide-post` returns the selected direction and a text-carousel image
   recommendation when the format benefits from explanation or a saveable tool.
2. The drafting backend emits normal final content plus an ordered slide plan.
3. Runtime/application validation checks shape, order, text budgets, safety, and
   instruction leakage.
4. When image generation is requested, the application layer renders the full
   group locally in a temporary directory.
5. Only after every slide passes verification are the files promoted to stable
   ordered names and attached to the artifact and publisher request.

For a learning-series lesson, the existing plan/review/exact-confirmation and
explicit lesson-selection flow is unchanged. The frozen catalog now owns the
carousel plan as part of the controlled lesson template. `guide-post`, runtime,
artifact receipt, and offline evaluation all reconstruct the same plan from the
selected series/version/lesson.

## Rendering and publication

`NoteCardImageBackend` gains `psychology_text_card_v1`, with variants driven by
slide role rather than fake phone chrome. It renders only provided slide text;
it does not summarize the body or invent filler. Stable filenames use the
carousel order, for example `artifact-01-cover.png` and
`artifact-02-scene.png`.

The application layer owns group orchestration. Downstream watermark handling,
publisher interfaces, and manual image paths already accept ordered image lists
and remain generic. Local-renderer provenance continues to skip watermark
inpainting.

## Failure semantics

- Invalid carousel plans fail before image generation or publish.
- Slide rendering is all-or-nothing. A failed or missing page produces
  `psychology_carousel_generation_failed`; no generated page reaches the
  publisher.
- A failed generation receipt is persisted for diagnosis without treating a
  partial group as publishable.
- If image generation was requested for a learning-series run, production
  progress is recorded only after the complete carousel and strict catalog
  receipt are safe. When image generation was not requested, the existing safe
  content-artifact progress behavior remains valid.
- Learning-series recovery remains idempotent and never performs online cleanup
  of untrusted catalog/progress state.

## Observability

`image_generation` gains carousel-level `carousel_style` and `image_count`, plus
ordered `pages` evidence. Each page records its slide identity, order, role,
style, path, bounded visible-text summary, prompt hash, and provenance. The
generated-image asset ledger records the same page identity per image.

Post metrics retain the existing primary image style and add `image_count` and
`carousel_style` so future experiments can compare single covers with text
carousels without inventing performance claims.

## Testing strategy

- Domain tests lock valid and invalid slide contracts, safety scanning, stable
  ordering, and deterministic learning-series reconstruction.
- Drafting tests prove deterministic and model JSON paths preserve nested slides.
- Renderer tests inspect dimensions, nonblank output, role variants, text
  budgets, and stable page metadata.
- Application tests prove ordered multi-page generation, all-or-nothing failure,
  artifact/ledger evidence, watermark routing, and publisher order.
- Learning-series tests prove catalog ownership, receipt validation, override
  rejection, and progress timing.
- Guide, wrapper, docs, metrics, and e2e tests lock the user-visible contract.

## Documentation surface

Update the complete affected source-of-truth surface: `architecture.md`,
`runtime.md`, `playbooks.md`, `skills.md`, `harness-engineering.md`,
`observability.md`, `docs/operations.md`, and the affected operations runbooks.
Also update the psychology OpenClaw wrapper and the cross-domain image-form
reference. Topic Radar and unrelated domain/playbook contracts remain unchanged.

## Non-goals

- No raster-image model is used to typeset carousel text.
- No visual editor or review UI is added.
- No automatic publishing is introduced.
- No new psychology facts, diagnoses, treatments, or course lessons are created.
- No cross-domain automatic carousel rollout is included in this change.
