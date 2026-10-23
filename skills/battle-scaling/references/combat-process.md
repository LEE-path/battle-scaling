# 有证据状态轨迹：具体战斗过程

这是论战研究的 `process`。作者要求去掉报告措辞、按设定创作完整打斗并指定过程或结局时，转 [战斗写作辅助](writing-battle.md) 和 `battle.py writing`；不要通过关闭本模块证据门槛实现写作。创作正文与原作战绩分开保存。

**先完成独立角色定档，再运行过程。** 各方先走[共用单人评定流程](character-rating-workflow.md)，具体综合主档与适用属性完成选档，九维卡与完整推导经宿主验收；已证下限只是依据，不能替代综合主档。输入携带`independent_ratings`和匹配配置；直接调用process也不绕过此门。缺档返回`needs_independent_rating`，不结算步骤、胜者或胜率。[完成性审核](rating-completion.md)同时约束本入口：局部下限、重要候选未审或已撤回评级均不放行。已定档后跨作品作用未决才使用下文的条件分支，不能让角色未定档混入。

`standard` 独立于证据口径和呈现，默认汪吧。VSB过程改用对应特能门槛及[SBA胜利条件](vsb-combat.md)；`victory.vsb_checks` 按败方角色ID给条件／时长与来源，BFR至少一周、昏迷至少一小时、失能超过一天，死亡还需最终满足其一。步骤数不作秒数；缺证保留未决。

本工具执行宿主 Agent 已写出的行动、机制判断与条件分支，检查来源可读性并结算声明的有限效果。它不自动理解原作，不预测下一招，不从攻击力推导命中率，不执行自动物理战斗仿真。输出是 `hypothetical_process`，始终 `canon_evidence=false`。本模块仅使用 Python 标准库，自行实现，未复用外部战斗项目代码。

## 先选呈现，再选证据口径

- `overview` 是默认呈现：宏观获胜路径、合理胜率估计及关键条件。已有 `mode_processes` 数据并不意味着用户要求观看过程。
- 只有用户明确要求具体行动、命中、防御、伤势和后续时才选 `process`。内部先完成宏观胜负分析及逐步机制判断，再按下述默认格式向用户展示。
- 新任务统一使用 `mode:integrated`，读取 `case.matchup.mode_processes.integrated`。高光、通常、低谷只作为动作、状态、失误及交互条件参考，不分别生成三套角色评级或默认三局；权威规则见[综合评级](modes-scaling.md)。

## 详细打斗的默认输出：优势方的一局胜局

用户要求详细打斗而未指定结局或展开方式时，**默认选取总体胜率更高一方获胜的一局完整战斗**。先独立分析双方获胜路径、反制及胜率，再选一条合理胜路写成过程；不是随机抽签、连续多局，也不默认把双方各自的胜局全部展开。用户指定别的结局或呈现时按其要求。

面向用户的正文依次为：

1. 简要交代双方配置、开局条件和会改变结局的必要假设。
2. **优势方获胜的一局完整战斗过程**：用连贯战况呈现行动→发动/命中→防御/反制→伤势与状态变化→下一步，直到满足本场胜利条件；对手按其能力、已知信息与性格合理反击，不能为成全指定胜局而站桩、降智或遗忘有效能力。控制与抗性先按所选标准及证据结算；聪明不自带识破或抵抗改写的能力，被完全控制者只在实际残留的认知与行动范围内反应，不强制有效反击或互伤。
3. **总体胜率或优势程度及理由**：说明双方在相同开局下的获胜倾向与关键机制，和刚才展示的这一局分开；有合理依据才给粗粒度数值或区间，不能合理量化时明确说明。
4. **另一方是否可能获胜、如何翻盘**：交代最强可行反击路线及使主判翻转的最少条件；默认简要分析，不再展开第二篇完整战斗。
5. 附可追溯来源、叠法及关键假设；战况内可用来源编号关联，完整轨迹表、JSON和工具审查另存供核查。

胜率无法数值化但能合理判断优势方时，仍可展示该方的一局胜局，并保留低置信或条件性限定。连优势方也无法合理区分时，不强行选赢家；先说明未决，所给单局仅能明确标为条件示例，不称为“胜率更高者的胜局”。

**选择展示哪一局，不改变证据准入或动作结算。** 已知失败、超出特能上限、无法成立的发动条件不能为了凑出胜局改为成功；关键交互未知时可另存有明确前提的宿主胜局示例，严格过程审查仍保留未决，不把示例赢家写成已获准赢家。单局故事不是概率样本，不能从这场胜利或人为挑选的若干分支反推总体胜率，也不能回填为原作表现。

以上规定宿主面向用户的回答顺序；工具原始审计报告及状态轨迹是核查材料，不代替这份读者版战况。

