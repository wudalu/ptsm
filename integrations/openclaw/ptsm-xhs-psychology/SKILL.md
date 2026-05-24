---
name: ptsm-xhs-psychology
description: 当用户想发布小红书心理学、情绪、关系边界、焦虑、内耗、自我关怀或 AI 陪伴边界类内容时，先调用 PTSM 的心理学选题引导，再生成或发布。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Psychology

Use this skill when the user asks OpenClaw to create, prepare, draft, save, or publish a Xiaohongshu post in the psychology domain. Common triggers include 心理学、情绪、焦虑、内耗、边界感、关系、自我关怀、孤独、比较焦虑、AI 陪伴, and similar wording.

## Required Flow

1. Call PTSM guidance first. Do not write or publish the post before this step.

```bash
uv run python -m ptsm.bootstrap guide-post \
  --scene "<user request or concrete scene>" \
  --non-interactive \
  --format json
```

2. Show the user only the returned `topic_guidance.directions`: direction name, trend signal, viral hook, why it may work, best scenes, content angle, saveable tool, comment prompt, and avoid note.

3. Ask the user to choose one direction, or pick the best matching direction when the user has already given a clear scene.

4. Generate through PTSM only after the direction is chosen or confirmed.

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --guidance-ack \
  --scene "<confirmed psychology direction and concrete scene>" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --publish-mode dry-run
```

5. Real publishing requires the user's explicit publish intent and the normal PTSM publish flags. Prefer dry-run first.

## Guardrails

- 不要展示内部研究路径。
- 不要展示原始研究笔记。
- Do not mention hidden research documents, file paths, raw source URLs, or provenance to the user.
- Do not copy topic logic into this skill; PTSM owns the guidance payload.
- If `run-playbook --caller openclaw` returns `topic_guidance_required`, show the directions and call `run-playbook` again only after direction confirmation with `--guidance-ack`.
- Keep psychology safety boundaries intact: no diagnosis, no treatment promises, no medication advice, and crisis or persistent impairment should be redirected to professional support.
