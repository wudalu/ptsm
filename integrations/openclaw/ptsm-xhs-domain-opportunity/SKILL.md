---
name: ptsm-xhs-domain-opportunity
description: 当用户想分析小红书哪些领域更容易爆、比较内容赛道、寻找新增 PTSM 领域、评估现有 playbook 覆盖缺口，或要求运行 XHS domain opportunity scan 时，先调用 PTSM 的领域机会扫描，再给出下一步建议。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Domain Opportunity

Use this skill when the user asks OpenClaw or Codex to compare Xiaohongshu domains, find likely breakout niches, or decide whether PTSM should add a new domain/playbook.

## Required Flow

1. Resolve a keyword list from the user's request. If the request is broad, include current PTSM domains plus likely new candidates such as sleep recovery, light wellness, human enrichment, repair handcraft, Su Shi, World Cup, daily English, AI tools, pet life, and wuxia.

2. Run the PTSM scan. PTSM owns the scan, scoring, mapping, and artifact format.

```bash
uv run python -m ptsm.bootstrap xhs-domain-opportunity \
  --keywords "<comma separated keywords>" \
  --sample-limit-per-keyword 5 \
  --skip-login-check \
  --tool-timeout-seconds 70
```

3. Read the generated brief first:

- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.md`
- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.json`

Use JSON only when the Markdown brief is insufficient.

4. Summarize results into three action groups:

- `existing_playbook_fit`: use `guide-post` through `ptsm-xhs-topic-guide` or `ptsm-xhs-psychology`.
- `sublane_first`: run a narrow experiment inside an existing playbook before adding a domain.
- `new_domain_candidate`: create a new domain plan before implementing playbook/runtime assets.

5. Recommend the next PTSM action, not a finished post:

- For `existing_playbook_fit`, call `guide-post` next.
- For `sublane_first`, run `collect-xhs-patterns` for that narrower lane.
- For `new_domain_candidate`, create a new domain plan with docs, playbook, skill, account, eval, and harness updates.

## Guardrails

- Do not copy scoring logic from PTSM into this skill.
- Do not generate or publish posts from this skill.
- Do not expose raw feed ids, xsec tokens, raw URLs, or provenance.
- Do not treat search-level evidence as a full trend ranking.
- Do not invent domain recommendations that are not supported by the generated artifact.
- Do not call `run-playbook` from this skill; switch to the topic-guide or psychology skill after the user chooses a concrete content direction.
