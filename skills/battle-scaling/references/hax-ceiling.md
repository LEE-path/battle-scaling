# 特殊能力的表现上限与世界观角色天花板

## 规则身份与原话

本条是 `user_confirmed_policy`，策略 ID 为 `user_confirmed_hax_ceiling_20261020`。

用户原话：

> 汪吧规则是，特殊能力最高不可越过原世界观最强量级，特殊能力默认取表现内影响上限。

追问上限指最强角色还是结构后，用户回答：

> 最强角色已达到的量级

用户随后明确要求“修改入skill”。这里准确保存用户指定的采用口径；本轮没有独立检索、核验全部汪吧文献，不能将这项用户确认冒称为本轮已完成的全吧规则认证。

## 两道上限与独立机制检查

先检查该特殊能力自身已展示或有依据叠出的影响上限，再检查原世界观最强角色已达到的量级。目标超过其中一道有来源、可比较的上限，本次用法就是 `blocked`。三种模式都不能用 assumption 把已知超限改成条件成功。

“最高”允许该模式证据支持更高的能力上限、或更高的最强角色已达量级；先把依据录入证据包，再比较。最高模式本身不是跳过天花板的开关。原世界观结构再高，也不能代替具体最强角色已达证据；最强角色达到星级，也不会自动把所有特殊能力抬到星级。

能力影响上限与施术者 AP 分开记录。例如楼级施术者的控制能力已经控制城级对象，可以按这项能力的城级影响证据判断；不能用楼级 AP 反向压低该能力，也不能借世界观星级角色的存在把它无证抬到星级。

对象是否属于适用对象、跨作品机制是否兼容、发动与作用条件、抗性与反制分别核查。作用域另写，不能把“控制了多少人／覆盖多大面积”直接换成“能控制什么档次的个体”。目标同档或无抗性记录，均不自动证明作用成功。已知不相容、发动失败、存在阻断该用法的抗性，仍可使本次用法 `blocked`。

## `hax_policy.run(request)` 输入

最小完整的可执行合成示例见 [hax-ceiling-synthetic.json](../assets/cases/hax-ceiling-synthetic.json)。该文件明确标识 `synthetic_not_original_evidence`，不是任何作品的原作证据。

```json
{
  "mode": "normal",
  "ability_id": "ability-id",
  "sources": [{"id": "s1", "access": "provided", "origin": "primary"}],
  "observed_limit": {
    "basis": "demonstrated",
    "ability_id": "ability-id",
    "statement": "这项能力已经影响到哪个档次的对象，或如何有依据叠出该上限。",
    "source_ids": ["s1"],
    "level": {
      "system": "具名分档体系",
      "ruleset": "具名规则版本",
      "axis": "affected_entity_tier",
      "label": "该对象档名",
      "rank": 2
    }
  },
  "world_ceiling": {
    "kind": "strongest_character",
    "character_id": "strongest-character-id",
    "source_ids": ["s1"],
    "attainment": {
      "kind": "achieved",
      "statement": "该最强角色已经达到此量级的具体证据。",
      "source_ids": ["s1"]
    },
    "level": {
      "system": "具名分档体系",
      "ruleset": "具名规则版本",
      "axis": "affected_entity_tier",
      "label": "最强角色已达档名",
      "rank": 3
    }
  },
  "target_level": {
    "system": "具名分档体系",
    "ruleset": "具名规则版本",
    "axis": "affected_entity_tier",
    "label": "目标档名",
    "rank": 2,
    "source_ids": ["s1"]
  },
  "checks": {
    "object": {"state": "pass", "explanation": "适用对象依据", "source_ids": ["s1"]},
    "compatibility": {"state": "pass", "explanation": "机制兼容依据", "source_ids": ["s1"]},
    "activation": {"state": "pass", "explanation": "发动及作用条件依据", "source_ids": ["s1"]},
    "resistance": {"state": "pass", "explanation": "抗性及反制检查依据", "source_ids": ["s1"]}
  },
  "effect_scope": {
    "description": "实际作用对象、范围、数量和持续条件；与个体档次分开。",
    "resistance_interaction": "这项效果如何与抗性相互作用，不能用范围替代抗性判断。",
    "source_ids": ["s1"]
  }
}
```

