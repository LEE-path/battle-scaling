# 单次表现因果审查

先确定这一次发生了什么，再决定这次表现能用于哪些结论。`feat_audit.run(request) -> dict` 只核结构、来源引用/可读性和显式前提；不看图、不读原作语义、不认证作者，不从“喘气”“怒吼”“失败一次”等字符串自动识别疲劳或全力。它不新增物理公式和量级，数值计算仍交给现有 `physics` / `derivation`。

离线入口：`python scripts/battle.py feat --input PACKET.json`；也可直接运行 `python scripts/feat_audit.py --input PACKET.json --output REVIEW.json`。例子见 [纯合成审查包](../assets/cases/feat-review-synthetic.json)，不代表任何真实作品。

## 单次发动与作用前后分层

先按[通用原则](scaling-principles.md)确定待证命题。此模块审事件因果，不要求所有身份、静态构成和可靠能力定义都伪造一次发动；下列动作与例子均非封闭能力列表，条件只在相应推论中使用。

本页的单次输出指一次行动、一次主动能力发动或一次可辨识被动触发及其有效结果，包括物理攻击、装备、创造、修复、重建、控制、转化、删除、因果／信息／叙事改写等；不限一拳、一次物理爆炸或焦耳值。`event.observed_output`、`effort.actual_output`及因果链同样记录非伤害、非能量效果；按[非伤害作用定档](rating-card.md#创造修复与全域转化)核完整对象与实现程度，材料无关时不强填材料或虚构能量换算。

存在拉入、降格、封印、改写属性或编排结局时，按实际因果拆开：**作用前的对象／本体与状态 → 发动、纳入及权限变化 → 作用后的身份与属性 → 内部动作和最终结果**。逐段标明施术者、装备／外援归属、目标的独立定档、抗性、持续和解除／回投条件。复合发动的多个环节分别核证，不将每一环都假定无限或同档。

例如，高档对象先被纳入故事、限制或重写属性，再以嫌疑人身份被子弹杀死：前段纳入／降格／编排须按原对象及其被突破的抗性评机制输出；后段枪击记录故事内身份下的结果。不能只据最终“枪杀”画面把施术者综合定成普通人，也不能据此证明原态肉身被普通枪口动能击穿。要核死亡能否回投本体、是否仅投影／暂时形象、是否确实由该角色编排；可见表象不代替这些桥。

## 输入契约

新请求 `mode` 使用 `integrated`（默认）；旧 `normal/highest/lowball` 只兼容读取历史资料，三类表现依[综合规则](modes-scaling.md)记录，不分别定角色档位。`requested_uses` 默认只含 `observed_output`；只补实际需要的用途，不能为了普通直接表现而强制填写全部材料、全力和全盛条件。未知不填零，暂缺材料不清空已记录输出。

统一 claim：

```json
{
  "status": true,
  "basis": "observed",
  "reason": "宿主读到的具体事实、推测理由及其适用范围",
  "source_ids": ["s1"],
  "evidence_claim_ids": [],
  "assumptions": []
}
```

`status` 必须是真正的 `true` / `false` / `null`；不能用字符串代替。缺失或 `null` 是未知。`basis` 支持 `observed`、`measured`、`documented`、`estimated`、`assumed`、`host_interpretation`、`author_statement`、`narrator_statement`、`character_statement`、`reasonable_inference`、`unknown`。明确值须有具体 `reason` 和可读来源；来源可经 `evidence_claim_ids` 继承。合理估计/假设/宿主解释保留 `conditional`，不是伪装成测量。未知前提附局部 `assumptions` 可形成条件估计；已知 `false` 不能被假设或最高口径覆盖。

`sources` 为数组或以 ID 为键的映射。每条源至少有 `id/title/origin/access/locator`，映射形式的键为 ID。`title/origin` 为非空文字，`locator` 可为非空文字或 `{chapter,page,panel/PTS}` 等非空定位对象，`event.locator` 也支持这两种形式。来源可读状态严格共用 `pk_modes.READABLE`：`verified`、`provided`、`indexed`、`read`、`verified_via_host_browser`。`indexed` 仍只代表已读索引的相应部分，不是读过完整原作；这些元数据均由宿主提供，工具不会替它认证。未知引用 ID 是输入错误，`blocked` 等不可读源阻断依赖它的用途；定位/来源身份信息不足为 `undetermined` 并产生补证任务。

| 区域 | 字段与用途 |
|---|---|
| `event` | `actor_id`、`version`、`state`、`locator`、`description` 是这次事件的明确文字范围；`observed_output` 是“该范围内确实出现此输出”的 claim。 |
| `causal_chain` | `action` → `transmission` → `target_response` 分写动作、传递与响应；`attribution` 是该记录输出能归属于此角色当次行动的 claim。 |
| `causal_chain.confounders[]` | 每项为 `{kind,description,accounted_for:claim}`；kind 为 `pre_damage/environment/external_energy/other_actor/other`。出现混杂时另需 `incremental_effect_isolated` claim，区分原有损伤、环境/外源贡献与角色新增贡献。不能把预裂、集火或储能的全部结果归给这一击。 |
| `actor_state` | 可分别记录 `fatigue`、`injuries`、`resources`、`form`、`prime_condition` 等 claim；`reason` 说明每项命题，保留当时资源、伤势、形态与全盛情况。这里的 false 是否定状态事实，不是“审查前提失败”。 |
| `combat_intent` | `killing_intent`、`will_to_fight`、`holding_back` 分别记录杀意、战意和留手命题，不把它们与疲劳、全盛或实际出力合并。无杀意不等于半力；高战意不证明全力。 |
| `effort` | `actual_output` 用文字记录这一次实际行为/输出；`full_effort` 单独论证在此次形态、资源、机制与招式范围内是否尽力。全力不等于全盛。工具不由表情、失败、疲劳自动判满力；不读取 `actual_output_fraction` / `percent` 来倒推满值，传入这些字段只记录未使用提示。 |
| `materials[]` | 每项需唯一 `id`，可列 `identity_candidates`；`identification`、`geometry`、`properties`、`property_match` 是 claim。`condition` 包含具体 `description` 和 `accounted_for` claim；description 应记录裂纹/预损、层、厚度、支承、受力位置、受潮/温度等相关工况。物性必须匹配材料、受力机制与工况，不把外观类似当成材性相同。 |
| `state_transfer` | `target_state` 明确所评状态，跨版本时补可选元数据 `target_version`；`compatible` 论证当次状态到该状态能否传递，以及有无相关伤势/资源/形态/机制变化。理由可给条件范围；工具不按疲劳自动折扣或补满数值。 |
| `upper_bound` | `scope` 明确只约束哪项能力、招式、目标与配置；`failure_observed`、`opportunity`、`same_configuration`、`mechanism_applicable` 都是 claim，并且必须满足此次 `effort.full_effort` 以及本次事件/因果归因审查。单次未破坏不能直接变成全盛/全招式的上限。 |

宿主须主动寻找未列出的混杂、反证和替代解释。工具不会根据未列 `confounders` 自动证明“没有混杂”；这也不是对裸布尔值做原作真实性认证。

## 证据性质账本

`evidence_claims[]` 每项有唯一 `id`、`kind`、`source_ids`、可选文字 `reason`，并由需要它的 claim 的 `evidence_claim_ids` 引用。只审被使用的证据主张；未被使用的条目可保留为线索。原始记录和审查前提分开，工具不会因为标记了某种 kind 就赋予该记录权威。

| kind | 需要的 `checks` claim |
|---|---|
| `direct_observation` | 宿主读到的动作/响应，附原页/画格/时间定位；不额外声称模型已读图。 |
| `author_statement` | `identity_verified`、`original_context`、`version_applicable`、`serious`、`consistent_with_original`。逐项核作者身份、原帖上下文、适用版本、严肃/玩笑及与原作冲突。 |
| `narrator_statement` | `scope_applicable`、`knowledge_sufficient`、`consistent_with_original`；考虑旁白的叙述层与知情范围。 |
| `character_statement` | 上一行三项加 `independent_corroboration`；角色说“我尽全力了”本身不客观证明全力。 |
| `reasonable_inference` | `premises` 数组列统一 claim；`checks.alternatives_considered` 记录已考虑替代解释；可另列 `assumptions`。即使全部前提获包内支持，推测仍为 `conditional`。 |

作者身份未核的截图可以作为待核线索，不能获得作者权威，连给 `identity_verified` 填假设也不行。若原文内容本身有推测价值，另建非权威的 `reasonable_inference`，写明前提和替代解释；不能把作者认证缺口藏进激进解释。已知与原作表现冲突的权威/陈述前提为 false 时，依赖它的用途阻断，遵守表现高于冲突设定。

## 输出与用途准入

返回 `schema_version/engine/operation/id/mode/status`、原 `event`、`recorded_context`（完整保留因果链、实际输出、状态、材料与用途范围）、`ledger`、`evidence_claims`、`issues`、`research_tasks`、`conditional_branches` 和 `validation_scope`。`admissions` 仅含请求用途，每项均有：

```json
{
  "status": "conditional",
  "reasons": ["依赖哪些命题、缺口或已知反例"],
  "assumptions": ["具体条件，不能只写一切成立"],
  "source_ids": ["s1"]
}
```

| status | 含义 |
|---|---|
| `supported_by_packet` | 包内来源/显式前提通过工具检查；不是工具认证原作事实或作者。 |
| `conditional` | 明确估计、解释或局部假设，可在交付中保留为有条件的结论。 |
| `undetermined` | 关键前提尚未知，不能静默当真。补证任务给出目标路径、待查问题、完成标准及宿主执行者。 |
| `blocked` | 所需前提明确 false，或依赖来源不可读。任何模式不能改写。 |

`observed_output` 是当次状态的物理或机制输出归属；`material_model` 是特定材性/工况能否用于计算；`full_effort` 是这一次是否尽力；`state_transfer` 是向所评状态迁移；`upper_bound` 是失败能否约束所评配置。它们分别判定，例如材料失配会阻断 `material_model`，同时保留已观察的裂纹或机制效果。总 `status` 是已请求用途中最受限制的状态，不应取代各用途判定。

未知可另列 `conditional_branches`，`admitted:false`，只说明未来须成立的假设；不替换主 admission，也不形成另一套角色最高档。已有 false 或不可读来源的用途不会生成越过它的条件分支；高光、通常、低谷任何视角都不从一次失败补出上界前提。

## 与 CASE 的绑定

CASE 在 `feat_reviews` 中存 `{id,modes?,request}`；分析器按本次综合请求注入 CASE 的 `sources` 与 `mode`，本模块本身不修改 CASE 传播。锚点、传播边和定性主张用 `review_requirements:[{review_id,use}]` 绑定具体审查用途，不能仅把审查结果附在报告里却不约束结论。

CASE 中角色 ID 必须匹配 `event.actor_id`。锚点的版本/状态文字与事件不同，须额外引用同一 review 的 `state_transfer` 用途；不能依靠字符串相似或同义词猜测兼容。若真实等价，由宿主写明并以 `compatible` 论证。能力上限 `upper` 锚点必须约束相应 `upper_bound`；仅表示单次测量上界时显式用 `claim_scope:"event"`，不升为状态最大能力。材料反算须约束相应 `material_model`。CASE 默认为未判定用途关闸；宿主要保留未证分支，须在 requirement 中明确 `allow_unproven:true` 并附具体 `assumptions`，形成可见的条件路径。`blocked` 始终禁止。

state_transfer目标默认取锚点/主张subject或叠边to.subject；迁移针对边另一端时显式填 `state_transfer.target_actor_id`。target_state与跨版本target_version须对应实际目标配置。身份与机制延续仍需compatible举证。详见 [CASE 格式](case-format.md)。