## 宿主的职责

1. 固定版本、时期、状态、装备、规则和胜利条件。原规则没有规定的双失能裁决，保留未定。
2. 为双方提出行动意图，然后逐项判断能否发动、能否命中、防御或反制是否阻止效果、伤势及状态如何变化、下一步还剩哪些行动与恢复窗口。
3. 每个可执行判断带来源 ID，或者以 `assumed` 和非空 `assumptions` 明确选择条件分支。未知不是失败，未知也不是自动成功；不把未出现的格挡写成“从来不会防御”。
4. 效果只能表达已论证的机制。真实人体、动物、体量、量级不能随意转成 HP；仅原作游戏的有来源数字可以启用 HP 模型。没有游戏数值时只写定性状态效果。
5. 反例和明确失败必须进入门槛或 `counterevidence`；不能用假设把已经失败的行动改成成功。分支故事不能回流为原作证据。

同一时间组的意图只依据双方此前可知信息与可见状态；除非有读心、预知等证据，不让一方读取另一方本组的未公开意图再针对选招。宿主先保存意图，再裁决，不以事后战果改写成事前必然知道。

## 调用

`scripts/combat_trace.py` 提供 `run(request: dict) -> dict`，不修改输入。宿主将当前综合配置的过程包与来源表一起传入：

```python
import copy
from combat_trace import run

mode = 'integrated'
request = copy.deepcopy(case['matchup']['mode_processes'][mode])
request['sources'] = case['sources']
request['mode'] = mode
request['hax_checks'] = case.get('hax_checks', [])
request['independent_ratings'] = case.get('independent_ratings', [])
request['rating_subjects'] = case['characters']
result = run(request)
```

完整可运行合成包为 `assets/cases/pk-process-synthetic.json`。其中两边同时命中是展示假设，伤害与同时结算来自给定规则；包内不声称这是一场真实战斗。

## 顶层与角色

| 字段 | 含义 |
|---|---|
| `mode` | integrated（默认）；旧normal / highest / lowball只兼容历史读取，不代替综合评级 |
| `sources` | 来源对象列表或以ID为键的来源字典；需唯一ID和读取状态 |
| `independent_ratings` | 必需：各方匹配标准、口径与配置的独立定档包，见[共用流程](character-rating-workflow.md)；不能用步骤中的胜果反过来补主档 |
| `rating_subjects` | 可选：从CASE携带角色的id/version/state/equipment供actors匹配；直接过程也可在各actor显式给这些配置 |
| `hax_checks` | [双上限检查](hax-ceiling.md)的`[{id,request,modes?}]`；CASE由analyze注入顶层共用检查，独立过程请求自行提供 |
| `actors` | 至少两个角色，各有唯一id、initial，HP和恢复规则按需提供 |
| `teams` | 可选的actor ID到team ID映射，例如`{"a":"left","ally":"left","b":"right"}`；未列角色各自独立，不将人数合成单次攻击 |
| `steps` | 按时间顺序的同时结算组，每组含actions；空actions可明确推进一个恢复/持续效果时点 |
| `victory.defeated_states` | 宿主明确采用的失败状态列表；缺失时不指定独占胜者 |
| `victory.mutual_outcome` | 可选，规则已给出的双失能裁决文字；没有时adjudication保留undetermined |
| `max_steps` | 1至1000，缺省100；只限执行预算，不创造平局 |
| `include_narrative` | 可选，生成仅复述已记录步骤的简短说明 |

角色示例：

```json
{
  "id": "a",
  "version": "本篇游戏版本1",
  "state": "本场健康可战配置",
  "equipment": [],
  "initial": {"state": "active", "hp": 10, "max_hp": 10, "resources": {"ammo": 1}},
  "hp_model": {
    "kind": "game", "zero_state": "incapacitated", "evidence_ids": ["s-game"],
    "assumptions": ["本分支采用零HP即失能的解释"]
  },
  "resource_evidence_ids": ["s-game"],
  "resource_exhaustion": {"ammo": "withdrawn"},
  "recoveries": []
}
```

该示例的弹药及耗尽退出也必须有本次来源支持；不要将示例值复制给无此机制的角色。资源归零默认只意味着不能再次支付对应成本，不会自动失能。只有显式 `resource_exhaustion` 才产生相应状态。

合法状态是 `active/incapacitated/dead/sealed/withdrawn/unknown`。只有active可以在新时点发动宿主行动；初始未知状态产生needs，不据此判终局。initial是指定情景边界，并非从原作自动推定。非游戏角色可完全省略hp、max_hp、hp_model，使用有证据的定性状态。

## 判断门槛与行动