`mode` 为 `normal`（默认）、`highest`、`lowball`。`sources` 也接受以来源 ID 为键的字典。`observed_limit.basis` 只能是 `demonstrated` 或 `supported_scaling`；宿主应保存原文、推导链及反例位置，可在输入中增加 `derivation` 等原始记录，它们随 `request_snapshot` 保留，但本工具不会代做语义证明。

`world_ceiling.kind` 必须为 `strongest_character`，并具备具体 `character_id`、`attainment.kind=achieved`、已达说明和可读来源；`cosmology_structure` 不被采纳为角色天花板。两个上限下的 `level.source_ids` 可以省略并继承所属上限的 `source_ids`；目标的档次必须独立绑定来源。所有声明的来源都必须可用，不能只保留其中一个来掩盖其他不可读来源。

证据节点或来源可以增加 `modes: ["highest"]` 等非空模式列表，防止某模式专属证据混入另一模式。宿主集成时以外层 CASE 的 `sources` 和当前模式覆盖嵌套 request 同名值，避免内部来源表或模式逃逸。

## 有来源的同体系比较与高层偏序

数值 `rank` 仅在同一个具名 `system`、同一个具名 `ruleset`、同一 `axis=affected_entity_tier` 内比较，约定数值越大档次越高。rank 的依据随对应 level 或上限来源保存。布尔、NaN、Infinity 均不是合法 rank；缺 rank 也不能填无限或零。

本工具不自带、也不虚构所有档位的总序。高层档位若只有局部可比关系，可以省略 rank，并提供宿主从可读来源提取的局部比较：

```json
{
  "explicit_comparisons": [
    {
      "left": "target_level",
      "relation": "le",
      "right": "observed_limit",
      "explanation": "来源为何支持目标不高于该能力上限。",
      "source_ids": ["s1"]
    },
    {
      "left": "target_level",
      "relation": "gt",
      "right": "world_ceiling",
      "explanation": "来源为何支持目标已经超过该角色天花板。",
      "source_ids": ["s1"]
    }
  ]
}
```

`le` 表示不高于，`gt` 表示严格高于。只接纳 `target_level` 对两道上限的直接比较，不自动传递或补全总序。这些关系同样不能跨 `system/ruleset/axis`。已知数值超限不能被额外 `le` 声明覆盖；有来源比较出现冲突且其中已知超限时保留 `blocked` 和冲突说明，回看原资料解决。

缺上限、不可比、跨标准未完成统一，输出 `undetermined` 与补证任务。不能把不可比解释成没有上限，更不能把它算成已作用成功。

## 条件、输出与覆盖范围

每项 `checks` 使用 `state: pass|fail|unknown`。`pass` 或 `fail` 需要说明和可读来源。已知 `fail` 不受 `assumption` 覆盖；未知抗性默认补证。若明确建立假设分支，可在 `unknown` 节点加 `assumption: "假定无相关抗性"`，此时至多得到 `conditional`。假设自身不是有来源事实。顶层 `assumptions` 也可保存明确条件，但不能代替能力上限、世界观天花板、同体系比较或作用域说明。

核心输出：

```text
status: supported_by_packet | conditional | blocked | undetermined
within_observed_limit: true | false | null
within_world_ceiling: true | false | null
assumptions: string[]
reasons: string[]
source_ids: string[]
research_tasks: [{field, task}]
policy_id, policy_identity, validation_scope
request_snapshot, comparison_trace
```

`false` 表示本包存在可读且可比较的已知超限；`null` 表示缺证或不可比较，不是零或无限。状态优先级为：已知阻断 `blocked` → 尚有必须补证的缺口 `undetermined` → 仅在显式假设下成立 `conditional` → 本包所有检查满足 `supported_by_packet`。

`supported_by_packet` 只表示本包中的两道上限和独立机制前提通过检查；不意味着必定命中、必定生效、必胜，或工具独立阅读了原作。比较原始档位、方法及结论保留于 `comparison_trace`，完整输入保留于 `request_snapshot`，方便报告追溯，调用方仍须保存原作文件、页码、原文及推导。

可读来源集合直接复用 `pk_modes.READABLE`。`primary`、`verified` 是宿主填入的元数据；`input_declares_primary_verified` 只汇报元数据声明，`original_source_verified` 始终为 `false`。工具不认证原文含义、身份真伪、推导语义蕴涵或全吧标准。`blocked` 等不可读来源不会纳入有效来源，重复来源 ID 也视为歧义，需要补证。
