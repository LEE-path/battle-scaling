# 可执行证据包

路径均相对本Skill；输出目录由本次任务指定。脚本是宿主Agent的工具，不能单独凭角色名取得原作并理解图片。宿主通过已实际存在的搜索/视觉工具搜证，再写下列packet。字段验证可运行battle.py validate；它验证结构、引用和数值，不验证引文语义真假。

```json
{
  "schema_version": 1,
  "case_id": "demonstration-not-canon",
  "fixture_kind": "synthetic",
  "characters": [{"id":"a","name":"示例角色","version":"回归夹具","state":"常态"}],
  "sources": [{"id":"s1","title":"合成证据","origin":"synthetic","access":"provided","locator":"测试事件1"}],
  "anchors": [{"id":"feat1","subject":"a","attribute":"attack_energy","kind":"repeated_feat","quantity":{"min":1800,"best":2000,"max":2400,"unit":"J"},"bound":"lower","evidence_ids":["s1"],"assumptions":["仅为工具示例"]}],
  "edges": [],
  "coverage": {"scope":"仅此合成夹具，不是原作"},
  "limitations": ["不能用作任何角色的战绩"]
}
```

characters每项必填id/name/version/state，补充work/continuity/period/equipment。ID为完整范围，不按姓名自动合并。

sources必填id/title/origin/access/locator；提供url或path、检索/版本日期、原文位置及媒体坐标。origin可用primary/community/measurement/assumption/synthetic；access填写verified/provided/indexed/blocked等；未读、blocked、unknown不建立锚点。indexed表示已读搜索索引中明确内容，必须说明未取得完整原页，不能冒称已读整章。

anchors.kind为repeated_feat/credible_feat/calculation/statement/outlier/anti_feat。quantity是{value,unit}或{min,best,max,unit}；bound为lower/upper/estimate。力N不转能量；能量转换支持J/kJ/MJ/GJ/kg_TNT/t_TNT/kt_TNT/Mt_TNT。新册直接`finite`工具接受十进制字符串；案例也可用数字串保留原输入，有限分档和传播倍率保留Decimal，路径选择及通用物理工具仍用有限浮点，不应声称无限精度。tier用{kind:"tier",ruleset:"具名规则",label:"档位",rank:该规则内序号}；rank仅用于同一规则下的比较，不是物理倍率。

案例顶层可加`ruleset_profile`；锚点或案例可加`tier_context:{"context":{...}}`；边可显式覆盖`tier_context`。新册默认对虚构表现同时检查能量、破坏尺度、材料、释放和多击条件；字段与例子见[量级册协议](handbook.md)。没有几何数据时保留能量参考，不伪造最终定档。计算的`attach`可直接带此条件对象。

edges每项含id、from:{subject,attribute}、to:{subject,attribute}、relation、evidence_ids、conditions；关系及条件见模式文档。用modes限制适用口径，assumptions保存激进前提。明确倍数再附multiplier与multiplier_evidence_ids。含upper的约束仅在明确bound_transfer:"upper"时按上界方向传播。

computations每项可写{id,type:"physics"或"high",request:对应工具输入}，analyze会真实运行并把输出及全部中间值写入报告。需要把数值用作锚点时附attach，包含普通anchor字段，再加result_path和unit；例如result_path:"result.value",unit:"J"。只有已经论证该计算属于此角色此属性时才attach。高层非标量输出保留在computations和qualitative_claims，不伪造数值锚点。

qualitative_claims按模式记录能力、证据、反例和条件；原文没有可测数值仍可完整评定。matchup及条件见matchups.md。禁止把仅有世界观、旅行能力或一次胜利的量级无条件附到全部属性。

新单次表现按 [feat-review.md](feat-review.md) 建立顶层 `feat_reviews:[{"id":"scene-review","modes":["normal","highest","lowball"],"request":{...}}]`。request中的event.actor_id须是本CASE角色ID；analyze按模式运行并用CASE的sources覆盖内层来源，不允许内层换来源或口径。锚点、叠边、定性主张以 `review_requirements:[{"review_id":"scene-review","use":"observed_output"}]` 声明依赖；use支持observed_output/material_model/full_effort/state_transfer/upper_bound，须已在request.requested_uses中请求。

同一事件的实际表现可以成立，而全力、材料或迁移用途分别受阻；只排除依赖受阻用途的结论。blocked不能被任何模式覆盖；undetermined默认不导入，合理估计conditional可保留并传播其前提。若要讨论未定的激进假设，显式设置该依赖的`allow_unproven:true`和非空`assumptions`另建条件分支，不能绕过blocked或将作者身份假设升级为已证。没有数值增幅依据，不根据疲劳/留手标签自动乘除。

锚点/定性主张的subject须对应review的actor_id，叠边须至少有该角色端点。事件version/state与所评角色不同，须额外绑定同review的state_transfer用途；同义名称由宿主先统一，字符串一致本身不证明语义相容。全力只针对事件当时状态；疲劳状态全力不等于全盛状态上限。

已绑定新审查的能力上限锚点（bound:upper）必须请求并依赖upper_bound；仅引用observed_output或full_effort不够。若评的是“这一次的测量上界”而非角色能力上限，用claim_scope:"event"明确标注，报告会保留该范围，不自动升为最大能力。跨状态的state_transfer.target_state必须是CASE实际目标state；跨版本时target_version也须对应目标version。

