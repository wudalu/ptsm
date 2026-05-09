# Modern Psychology Domain Research Notes

Date: 2026-05-09

## Goal

调研是否值得为 PTSM 增加一个心理学 / 心理问题探索领域，并把结论转成可执行的产品设计输入。

本研究关注的是内容产品方向，不是医疗产品设计。推荐方向是“现代心理困境观察”：用心理学框架解释当代人的压力、关系、孤独、数字生活和自我成长问题，但不做诊断、治疗、药物、危机干预或替代专业服务。

## Current PTSM Baseline

PTSM 当前已经具备新增内容领域的基础条件：

- `playbook` 是业务编排单元，负责绑定领域、平台、技能、人设和反思规则。
- `SkillSelector` 可以按 domain / platform / playbook tags 暴露小范围 builtin skills。
- `xhs_trend_scan` 和 `topic_research` 已经能把小红书站内趋势、topic-radar artifact 注入 planner。
- `topic_radar` 现有 fallback 聚类里已经包含 `情绪疗愈`、`轻养生`、`打工人日常` 等相邻垂类。
- `docs/xhs-topics/verticals.md` 已把“修复系手作 / 情绪疗愈”和“轻养生 / 睡眠恢复 / 办公室健康”列为优先方向。

这意味着心理领域不需要先改运行时。第一阶段更适合通过新 playbook、少量领域 skills、账号定义和内容安全约束接入。

## Source Summary

### Global Mental Health Demand

WHO 2025 年 mental disorders fact sheet 显示，全球接近七分之一人口生活在心理障碍中，焦虑和抑郁是最常见类型。WHO 同时强调有效预防和治疗存在，但有效照护可及性不足。这说明大众心理健康内容存在长期需求，但内容必须避免把科普替代治疗。

Source: <https://www.who.int/news-room/fact-sheets/detail/mental-disorders>

### Workplace Stress Is A Core Modern Scenario

WHO 2024 年 workplace mental health fact sheet 把歧视、不平等、工作过载、低工作控制感和工作不安全感列为工作心理健康风险，并估计 2019 年工作年龄成年人中 15% 有心理障碍。它还指出抑郁和焦虑每年带来大量工作日损失和生产力成本。

Source: <https://www.who.int/news-room/fact-sheets/detail/mental-health-at-work>

Product implication:

- 职场心理不是小众内容，是第一优先切口。
- 推荐主题：倦怠、低控制感、冒名顶替、边界感、绩效焦虑、下班后反刍。

### Loneliness And Social Disconnection Are Durable Topics

WHO 2025 年 social connection Q&A 显示，全球约 1/6 人报告孤独，年轻人尤其突出。孤独被定义为主观上“已有连接”和“想要或需要的连接”之间存在落差。

Source: <https://www.who.int/news-room/questions-and-answers/item/social-connection>

Product implication:

- 关系与孤独可以成为第二内容支柱。
- 内容应从“你是不是有病”改为“为什么你会在关系里这么累”。

### Young Adults Are A High-Signal Audience

NIMH 基于 2022 年 NSDUH 数据指出，美国 23.1% 成年人有 any mental illness，18-25 岁年轻成年人比例最高，达到 36.2%。这不是中国市场数据，但能辅助判断：年轻人对心理健康、情绪调节、自我理解类内容有更高基础需求。

Source: <https://www.nimh.nih.gov/health/statistics/mental-illness>

### China-Specific Signals

中国科学院心理研究所与社会科学文献出版社 2025 年发布《心理健康蓝皮书：中国国民心理健康发展报告（2023-2024）》。公开报道提到，项目采集逾 17 万份问卷；成年人的抑郁和焦虑风险总体随年龄增长而降低；城市人群焦虑风险显著高于农村人群；工作时间超过 10 小时者抑郁风险较高；高强度短视频使用与抑郁、焦虑风险显著相关。

Source: <https://www.cas.cn/cm/202504/t20250418_5064632.shtml>

Product implication:

- 城市年轻人、职场人、大学生是小红书心理内容的高相关人群。
- “短视频停不下来”“睡前越刷越空”“信息过载”应作为数字生活心理支柱。

### Social Media Needs A Safety Boundary

U.S. Surgeon General 2023 advisory 指出，青少年社交媒体使用几乎普遍，同时社交媒体既有益处也有心理健康风险，不能简单断言其对儿童青少年足够安全。

Source: <https://www.hhs.gov/surgeongeneral/reports-and-publications/youth-mental-health/social-media/index.html>

Product implication:

- 该领域不应做鼓励沉迷、比较焦虑或自我诊断的内容。
- 涉及青少年、自伤、自杀、成瘾、严重失眠等主题时，应触发更严格安全话术。

### Consumer And Platform Direction

QuestMobile 2026-03-31 发布的 2025 中国营销市场洞察提到，用户进一步转向内在价值投资，更关注自我成长、身心健康与个体情绪感受；情绪消费、体验消费、健康消费等成为重要驱动力。

Source: <https://www.questmobile.com.cn/research/report/2038888455543558145/>

Product implication:

- 心理领域不应只做知识解释，还应提供情绪共鸣、体验感和可执行的小行动。
- 小红书表达应偏“场景化、陪伴式、可收藏”，而不是学术讲义。

## Recommended Positioning

推荐领域名：

```text
现代心理困境观察
```

一句话定位：

```text
把现代人的焦虑、孤独、内耗和关系困境讲清楚，但不把读者病理化。
```

账号人设：

