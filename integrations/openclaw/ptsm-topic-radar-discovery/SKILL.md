---
name: ptsm-topic-radar-discovery
description: 当用户想不限定方向找热点、看今天热点、找全平台可讨论话题、先发现再决定内容赛道时，先运行 PTSM 的开放热点发现与后置赛道路由。
metadata: {"openclaw": {"requires": {"bins": ["uv"]}}}
---

# PTSM Topic Radar Discovery

Use this skill for generic hotspot discovery. It starts with evidence collection,
not a playbook, account, domain, or keyword guess.

## Required Flow

1. Confirm the request is broad discovery: for example “现在有什么热点”“全平台热点是什么” or “先找热点再决定写什么”. If the operator instead names explicit candidate domains or keywords to compare on Xiaohongshu, use `ptsm-xhs-domain-opportunity`.

2. Run the discovery command without adding a direction filter. PTSM owns collection, evidence validation, routing, and artifact format.

```bash
uv run python -m ptsm.bootstrap hotspot-discovery
```

The default brief returns the top 12 verified clusters by Topic Radar score. If
the operator explicitly needs a shorter or longer reading list, add only
`--max-hotspots <positive-number>`; this changes the display cap, never the
platform scan or direction.

3. Read the JSON response, then its generated Markdown brief under `outputs/artifacts/hotspot-discovery/`. The brief is an operator report: it may show an `operator_headline`, opaque cluster/evidence references, scan quality, route candidates, and `eligible_hotspot_count` / `returned_hotspot_count` / `hotspot_limit` so a capped list is not mistaken for a full ranking. Also read `route_status_counts` and the non-duplicated `routed_hotspots` supplement: each row introduces at least one not-yet-shown playbook, while an ambiguous row keeps its complete candidate set; it never changes the all-platform order.

4. Read `status` before discussing results:

- `completed`: summarize only the returned evidence-backed hotspots. It reflects configured public platform sources, not an unlimited whole-web claim.
- `partial`: show the returned `platform_errors`, summarize only the successful evidence subset, and state the limitation. Do not describe a partial scan as all-platform.
- `insufficient_evidence`: say there is no usable hotspot recommendation, show diagnostics, restore the unavailable source/MCP/login path, then rerun. Do not invent a static topic list.

5. Present `hotspots` in their returned score order and show each `route.status`; use `route_status_counts` for the overall route summary. Do not regroup Top-N in a way that changes its all-platform order. Then include any separate `routed_hotspots` supplement without calling it part of the Top-N ranking:

- `existing_playbook_fit`: show the operator headline, evidence/platform support, and the returned existing playbook candidate. Ask the user to choose it before entering a content flow.
- `ambiguous`: show the returned candidates and ask the user to choose; do not tie-break with a guessed domain.
- `unmapped`: say that PTSM has no current playbook fit. If `new_domain_candidate` is true, offer a deliberate new-domain review/plan; otherwise recommend monitoring or rescanning. Never force it into psychology, wellness, or another existing lane.

6. Only after the user chooses a mapped existing playbook, hand off to `ptsm-xhs-psychology` for psychology or `ptsm-xhs-topic-guide` for another existing playbook. Those skills collect the post brief and run their normal safe drafting flow.

## Guardrails

- Do not copy collection, scoring, clustering, or routing logic from PTSM into this skill.
- Do not generate or publish posts from this skill.
- Do not expose raw feed ids, xsec tokens, raw URLs, authors, or source bodies.
- Do not call `run-playbook` from this skill.
- Do not describe a partial scan as all-platform.
- Do not turn an `operator_headline` into a draft scene or copy it into a generation handoff.
- Do not invent a playbook fit, a static keyword list, or a new domain from insufficient evidence.
