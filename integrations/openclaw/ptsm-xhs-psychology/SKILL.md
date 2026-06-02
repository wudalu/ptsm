---
name: ptsm-xhs-psychology
description: 当用户想发布小红书心理学、情绪、关系边界、焦虑、内耗、自我关怀或 AI 陪伴边界类内容时，先调用 PTSM 的心理学选题引导，再生成或发布。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Psychology

Use this skill when the user asks OpenClaw to create, prepare, draft, save, or publish a Xiaohongshu post in the psychology domain. Common triggers include 心理学、情绪、焦虑、内耗、边界感、关系、自我关怀、孤独、比较焦虑、睡眠恢复、轻养生、办公室恢复、AI 陪伴, and similar wording.

For non-psychology XHS playbooks, use `ptsm-xhs-topic-guide`; this file remains the psychology-specific wrapper.

## Required Flow

1. Call PTSM guidance first. Do not write or publish the post before this step.

```bash
uv run python -m ptsm.bootstrap guide-post \
  --scene "<user request or concrete scene>" \
  --non-interactive \
  --format json
```

2. Show the user only the returned `topic_guidance.directions`: direction name, `direction_type`, `scene_fit`, trend signal, viral hook, why it may work, best scenes, content angle, saveable tool, comment prompt, and avoid note. When returned direction(s) have `direction_type: open_scene`, label them as PTSM-returned open_scene exploration directions.

PTSM may return sleep recovery / light-wellness directions such as 睡眠恢复、轻养生、办公室恢复 as a PTSM-returned psychology sublane. Display them exactly like other returned psychology directions; do not turn them into a separate non-psychology playbook or add unreturned wellness advice.

3. Ask the user to choose one direction, or pick the best matching direction when the user has already given a clear scene.

If the user changes the scene, call `guide-post` again with the new scene. Do not reuse previous directions for a different scene.

4. After the topic direction is chosen or confirmed, show only the returned `topic_guidance.image_recommendation`: `recommended_backend`, `local_style`, `provider`, `model`, `role`, `text_density`, `max_text_units`, `reason`, `command_hint`, and `fallback`.

If `recommended_backend` is `provider_image`, describe it as an LLM/provider image recommendation and use the returned `provider` and `model`. If `recommended_backend` is `local_social_screenshot`, describe the returned local style such as `wechat_chat`, `iphone_notes`, or `note_card`. Do not add extra image styles, providers, or model names.

5. Generate through PTSM only after the direction is chosen or confirmed. Pass the chosen direction's id as `--topic-direction-id`.

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --guidance-ack \
  --scene "<confirmed psychology direction and concrete scene>" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --topic-direction-id "<chosen direction id>" \
  --publish-mode dry-run
```

6. Real publishing requires the user's explicit publish intent and the normal PTSM publish flags. Prefer dry-run first.

## Guardrails

- 不要展示内部研究路径。
- 不要展示原始研究笔记。
- Do not mention hidden research documents, file paths, raw source URLs, or provenance to the user.
- Do not copy topic logic into this skill; PTSM owns the guidance payload.
- Do not invent, expand, or replace PTSM-returned open_scene direction(s); only display them when they are present in `topic_guidance.directions`.
- Do not invent, expand, or replace PTSM-returned psychology sublane direction(s), including 睡眠恢复、轻养生 or 办公室恢复; only display them when PTSM returns them.
- Do not invent, expand, or replace PTSM-returned image recommendation; only display `topic_guidance.image_recommendation` when PTSM returns it.
- If `run-playbook --caller openclaw` returns `topic_guidance_required`, show the directions and call `run-playbook` again only after direction confirmation with `--guidance-ack`.
- Keep psychology safety boundaries intact: no diagnosis, no treatment promises, no medication advice, and crisis or persistent impairment should be redirected to professional support.
