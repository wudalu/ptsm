---
name: ptsm-xhs-topic-guide
description: 当用户想发布小红书发疯文学、人类丰容、苏轼诗词或其他已支持的非心理学 XHS 内容时，先调用 PTSM 的跨领域选题引导，再生成或发布。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Topic Guide

Use this skill when the user asks OpenClaw to create, prepare, draft, save, or publish a Xiaohongshu post for a supported non-psychology PTSM playbook.

## Intent Mapping

自动从用户意图映射到支持的 playbook id when clear:

- 发疯文学 / 打工人 / 抽象吐槽 -> `fengkuang_daily_post`
- 生活丰容 / 居家变量 / 低成本改造 -> `human_enrichment_daily_post`
- 苏轼 / 诗词 / 古典文化治愈 -> `sushi_poetry_daily_post`
- 心理学 / 情绪 / 关系边界 / 内耗 -> use `ptsm-xhs-psychology` instead

If the request is 模糊 or multiple playbooks fit, ask one short 澄清 / clarification question before calling PTSM. If the caller already resolved the target, accept the explicit `--playbook-id`.

## Required Flow

1. Call PTSM guidance first. Do not write or publish the post before this step.

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id "<resolved playbook id>" \
  --account-id "<resolved account id>" \
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
  --scene "<confirmed direction and concrete scene>" \
  --account-id "<account id>" \
  --playbook-id "<playbook id>" \
  --publish-mode dry-run
```

5. Real publishing requires the user's explicit publish intent and the normal PTSM publish flags. Prefer dry-run first.

## Guardrails

- 不要展示内部研究路径。
- 不要展示原始研究笔记。
- Do not mention hidden research documents, file paths, raw source URLs, or provenance to the user.
- Do not copy topic logic into this skill; PTSM owns the guidance payload.
- Do not expose directions that are not present in the returned `topic_guidance.directions`.
- For psychology, switch to `ptsm-xhs-psychology`; this generic skill does not own psychology safety boundaries or the `--guidance-ack` gate.
