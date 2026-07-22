---
name: ptsm-xhs-domain-opportunity
description: 当用户给出明确候选领域或关键词，想比较它们在小红书的搜索证据、评估现有 playbook 覆盖缺口，或要求运行 XHS domain opportunity scan 时，先调用 PTSM 的领域机会扫描，再给出下一步建议。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM XHS Domain Opportunity

Use this skill when the user asks OpenClaw or Codex to compare named Xiaohongshu domains/keywords or evaluate a concrete possible coverage gap. It is a bounded candidate comparison, not generic hotspot discovery.

## Required Flow

1. Require explicit candidate domains or keywords from the operator. The operator must supply at least one explicit keyword. If the request is broad (“找热点”“现在有什么值得写”), switch to `ptsm-topic-radar-discovery` and its `hotspot-discovery` command; do not invent a keyword list from current playbooks.

2. Run the PTSM scan. PTSM owns the scan, scoring, mapping, and artifact format.

```bash
uv run python -m ptsm.bootstrap xhs-domain-opportunity \
  --keywords "<comma separated keywords>" \
  --sample-limit-per-keyword 5 \
  --tool-timeout-seconds 70
```

Keep the default login preflight so `login_required` is an actionable result.
Only add `--skip-login-check` after the operator has just verified the XHS session and
only needs to avoid a slow duplicate preflight; an expired session then appears through
search diagnostics rather than `login_required`.

3. Read the generated brief first:

- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.md`
- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.json`

Use JSON only when the Markdown brief is insufficient.

4. Read `status` before recommending anything:

- `login_required` means the default XHS login preflight stopped before any keyword search. Show the `_login` diagnostic, ask the operator to run `ptsm xhs-login-qrcode`, then rerun. There are no fits, rankings, or new-domain candidates in this state; never fill the gap with static mappings.
- `insufficient_evidence` means the bounded scan has no successful unique samples. Say that the scan found insufficient evidence, show only the returned diagnostics, and recommend recovery: restore XHS login/MCP access, narrow or replace keywords, then rerun the scan. There are no fits, rankings, or new-domain candidates in this state. Do not turn static keyword mappings into a recommendation.
- `partial` means some unique samples succeeded but one or more requested keyword paths either failed or returned no samples. Summarize only the artifact-backed results, name the limitation, and do not describe the result as a whole-site trend ranking. Recovery is to resolve the returned diagnostics or replace the zero-result keyword, then rerun before making an irreversible domain decision.
- `completed` means the bounded scan returned usable unique samples for every requested keyword path. Continue with only the artifact-backed action groups below.

5. For a `completed` result, or the evidence-backed subset of a `partial` result, summarize action groups only when they are present in the generated artifact:

- `existing_playbook_fit`: use `guide-post` through `ptsm-xhs-topic-guide` or `ptsm-xhs-psychology`.
- `sublane_first`: run a narrow experiment inside an existing playbook before adding a domain.
- `new_domain_candidate`: create a new domain plan before implementing playbook/runtime assets.

6. Recommend the next PTSM action, not a finished post:

- For `existing_playbook_fit`, call `guide-post` next.
- For `sublane_first`, run `collect-xhs-patterns` for that narrower lane.
- For `new_domain_candidate`, create a new domain plan with docs, playbook, skill, account, eval, and harness updates.

## Guardrails

- Do not copy scoring logic from PTSM into this skill.
- Do not generate or publish posts from this skill.
- Do not expose raw feed ids, xsec tokens, raw URLs, or provenance.
- Do not treat search-level evidence as a full trend ranking.
- Do not invent domain recommendations that are not supported by the generated artifact.
- Do not invent a fit, ranking, or new-domain candidate when status is `insufficient_evidence`, or fill in missing partial evidence with the static mapping.
- Do not call `run-playbook` from this skill; switch to the topic-guide or psychology skill after the user chooses a concrete content direction.
