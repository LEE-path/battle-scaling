# VSB：特殊能力、抗性与 NLF

仅 `standard: "vsb"` 使用本规则；默认汪吧仍使用 [双上限](hax-ceiling.md)。VSB 不是换档名：**不机械套用“不得超过原世界最强角色”上限，也不拿施术者 AP 给每种特能封顶**。低 AP 的能力可以有依据地影响高 AP 目标；同时，高 AP 目标也不自动抵抗一切特能。是否奏效由能力本身的机制、强度、射程、作用尺度、目标性质及对应抗性决定。[Hax](https://vsbattles.fandom.com/wiki/Hax?oldid=9692470)、[Resistance](https://vsbattles.fandom.com/wiki/Resistance?oldid=9313371)

## 必查项

1. 查该版本**真实成功、失败和受限表现**，区分施术者本体、特能、载体、特能增幅与控制熟练度。泛称“更强/能力更大”不自动提高每项特能强度。
2. 查作用对象及可触达的方面：物质、脑、非物质心灵、灵魂、概念等不可只凭同名互换。范围、面积和 potency 分开；覆盖更多目标未必提高对单体的效力。
3. 分开比较发动/命中、对象兼容、抵抗机制、强度、持续与射程。只绕过部分体防的穴位/内脏攻击，仍可能因巨大体防差失败；完全绕体防的能力也须触达相应目标。数值无限差、真正高维存在、质性 R>F 不能合成一个“高一级就免疫”规则。
4. 层数须有实际突破对应抗性的表现；变强、烧得更热、额外的抗性无效化机制不直接算同一类叠层。**跨作品层数不是通用单位**，100 层不能只凭数字判压过另一作品 1 层；机制或强度因子互有优劣而无法比较时保留未决。名为“免疫”也须核其依据及能否被强行赋予所缺的作用方面。
5. 击败对手不等于抵抗其全部能力，力量更强不自动继承所有抗性；需原作继承桥。没有列出层数不代表没有相应表现；没有反例不等于无限有效。[Fallacies §16](https://vsbattles.fandom.com/wiki/Fallacies?oldid=9363140#16._No_Limits_Fallacy_(NLF))

合理世界观等化只让**相近且机制兼容**的超自然系统可交互；不增加/删除固有能力和抗性，不移除有效、未矛盾的能量差门槛或其他弱点。具体见 [VSB 对战](vsb-combat.md)。

## 可运行门槛

`scripts/vsb_hax_policy.py:run(request)` 审核宿主提供的原始主张包，不读取原作、不证明语义、不生成胜负。`hax_gate` 按所选 standard 路由；不得提交现成 `status`、`research_tasks` 或 `source_access_checked` 冒充已审结果。

```json
{
  "ability_id": "角色A-特定能力",
  "actor_id": "A",
  "target_id": "B",
  "mode": "integrated",
  "sources": [{"id": "原作片段", "access": "read", "origin": "primary"}],
  "effect_evidence": {
    "ability_id": "角色A-特定能力",
    "basis": "demonstrated",
    "statement": "填写该能力实际做到了什么，并绑定具体出处。",
    "mechanism": "填写实际机制及已知限制。",
    "source_ids": ["原作片段"]
  },
  "target": {"description": "目标相关生理、存在或能量性质及出处。", "source_ids": ["原作片段"]},
  "checks": {
    "object": {"state": "unknown", "explanation": "该作用对象是否存在、可触达？"},
    "compatibility": {"state": "unknown", "explanation": "等化是否合理、机制是否兼容？"},
    "activation": {"state": "unknown", "explanation": "发动、射程、命中、成本条件是否满足？"},
    "resistance": {"state": "unknown", "explanation": "双方对应机制、强度及抗性实际表现如何比较？"},
    "no_limits": {"state": "unknown", "explanation": "此次外推是否有实绩或机制依据，是否超出已知硬限制？"}
  },
  "effect_scope": {
    "description": "实际影响目标与范围。",
    "range_interaction": "当前距离、维度及覆盖如何满足能力范围。",
    "resistance_interaction": "具体抗性及对应能力如何交互。",
    "source_ids": ["原作片段"]
  }
}
```

上例是**待填模板，不是通过包**。`effect_evidence.basis` 可选 `demonstrated`、`supported_mechanism`、`supported_scaling`；后两者仍须给可读依据。五项 check 均用 `state: pass/fail/unknown` 与明确 `explanation`；`pass/fail` 绑定各自 `source_ids`。`unknown` 只有附具体局部 `assumption` 才成为条件前提，不能给全局一句假设来填掉缺失的能力/目标/范围证据。

输出 `supported_by_packet / conditional / blocked / undetermined`，附 `source_ids/reasons/assumptions/research_tasks/mechanism_trace`。已知且有可读依据的失败优先阻断，高光／低谷视角和假设都不能覆盖；评级按[统一综合主档](modes-scaling.md)处理。只有索引、抓到未读、blocked/error 或失联来源不能放行；实际已读正文标 `read/provided/verified/verified_via_host_browser`。`original_source_verified:false` 始终提醒程序没有替宿主认证原文。

规则快照核读日：2026-10-21（客户端日期）。原站公开 API 全文已核，revision：Hax 9692470、Resistance 9313371、Fallacies 9363140。规则可更新；遇该领域的新修订时核指定现行条款，不以旧搜索摘要覆盖本轮正文。这里是方法摘要，不承诺已内置每一种独立能力页面。