- 有心理学素养的观察者，不是诊断者。
- 像一个读过研究、也经历过现代生活压力的朋友。
- 能把专业概念翻译成生活语言。
- 重视边界：科普、识别、行动建议可以做；诊断、治疗、药物和危机处理不做。

## Content Pillars

### 1. 职场心理困境

目标用户：城市职场人、初入职场年轻人、长期加班者。

典型主题：

- 倦怠不是单纯懒，而是长期消耗后的系统报警。
- 下班后还在复盘白天那句话：反刍思维。
- 为什么你一被催就脑子空白：压力下的执行功能。
- 冒名顶替感：为什么越优秀越怕被发现“不够好”。
- 边界感：为什么拒绝别人会有罪恶感。

### 2. 关系与孤独

目标用户：亲密关系、友情、家庭关系中高敏感和高消耗的人群。

典型主题：

- 别人不回消息，为什么你会开始脑补。
- 讨好型人格这个词被滥用了，真正需要看的是边界和恐惧。
- 为什么越长大越不想社交，但又害怕孤独。
- 关系里“冷下来”不一定是不爱，也可能是防御。
- 原生家庭内容要做，但避免宿命论。

### 3. 数字生活心理

目标用户：短视频重度用户、信息过载用户、创作者、学生和职场人。

典型主题：

- 睡前刷短视频停不下来，可能不是自控力差。
- 比较焦虑：为什么你看完别人生活更讨厌自己。
- 信息越多越难行动：选择过载和决策疲劳。
- AI 陪伴能缓解孤独，但不能替代真实支持网络。
- 多巴胺、成瘾、ADHD 等词要谨慎使用，避免伪科学和自诊断。

### 4. 自我成长与情绪调节

目标用户：想理解自己、改善生活秩序但不想听鸡汤的人。

典型主题：

- 情绪调节不是把情绪压下去。
- 为什么“松弛感”不能靠命令自己放松获得。
- 完美主义的底层不是追求完美，而是害怕犯错后不被接纳。
- 低成本恢复：睡眠、运动、人际支持、记录、环境整理。

## Content Format

推荐每篇固定成 5 段：

1. `生活场景`：先写一个具体场景，例如下班后仍在脑内复盘。
2. `心理机制`：解释一个概念，例如反刍思维、低控制感、边界压力。
3. `误区澄清`：不是懒、不是矫情、不是一句“想开点”能解决。
4. `轻量行动`：提供 1-2 个低风险行动，例如记录触发点、减少睡前刺激、向可信任的人求助。
5. `专业边界`：如果持续痛苦、功能受损、自伤想法或严重睡眠问题，应寻求专业帮助。

## Safety And Compliance Boundaries

必须禁止：

- 诊断化标题：如“你就是抑郁症”“三条判断你是不是双相”。
- 医疗承诺：如“这样做治好焦虑”。
- 药物建议：包括用药、停药、剂量、替代疗法。
- 危机处理替代：涉及自伤、自杀、严重创伤时不能只给内容建议。
- 滥用流行标签：ADHD、PTSD、人格障碍、双相、抑郁症等不能被娱乐化。

必须包含：

- “这不是诊断/治疗建议”的轻量边界表达。
- 对严重风险的求助引导。
- 以生活困境和心理机制为主，不把普通情绪直接病理化。

## Recommended PTSM Implementation Shape

第一阶段建议新增：

```text
src/ptsm/playbooks/definitions/modern_psychology_post/
  playbook.yaml
  planner.md
  persona.md
  reflection.md

src/ptsm/skills/builtin/psychology_style/SKILL.md
src/ptsm/skills/builtin/psychology_safety/SKILL.md
src/ptsm/skills/builtin/xhs_psychology_hashtagging/SKILL.md

src/ptsm/accounts/definitions/acct-psychology-local.yaml
```

推荐 `required_skills`：

```yaml
required_skills:
  - xhs_trend_scan
  - topic_research
  - psychology_style
  - psychology_safety
  - xhs_psychology_hashtagging
```

推荐 `trend_keywords`：

```yaml
trend_keywords:
  - 职场焦虑
  - 情绪内耗
  - 关系边界
  - 孤独感
  - 短视频焦虑
  - 睡眠恢复
```

如果 `trend_keywords` 扩展点尚未进入代码，先在 planner/persona 里写静态方向，不阻塞第一版 playbook。

## Evaluation Signals

第一版至少要检查：

- 标题和正文不包含诊断化承诺。
- 正文必须包含具体生活场景。
- 正文必须解释一个心理机制，而不是只共情。
- 正文必须包含一个低风险行动建议。
- 涉及严重风险时，必须引导专业帮助。
- 标签必须包含 `#心理学` 或 `#情绪管理` 之一。

## First Two-Week Experiment

建议用四组关键词跑内容实验：

1. `职场焦虑, 倦怠, 反刍思维, 边界感`
2. `孤独感, 亲密关系, 讨好, 回避`
3. `短视频焦虑, 信息过载, 睡前刷手机`
4. `情绪调节, 睡眠恢复, 低成本自救`

成功信号：

- 每组都能产出至少 5 个非重复选题。
- 评论区出现经验交换，而不是只打卡或泛泛共鸣。
- 内容不依赖热点也能成立。
- 安全规则能稳定拦住诊断化标题和治疗承诺。

## Decision

建议进入 PRD 作为规划中第五领域，状态标记为 `产品设计完成 / 待实现`。不建议把它并入 `fengkuang_daily_post`：发疯文学偏情绪宣泄，心理领域需要更严格的解释结构和安全边界，长期应独立成 playbook。
