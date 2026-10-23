# 表现计算与叠链的绑定审查

在已有公式计算、综合传播和高层类型分析上增加一层调度：把“算得出来”与“这项表现能否归属于该角色、该属性”分开。需要从画面参数推算、审核长叠链或复核高层映射时按需调用；普通有明确原作数值的评级不必先填完整物理表。

本层不装载九个外部项目的模型。吸收的实现目的：

- [OmniBattle](https://github.com/Zerhal/omnibattle-ai)：分阶段处理检索、速度、特殊能力和证据；本层把缺的前提变成补证任务，不采用 Wiki 档位捷径。
- [Cited Feats](https://citedfeats.com/) 与 [Animal Battle Stats](https://github.com/RamiNoodle733/animal-battle-stats)：出处定位、直接表现/推断与测量/估算分类；本层保留页、格、PTS、参数依据，不继承排名和胜率。
- [QuantiPhy](https://github.com/Paulineli/QuantiPhy)、[MangaLMM](https://github.com/manga109/MangaLMM)、[ManGo](https://arxiv.org/abs/2608.29865)：已知比例条件、观测与推断分离、按缺口选择下一份证据；本层只调度宿主已有视觉与研究能力，不声称自动分格、识物性或获得完整物理求解器。

新单次表现先按 [feat-review.md](feat-review.md) 审实际因果归属、出力/状态和材料工况，再把可用参数送本层。CASE的计算attach锚点也可携带review_requirements，analyze在真实计算后按用途准入筛选；数值算得出来不绕过材料/归属审查。把失败作为能力上限时单独请求upper_bound；已测单次做功不需要先证明全力。

未复制候选项目代码。现有物理公式、有限册规则和高层类型分析仍分别由 [physics-models.md](physics-models.md)、[evidence.md](evidence.md)、[high-tier.md](high-tier.md) 负责，不新增或偷换汪吧门槛。

## 入口与状态

```python
from derivation_audit import run
result = run(request)
```

```powershell
python scripts/derivation_audit.py --input request.json --output audit.json
```

支持 `operation: physical | chain | high | bundle`；新任务通用 `mode: integrated`（默认），高层子请求同步该综合口径。旧 `normal/highest/lowball/all` 仅用于历史读取或旧结果复算，不证明综合选档完成；三类表现按[统一综合规则](modes-scaling.md)进入同一推导账本。

结果共有 `issues`、`research_tasks` 和 `validation_scope`。状态含义：

| 状态 | 含义 |
|---|---|
| supported_by_packet | 该包中的结构、引用及已填写条件通过检查；不表示脚本联网核实了原作或证明了语义 |
| conditional | 保留可用条件结果，并明确待查参数、来源或桥接 |
| blocked | 有明确反例/假前提/物理量类型冲突，该路径不能纳入；原始情景数值可保留供审计 |
| invalid | 输入格式、引用或底层类型计算无效；CLI 退出码 2 |

社区摘要、索引和转述可参与明示的暂定估计，不因尚未核到 primary 一律丢弃。它们不会升级为已核原作。综合分析可保留有据但未证的条件分支，不能把已知 `false` 改成 `true`。缺参不填零，数值区间不充当高光、通常或低谷战绩。

可读元数据与 PK 共用 `pk_modes.READABLE`：verified、provided、indexed、read、verified_via_host_browser。community/indexed 可做条件参考，不要求所有参考都为 primary；downloaded 只表示下载，blocked/not_found/unread/unknown 或缺访问状态不能支持可导入锚点、有效继承边或 admitted_mappings。仍返回情景计算、原始高层分析和补证任务，不把未读资料中用户填下的 true 升级为已采纳前提。

## 物理表现包：physical

核心字段：

```json
{
  "operation": "physical",
  "id": "work-version-event",
  "mode": "integrated",
  "sources": [
    {"id": "scene", "title": "原作场景", "origin": "primary", "access": "verified",
     "locator": {"chapter": 10, "page": 8, "panel": 2}},
    {"id": "material", "title": "物性资料", "origin": "primary", "access": "read",
     "locator": "表号、温湿度、试件方向、页码"}
  ],
  "observations": [
    {"id": "o1", "source_ids": ["scene"],
     "locator": {"page": 8, "panel": 2, "bbox": [10, 20, 80, 90]},
     "visible_fact": "只写图中确实可见的动作",
     "interpretation": "和可见事实分开的物理解释",
     "unknowns": ["镜头深度未知"], "image_sha256": "实际原图哈希"}
  ],
  "calculation": {
    "model": "kinetic", "inputs": {"mass": 2, "speed": 3},
    "intervals": {"mass": [1, 3], "speed": [2, 4]}
  },
  "parameter_bindings": {
    "mass": {"source_ids": ["material"], "basis": "estimated",
             "reason": "展示该质量范围为何适用于场景"},
    "speed": {"source_ids": ["scene"], "observation_ids": ["o1"], "basis": "measured",
              "reason": "同平面尺度与实际PTS的测量过程"}
  },
  "model_conditions": [
    {"name": "physical_translation", "status": true, "source_ids": ["scene"],
     "reason": "排除瞬移、镜头移动和表现性画面后仍成立"}
  ],
  "target_anchor": {"id": "c1", "subject": "character-state-id",
                    "version": "指定版本", "state": "指定状态", "attribute": "raw_energy"}
}
```

上例数值是公式基准夹具，不是某角色战绩。`calculation` 直接使用既有 `physics.calculate` schema；`parameter_bindings` 按实际输入名绑定，`basis` 只能为 measured/documented/estimated/assumed。做功采样曲线用 `samples[0].force`、`samples[0].displacement` 等路径。估算参数给有根据的区间或 `range_justification`；不能把未知木材、手部力臂和有效接触面积写成实测。

输出新增：

- `calculation_request` 与 `calculation`：真正执行的请求、步骤、数值、单位、区间情景及底层适用限制。
- `parameter_ledger`、`observations`、`model_conditions`：每个值和条件连到哪些资料/画面。
- `anchor_candidate`：可审核后导入 CASE 的候选。始终保留版本、状态、证据和量纲；不在本层偷偷定档。

既有断裂计算的主结果是临界应力 Pa，另有 `nominal_force` N 和可选的断裂功。需要其中一项时设置 `result_path: ["nominal_force"]`（相对底层 `result` 的键路径），结果在 `selected_quantity` 中返回；有区间时重新计算所选子物理量的各角点到 `selected_sensitivity`，不会给原应力数值换一个牛顿单位。选不到真实计算字段就报 invalid。

`raw_energy/raw_force/raw_torque/raw_work/raw_speed/raw_pressure/raw_quantity` 表示原始物理量。若目标是 AP、体防或其他战斗属性，另给：

```json
{"transfer": {"status": true, "source_ids": ["scene"],
  "mechanism": "证明能量由该角色输出或由其本体承受；说明实际耦合与损失",
  "scope": "这一次、这一状态、这一机制", "reason": "原作和计算间的桥接"}}
```

缺桥接时仍返回数值和补证任务，但不产生该属性锚点。力 N、力矩 N m 不能直接重新命名为 J 或输出档；即使量纲相似也不自动转化。`raw_quantity` 仅保留带单位的原始结果，不能借此跳过后续属性定档审查。质能转换、爆炸相似率和断裂模型仍受既有公式的专门适用条件约束。

最后把审核通过的候选送既有 CASE/evidence 与册中多条件规则；能量账面值、破坏尺度、释放方式和稳定性要一起评定。不能用几焦耳的浮点结果直接替代“爆×”的原册条件。

## 叠链包：chain

`case` 采用已有 [case-format.md](case-format.md)，不另建与旧证据图冲突的格式。`hop_audits` 对每个 `edge_id` 追加：

```json
{
  "edge_id": "tank-001",
  "from": {"state": "攻击发生时状态"},
  "to": {"state": "受击时状态"},
  "mechanism": "实际有效命中、无盾/免疫/卸力，继承的是特定机制体防",
  "scope": "明确该攻击的实际规模和承受比例",
  "conditions": [
    {"name": "state_compatible", "status": true, "source_ids": ["s1"]},
    {"name": "scope_compatible", "status": null, "source_ids": ["s1"]}
  ],
  "counterexamples": [
    {"status": "unresolved", "source_ids": ["s2"], "reason": "此前类似攻击曾被特殊盾化解"}
  ]
}
```

`from/to` 的 subject 与 attribute 不可悄悄改成另一个对象；若要新关系，应新建 CASE edge。状态、版本、装备变化需要连续性/可比性的证据。`counterexamples.status` 为 confirmed/unresolved/resolved，resolved 另给有来源的 resolution；激进解释也不能绕过已确认反例。

输出 `hop_ledger` 展示每跳源/目标属性、各自状态、来源、条件、机制、范围和反例；`effective_case` 是去掉明确受阻路径、把未知桥接写入假设后的 CASE；`chain_analysis` 调用综合传播器，证据视角与条件分别保留但角色主判统一；`cycles` 指出循环并要求独立锚点。

一个受阻分支不会抹掉角色已独立成立的表现。未知桥接保留条件分支；传播仍须按[综合选档](modes-scaling.md)比较全部重要候选，本层不强迫其把证据不足的边变成已证事实，也不能把最高数值或最低地板直接当成完整主档。最强声明的领域、属性覆盖、阶段、反例需逐项保留，不能“打赢某人”就继承其体量、智力、速度和全部能力。

## 高层证明账本：high

输入 `high_request` 是既有 typed analyzer 的原请求；`proof_bindings` 只补原生节点的解释桥接：

```json
{"operation": "high", "high_request": {"kind": "native", "nodes": []},
 "proof_bindings": [{"node_id": "existing-node",
   "source_locator": "原文定位", "object_type": "作品原生closure或标准cardinal等",
   "interpretation_bridge": "原句为何能解释为该对象；不成立的替代解释也列出",
   "domain": "量词及闭包作用域", "assumptions": ["背景公理或语义条件"],
   "rule_id": "选用的具名册/历史标准", "contradicted": false}]}
```

上例仅展示字段，实际 nodes 必须满足原分析器要求。输出 `high_analysis` 是底层真实结果；`proof_ledger` 把来源→原生操作→数学对象→具名规则分开；`admitted_mappings` 是可纳入的条件映射。若解释被明确反驳，原始计算保留用于审计，但 `admitted_mappings` 清空，不能把原始输出重新表述成采纳结论。

借用“分阶段审查”思想，不改变已有数学定义和册中规则：

1. 先核原文、版本、符号及作用域；有限序列不冒称已到极限，“全部”不自动包括未定义对象域。
2. 有标准数学解释时，交 typed analyzer；CH/GCH、基数与序数、作品 Φ 与 Veblen φ 分开。理论、真类、叙事层级不输出伪焦耳。
3. 映射必须写具名规则及来源。VSB Tier 0、总排行和“无穷超越”的词语不能替代汪吧或基数证明。
4. 角色达到/看见/存在于结构，与创造/摧毁/控制/承受结构分别举证。世界观等级不自动变全属性 AP。
5. 对内置算术外的对象，继续查定义与数学论文，给原生偏序、条件界和待证桥接，不称已自动形式化全部作品叙事。

## 补证任务如何真正推进

每条 `research_tasks` 有稳定 task_id、kind、query、target_path、required_fields、completion_criterion、source_ids、executor。脚本不自己联网或调用模型：宿主把 query 交搜查工具，把图格任务交实际视觉，把原始材料与结果回填；完成标准是来源支持/反驳了具体前提，不是“搜索有结果”。

优先补会改变主判的缺口，再补数值精度。对小说仍按结局统一配置、每项由后往前找；检索与图像结果不是新的作品事实，必须保留来源类型。重复同一失败入口而无新线索时停止该入口，转别的资料渠道并保留条件结论。不要把“执行器返回缺资料”当作用户需求已完成，宿主要继续执行必要检索。

`bundle` 可含 `physical`、`chain`、`high` 三个子请求，按需调用，不要求每场 PK 都加载三套账本。宏观胜负与具体战斗轨迹引用这些审核结果；轨迹故事不能回流为新的表现证据。

## 已验证与实际边界

新测试覆盖真实公式的 2 kg、3 m/s → 9 J 恒等式与区间角点、来源不明的暂定保留、缺参任务、False 在条件推导中仍受阻、力矩不能充能量、属性桥接、逐跳反例与循环、既有旧神盒案例的条件规则映射及旅行不转 AP。测试夹具只验软件，不充当角色原作。

既有案例演示应同时保存请求与输出：地球均匀球引力束缚能只是物理参照；美队掰木头的条件断裂载荷仍不是输出能量；旧神盒的具名历史规则映射仍不替未指明角色授予 AP。旧案例只有 archived/free-text访问说明而无可读元数据时，原始情景仍保留，admitted 输出暂空，待实际回读或显式标注已读索引后再审；不能为了让旧演示通过而自动改成 verified。能正确提示这些边界，比无条件给三者同一条数值档位更符合用户的可追溯目标。

此层没有部署外部模型，没有自动掌握所有树种/材质，没有在离线状态读取新原作，也没有证明所有叙事结构的形式一致性。宿主具备的搜索、视觉和数学工具负责实际执行，账本负责不让来源与前提丢失。