每个判断是对象：`{status, evidence_ids, assumptions}`。读取状态允许 `verified/provided/indexed/read/verified_via_host_browser`；indexed仍只是已读索引，不证明取得完整原作。blocked/unread/unknown/error/not_found及未知读取状态不能支持已证效果。

| status | 执行含义 |
|---|---|
| supported | 至少一个来源ID，且全部来源可读；仅表示包内引用可用，不代表工具证明原文蕴含判断 |
| assumed | 至少一个明确假设；若同时引用来源，来源仍须可读；结果列为条件分支 |
| failed | 明确失败；不应用行动效果，附带假设不会覆盖此结果 |
| unknown / blocked / 缺失 | 不应用该效果，写入needs；可另建显式假设分支运行 |

一个行动示例：

```json
{
  "actor": "a", "target": "b", "intent": "尝试命中B",
  "activation": {"status": "assumed", "assumptions": ["本分支A进入可发动条件"]},
  "hit": {"status": "assumed", "assumptions": ["本分支A有效命中"]},
  "defense": {"status": "assumed", "outcome": "not_prevented", "assumptions": ["本分支防御未阻止命中"]},
  "costs": [],
  "counterevidence": [],
  "effects": [{"type": "damage", "target": "b", "amount": 10, "status": "supported", "evidence_ids": ["s-game"]}]
}
```

activation和hit都需通过；defense也需通过且outcome=`not_prevented`。若outcome=`prevented`，该行动被防住；outcome未知则保留未定。这里的defense判断是“防御结果判断是否成立”，不是“角色防御行动是否成功”；请同时写清outcome以避免歧义。

## 特殊能力的上限门槛

特殊能力默认取自身表现内影响上限，无论表现视角或交手条件，均不超过原世界观最强角色已达量级，详见 [规则与检查输入](hax-ceiling.md)。动作本体、activation/hit/defense、cost、counterevidence、effect和recoveries均可声明 `is_hax:true,hax_requirements:["检查ID"]`；实际依赖该特能的每层判断均绑定。动作本体无普通status仍会先做特能检查，不能仅把受阻能力改写成assumed继续执行。

request的检查写明 `actor_id` 与 `target_id`。攻击动作/效果默认归属行动actor、作用于实际target；防御与反例判断默认归属防守方、作用于进攻方，需要其他归属时显式写 `ability_owner`、`affected_target`。实际动作/效果目标不能被metadata改名成低档对象来通过检查。恢复默认由本人维持并影响本人；外援、物品等在actors与配置中明确归属后独立审查。

父动作的hax_requirements以AND继承给其效果；持续tick、到期效果与延迟结算保留依赖，不因换时点而免审。父动作检查不直接强塞给属于防守方的defense或counterevidence，它们使用自己的检查。若效果有独立能力或范围，增加其自身检查；继承不代替识别新机制。恢复受阻时不先消费次数或排入pending；生成revive仍保留检查。

blocked或undetermined均不应用相关效果，记录hax_admissions；已知blocked表示本次用法明确失败，不据此自动判对手赢，也不妨碍另一条独立且完整的获胜路径成立。undetermined仍写入needs并保留终局未定；conditional仅按明确假设执行。输出hax_reviews为实际执行的审查结果，hax_review_coverage列出声明/未声明的位置。未标记旧轨迹可运行，但未声明不等于已审或已证普通物理机制。

`counterevidence`是一组同样的判断对象。任一反例通过则阻止效果；反例未定也不会忽略它继续打中。`costs`项为 `{resource, amount, status, evidence_ids/assumptions}`，发动成功便支付，即使随后未命中或被防御。多次行动不能重复使用同一份资源。同一角色在同一组内的成本按列出的行动顺序预留；不同角色的攻击资格均基于该组动作前状态。

## 可执行效果

每个效果也需自己的门槛与来源/假设；只证明行动发动，不等于证明伤害必能作用。target省略时采用行动target。

| type | 参数与行为 |
|---|---|
| damage | amount为非负有限游戏HP伤害；目标需有可用的game hp_model |
| heal | amount为非负有限游戏HP恢复，最多max_hp；不会自行解除失能、死亡或封印 |
| state | state为合法状态；可表达失能、封印、退出等；0HP直接改active会被阻止，需明确revive |
| injury | 非空part、description，可选limitations字符串列表；保存部位损伤、后果描述与证据/假设，不创造HP，不自动推导失能或动作禁用 |
| resource | resource名称、有限delta；不允许未知资源或透支 |
| ongoing | 唯一id、duration正整数、tick效果；可有on_expire效果列表；各嵌套效果也需判断与出处 |
| revive | 可选hp、from_states（缺省incapacitated/dead）、restore_state（缺省active）；有HP目标须明确恢复多少HP |