state_transfer的目标默认是锚点/定性主张的subject，或叠边的to.subject。若迁移只针对边的另一端，显式填state_transfer.target_actor_id（须是该边端点）。例如角色旧态ID→结局ID的迁移，应核对结局端的state/version，不能错误地与旧态端比较。身份是否同一角色、机制是否延续仍由compatible的证据与前提论证。

报告保存逐模式feat_reviews、review_trace、feat_review_coverage和独立feat-reviews.json及其哈希。未绑定审查的旧锚点保留兼容并列入unreviewed_anchor_ids，不能宣称新审核已覆盖。定性主张若提供evidence_ids，也必须引用实际存在的sources；合理推测的完整前提和原作语义仍由宿主核查。

新评特殊能力按 [双上限规则](hax-ceiling.md)，建立 `hax_checks:[{"id":"control-a-b","modes":["normal","highest","lowball"],"request":{...}}]`。request使用该文的完整请求，补 `actor_id:"a"`、`target_id:"b"` 和 `ability_id` 绑定实际施术者、实际受影响者与能力；两角色ID必须存在于CASE。每种目标档次、对象类型或状态分别建检查，不重用其他目标的通过结果。工具注入CASE.sources和当前模式，不能从内层request替换来源或模式；不接受预填的CASE.hax_results/hax_reviews。

凡依赖特能的锚点、叠边、定性判断、computation及其attach、win_path、路径requirement、mode_assessment和win_estimate，标记 `is_hax:true` 并填 `hax_requirements:["control-a-b"]`，多个ID按AND检查。计算生成的attach锚点继承父计算全部检查，不能通过换成计算结果丢掉特能限制；按模式保存获准计算hax_computations，受阻计算不再显示为已采用的角色或高层结论。必要时用 `ability_owner`、`affected_target` 明确能力归属与受影响对象；单人subject默认是归属者，叠边涉及不同属性或多角色时显式写清。宏观路径/主估默认归属winner角色，单挑默认作用于另一角色；借用伙伴能力、反弹或自我作用须明确归属与目标，队伍winner不能代替实际成员。通过上限审查只允许采用该用法，不自动创建能量或全属性继承边。blocked不导入；关键上限缺失或不可比的undetermined不导入；仅机制假设的conditional可保留并向后传播其前提。不能用最高模式、allow_unproven或assumed覆盖已知超限。

宏观路径缺检查只能作为待补条件，不能变成supported；主估依赖的特能也必须逐一绑定，受阻/未定时撤回winner和数值主估，不自动判另一方获胜。没有特能标记的旧项目兼容读取，但列入未审覆盖，不能以此声称已应用该规则。证据包语义与特能识别仍由宿主负责，工具不会从文字自动识别所有特能。

具体过程使用相同CASE.hax_checks；analyze向每模式过程注入，禁止在CASE的mode_processes内部另设hax_checks。独立 `process` 请求才在其自身顶层提供hax_checks。过程对实际动作/效果目标核对绑定，并将父级检查继承到子效果、延迟、持续和到期效果；恢复先审查再消费次数或排队。详见 [过程协议](combat-process.md)。

报告逐模式保存hax_reviews、hax_review_coverage和结论hax_trace，独立 `hax-checks.json` 保存检查结果、评级/PK/过程覆盖及过程各点采用记录；manifest记录其哈希，运行账本锁定策略ID与实际注入后请求指纹。复核原文、来源位置和档位比较仍由宿主完成，元数据通过不是独立语义认证。

`anchors`和`qualitative_claims`的项可带`modes:["highest"]`等数组，限制纳入口径。高层`computations`默认随主命令的模式运行；`--mode all`实际各运行一次，保留每模式请求和输出，分别进入`modes[mode].high_results`。只适用某模式的计算可在计算项上加`modes`。计算请求里不需要手工复制三份`mode`；外层分析模式会注入高层工具。物理测量误差和三模式取材独立，物理计算默认只运行一次。

命令：

```text
python scripts/battle.py doctor
python scripts/battle.py physics --input assets/cases/physics-earth-binding.json
python scripts/battle.py high --input assets/cases/high-godbox-stage4.json
python scripts/battle.py hax --input assets/cases/hax-ceiling-synthetic.json
python scripts/battle.py analyze --input CASE.json --mode all --output RUN_DIR
```

报告输出report.md、analysis.json、sources.json、derivations.json、rules-snapshot.json、run-ledger.json、原始字节副本CASE.json和manifest.json。manifest保存各文件hash，规则快照包含实际采用的规则内容和原件指纹；运行账本保存Skill版本、取证模式、PK呈现、输入和条件指纹。可选 `run_metadata` 记录宿主实际使用的模型标识、prompt版本、检索快照与人工审核者，未知字段不猜造。更改争议前提重跑到新目录，避免覆盖旧结论而丢失推导。

PK字段：`matchup.presentation` 默认overview；`matchup.mode_assessments[mode].win_estimate` 为 [宏观主估](matchups.md)；`matchup.mode_processes[mode]` 为 [过程工具输入](combat-process.md)，analyze注入该模式和案例sources。宏观报告不会展开预存过程数据，只有显式process入口运行和输出过程。输入CASE保持原字节，CLI覆盖呈现另记在账本中。

顶层可加 `derivation_requests:[{"id":"audit-1","request":{...}}]` 调用 [推导审查](derivation-workflow.md)，结果保存在 `derivation_audits`；审查结果不能直接当新的原作锚点。搜证计划/索引使用独立 `research` 请求，避免每次分析都无差别联网、加载全书或导入大型数据。
