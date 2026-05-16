---
title: XHS Content Experiment Log
status: active
owner: ptsm
last_verified: 2026-05-16
source_of_truth: false
related_paths:
  - docs/operations/content-experiment-runbook.md
  - docs/research/2026-05-15-xhs-content-quality-sample-set.md
  - outputs/artifacts
---

# XHS Content Experiment Log

This log records whether borrowed mechanics improve real account outcomes. Fill one row per published variant.

## Variant Legend

- `comment_chain`: asks readers to complete, rewrite, or submit an example.
- `save_tool`: gives a reusable line, template, checklist, mini-tool, or screenshot-worthy frame.
- `identity_conflict`: names a recognizable identity tension that people may share.

## Active Experiments

| date | account | playbook | variant | topic source | title | cover text | artifact | publish time | 2h views | 2h likes | 2h collects | 2h comments | 2h shares | 24h views | 24h likes | 24h collects | 24h comments | 24h shares | 72h views | 72h likes | 72h collects | 72h comments | 72h shares | comment quality notes | next rewrite decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2026-05-16 | acct-fk-local | fengkuang_daily_post | comment_chain | sample-set: 发疯文学 工牌/群聊 | 18:57那句在吗把工牌点燃了 | 我的工牌先替我发疯 | outputs/artifacts/acct-fk-local-fengkuang_daily_post-1-6.json | not_published |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | Watch whether comments contain completed 工牌疯话, not only short reactions. | pending_publish_approval |
| 2026-05-16 | acct-psychology-local | modern_psychology_post | save_tool | sample-set: 反刍思维/情绪管理 | TBD | TBD | TBD | TBD |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | Watch whether collects outpace likes and whether comments give concrete复盘瞬间. | TBD |
| 2026-05-16 | acct-fk-local | fengkuang_daily_post | identity_conflict | sample-set: 打工人身份冲突 | TBD | TBD | TBD | TBD |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  | Watch for shares or comments like “这就是我”. | TBD |

## Dry-Run Calibration Prep Notes

- 2026-05-16: Ran a local 12-post dry-run probe for the planned Task 10 batch shape. This was not a real publish batch and produced no platform metrics.
- The probe exposed two engineering gaps before publish: repeated dry-runs for the same account/playbook could overwrite the previous artifact path, and deterministic drafts could leak operator labels such as `变体要求`, `comment_chain`, `save_tool`, or `identity_conflict` into final正文.
- Follow-up fix: artifact storage now preserves repeated dry-runs with numeric suffixes; playbook contracts forbid experiment-instruction leakage; deterministic scene cleanup strips those labels before drafting.
- Post-fix smoke artifact: `outputs/artifacts/acct-fk-local-fengkuang_daily_post-1-6.json` has `required_failed = 0` and no experiment-instruction leakage. It is a candidate for manual review, not evidence of online performance.

## Score Formula

```text
interaction_score = likes + collects*2 + comments*4 + shares*6
interaction_rate = interaction_score / views
```

## Weekly Review Template

Use this after at least 12 posts have `24h` and `72h` metrics.

### Winners

| rank | variant | playbook | title | 24h views | 24h interaction_rate | why it likely worked |
| --- | --- | --- | --- | ---: | ---: | --- |
| 1 | TBD | TBD | TBD |  |  | TBD |
| 2 | TBD | TBD | TBD |  |  | TBD |
| 3 | TBD | TBD | TBD |  |  | TBD |

### Failure Patterns

| pattern | evidence | decision |
| --- | --- | --- |
| hook got views but no saves/comments | TBD | revise_mechanic |
| saves happened but views were low | TBD | revise_hook |
| comments were praise only, no examples | TBD | revise_comment_prompt |

### Prompt/Eval Updates

Only convert a finding into prompt or eval changes when at least three comparable variants point the same way.

| finding | affected layer | proposed update | owner | status |
| --- | --- | --- | --- | --- |
| TBD | playbook / skill / eval | TBD | ptsm | pending |