`injury`可用于真实肉身或无数值角色，例如`{"type":"injury","target":"b","part":"左前臂","description":"可见创口","limitations":["本分支握持能力受限"],"status":"assumed","assumptions":["创口及握持影响均为待核分支"]}`。后续是否还能用左手攻击，由宿主在下一行动的activation等门槛中提供证据或假设；工具不从伤势词语自行判断人体机能。已证创口与推测骨折/机能影响应分别记录，不以一个来源概括为全部已证。

所有效果可附 `delay` 非负整数；delay>0进入pending，到后续指定时点才结算。已发动的延迟效果和持续效果不会因施术者失能自动取消；若原作规定依赖施术者，宿主应选择不保留该效果的分支或记录反例，本工具不会自行发明依赖关系。

持续效果示例：

```json
{
  "type": "ongoing", "id": "synthetic-poison", "target": "b", "duration": 1,
  "status": "assumed", "assumptions": ["仅为时序测试的持续伤害分支"],
  "tick": {"type": "damage", "amount": 2, "status": "assumed", "assumptions": ["测试规则每次结算2HP"]}
}
```

在第n步附加duration=1的效果，会完整保留到第n+1步开始，结算一次tick后到期；不会在附加当步扣掉持续时间。on_expire用于显式到期效果，例如解除有限封印；没有写明的解除、伤害或回满不补造。

自动恢复窗口放在actor.recoveries，例如：

```json
{
  "id": "one-return", "trigger_states": ["incapacitated", "dead"],
  "delay": 2, "hp": 6, "uses": 1,
  "status": "assumed", "assumptions": ["测试分支：失能后两个时点恢复到6HP一次"]
}
```

若第1步失能，第3步开始恢复；第2步不能提前宣告彻底死亡或独占胜利。delay=0在触发步伤害结算后恢复；没有恢复到期步骤就保持pending，不自动生成无授权的未来情节。封印/退出不在from_states时，复活不会顺便解封或重返战场。未读恢复证据保留unknown，不当成已经证明“没有复活”。

## 时序与输出

每步依次：

这里的“步”是显式定义的事件时点或同时组，不默认等于一秒、一帧或一回合。若要推算现实时间，另附原作时间/速度与前后距离证据；不得把`delay:2`直接解释成两秒，也不把动画播放时间自动视为剧情时间。

1. 保存state_before，结算到期延迟效果和既有持续效果；新效果不在本步tick。
2. 以同一动作前快照审核双方资格、发动、命中、防御/反制；先预留可支付资源。
3. 集中应用该组效果。同组游戏HP伤害/恢复先合并，再统一更新失能；不会按列表先后取消另一方已同刻成立的命中。互相冲突的状态效果没有优先规则时进入needs。
4. 触发自动恢复规则，保存state_after、pending和终局状态。每条行动均保留intent、activation、hit、defense、state_changes和follow_up，以及来源/假设。

同组伤害/恢复集中结算，行动行的`state_changes`是涉及双方的该组共享结果，`state_changes_scope=simultaneous_group_shared_outcome`；不能把它读成该动作单独造成全部变化。逐效果机制看effects的原请求，实际同时结果看步级changes/state_after；需要区分个别伤害份额时，由宿主另给来源和耦合模型，不从共享变化倒推出独立伤害。

结果含 `trace/final_state/terminal/status/assumptions/needs/pending`。terminal.kind可为：

- victory：显式失败状态规则成立、只剩一个仍有active成员的队伍、所有敌方满足失败状态且没有待结算窗口；winner指向team ID。未提供teams时每个actor各自为队，因此单挑winner仍是actor ID。多人同队存活可正常判胜，同队成员已退出不妨碍队友完成规则中的胜利。
- mutual_defeat：双方/各方均不能继续，且无待恢复；winner为空。这是过程状态分类；双失能的胜负裁决未写明时adjudication仍为undetermined，不自动当成平局。
- recovery_pending：有待复活，is_terminal=false；不提前指定胜者。
- effects_pending：已发动的延迟攻击、有限持续效果或解除窗口还未结束，is_terminal=false。
- undetermined：有关键未知项、未读证据、未知初始状态或胜利条件不全。
- ongoing：所给步骤后仍可继续；未写后续不等于和局。
- truncated：max_steps截断剩余计划，is_terminal=false；不是draw。

status为recorded/conditional/needs_information/truncated。recorded只说明声明的状态操作完成，不等于原作事实已审核。可选narrative只从trace拼接步骤和状态，并标为illustrative_not_canon；它是便于阅读的说明，不能当作证据回填sources或anchors。工具不自动生成动作策略、命中分布或宏观胜率；这些归宿主的overview分析。
