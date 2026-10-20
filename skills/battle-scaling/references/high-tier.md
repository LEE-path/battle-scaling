# 高层结构、数学盒子与论外推导

仅在任务出现无限宇宙、数学构造、叙事超越或论外时加载。先读取案例索引 `high-tier-cases.md`；计算按需调用 `scripts/high_tier.py`。有限表现仍走物理模型，不因出现“无限”二字就放弃证据审计。

当前默认以 [2026.7.30册](handbook.md) 的已校勘条款映射。下文 `high-zerozhi2025-*` 与 `high-wiki-aos404` 是显式具名历史快照；本册的序数叠法、新标、道标、力标等另存规则，不能混同。`battle.py high` 自动采用安装配置；直接导入 `high_tier.analyze` 的纯算术请求若不传规则，保留为无社区定档的数学计算。

## 1. 推导分四个层次

1. **原文事实**：原作说了什么，谁说的、适用阶段、对象和语境是什么。
2. **形式化解释**：它可解释为基数、序数、社区N结构、理论／模型、真类，还是作品原生关系。解释本身是需要证据的桥梁。
3. **计算／推导**：在声明的公理及定义下算出了什么；支持的精确运算可执行，其他保留符号及定理依赖。
4. **规则映射及角色继承**：以具名版本映射标签，然后用独立证据把相应结构范围传给角色的特定能力。

这四层必须分别列出。世界拥有一个数学结构，不等于其居民的拳头都能毁掉该结构。抵达、感知、生成、抹除、控制、承受各自建立边。有限焦耳、无限基数和叙事优位也不混合相乘。

特殊能力还执行 [双上限规则](hax-ceiling.md)：以该能力表现内影响上限为默认，任何模式最高不超过原世界观最强角色**已达**量级。原世界观有更高结构而无人达到，不能用结构高度填角色天花板；同样不能因最强角色已达论外，就把普通角色未证的精神或时间能力自动升为论外。高层只有偏序时提供有来源的直接比较；不可比就保留缺口，不能解释为无上限。作用范围与抗性相互作用另证。

“成为某存在”使用`becomes→state_identity`，“融入／合一”使用`merges→fusion_state`。这是身份或融合状态声明，不能改写成`controls`。在`character_relations`中保留`state`、`duration`及`scope/conditions/timeframe/phase`等范围；缺少状态或持续时间会显式警告。未知持续时间不扩展为永久常态；这种关系即使附带泛化`bridge`也不会自动得到攻击、耐久或破坏范围，请求这些属性会出现`blocked_identity_to_combat_transfer`。若原作另有实际攻击或承受表现，分别添加相应事件证据再判。

## 2. 先确定类型

| domain | 典型对象 | 可以问什么 |
|---|---|---|
| finite magnitude | 巨大有限整数、有限箭头运算 | 是否仍有限、参数多大；大数不因难写而等于无限 |
| ordinal | ω、ε₀、Veblen层级 | 排序结构、后继与极限、可数性；序数加乘不交换 |
| cardinal | ℵ₀、ℵ₁、幂集 | 势、注入、等势、公理依赖 |
| community formal structure | 个人规则中的N、N^^N | 在该规则定义内属于什么结构标签 |
| theory/model | ZF+某公理、Ultimate L、V-logic | 模型、可解释性、一致性强度；通常不具有普通数值乘法 |
| proper class | 全体序数、集合论宇宙V | 类框架中如何描述；不能当成集合基数 |
| fiction native | 自定义Φ、叙事层、超数学操作 | 作品给出的相对关系及与具名锚点的比较 |

相同符号不意味着相同类型。神盒Φ不默认等于Veblen φ；小说把某阶段叫epsilon-zero，先保存其定义再决定能否用标准数学。超实数、超现实数、超限数不是同义词。基数的后继与序数的后继也分别处理。

## 3. 常见数学桥梁

- `1+ω=ω`，`ω+1>ω`；`2×ω=ω`，`ω×2>ω`。
- 可数序数的有限四则式、有限层ω指数塔，以及指定可数序列的该塔极限ε₀，仍属于可数序数；不是ℵ₁。
- 在ZFC中：`ℵ₀×ℵ₀=ℵ₀`，`ℵ₀^ℵ₀=2^ℵ₀≥ℵ₁`。`2^ℵ₀=ℵ₁`需要CH；`2^ℵα=ℵ(α+1)`的通式需要GCH。
- 显式ZF语境不补选择公理。没有适当选择／良序前提时，`P(ω)`不可数并不在此工具中被当成已证明存在`ℵ₁→P(ω)`的注入。
- 不可数、正则、极限给出弱不可达。再有强极限性质给出强不可达；GCH是从前者推后者的一个充分附加条件。没有GCH不等于它不是强不可达，只表示还需强极限证据。

数学依据：[Koellner, Set Theory: The Independence Phenomenon](https://people.math.harvard.edu/~wboney/fall16/settheory.pdf)。这些结论只处理数学对象；战斗量级映射由另一个规则文件提供。

对大基数，记录定义与背景逻辑。`large cardinal`和`huge cardinal`不混译；“不可达”“巨大”不能仅凭汉字形容词识别。Reinhardt、Berkeley等语境尤其检查Choice条件。执行器不认证任意公理系统相容，也不以发现矛盾为由让所有结论自动成立。

## 4. 将描述转换为可审计构造

每个节点保存`id, operation, depends_on, description, definition, scope, source, assumptions`。来源至少包含`url/path`和稳定`locator`。分清“已经完成”“必然会继续”“理论允许”“叙述者猜测”。

| 描述 | 建立的结构 | 必须补足的条件 |
|---|---|---|
| 无限个、无穷层 | 数量域／迭代指标的候选解释 | 是实际无限、任意有限，还是修辞？包含什么对象？ |
| 每层包含下层全部 | contains | 是否完整副本、是否包含全部平行分支；空间包含是否意味着能力优势 |
| 任意既有方法都到不了 | transcends(closure) | 既有操作集合、允许迭代长度、被超越闭包的范围 |
| 把上文全体当作0／单位 | base_reset | 被打包的完整子图、下一阶段规则；不能漏掉此前整体 |
| 换一种更高运算 | operation升级 | 新定义、对象域、与旧方法的相对关系 |
| 当成书／梦／投影 | narrative | 是否能实际改写下层、上层主体受何限制；不能只数纸张层数 |
| 超越一切数学／逻辑 | native候选 | “一切”范围、作品自身定义、实际超越机制；不自动给具体大基数 |
| 最强／同层 | 属性比较候选 | 比较对象、时间范围、属性含义和原文限定 |

**常态**优先可信反复表现；模糊范围先取有证据的解释。**最高**允许将模糊描述作激进范围扩张，由Agent自动提出具体前提写进`assumptions`，再推出条件结论；不必因规则有争议停止。**扒下限**登记限制、失败、破格及反向比较，区分“低于某锚点”的条件上界和“至少达到某锚点”的下界。

同一句模糊形容词重复十次，不会自动多出十层。最高模式也应说明新一次描述为何改变了基底、操作、作用域或支配关系。原生语义可以被接受为作品关系，但不能冒充标准数学定理。

## 5. 具名规则与分歧

配套文件分别保存：

- `high-zerozhi2025-old.json`：2025个人整理所记旧门槛，以ℵ₁作历史对照。
- `high-zerozhi2025-new.json`：该文N形式结构和部分新标；N^^N的标签按社区形式保存。
- `high-wiki-aos404.json`：第三方站点所引AOS／404，旧神盒第四阶段及以上锚点。

来源：[零智2025个人整理](https://www.bilibili.com/opus/1022449834228973569)、[战设标准2.0](https://vsbattles-wiki-cn.wikidot.com/comment-tools)。本轮核验不能把这些命名为2026汪吧统一官方总规范。两套规则中“论外一线”等同名字样不自动等价。切规则保留原构造和推导，只重做映射。

旧神盒第四阶段身份与锚点一致时，可在该AOS表下得到条件一线标签；其他作品需要逐项比较，而不是自称“比神盒更强”就算完成证明。对未核验的跨作品嵌入，工具输出`candidate`，Agent继续搜证并逐项解释。

原生比较达到更高锚点时可继续至论外及其细分档。不要把“不支持直接数值求值”写成“没有量级”；报告应给原生相对结论和能成立的具名映射。

## 6. 执行器API

所有工具路径相对Skill根目录。Python 3.10+，标准库即可：

```python
from high_tier import analyze
result = analyze({
    "kind": "cardinal", "expression": "aleph0^aleph0",
    "axioms": ["ZFC"], "ruleset": "high-zerozhi2025-old"
})
```

命令行：

```powershell
python scripts/high_tier.py --input assets/cases/high-godbox-stage4.json --output godbox-result.json
python scripts/high_tier.py --input request.json --ruleset rulesets/high-zerozhi2025-old.json --output result.json
python -m unittest discover -s tests -p test_high_tier.py
```

`--ruleset`允许自备具名JSON；API第二参数也接受完整规则对象。请求里的`ruleset`仅接受随包`high-*.json`名称，防止无意路径读取。规则数据来自调用方时，结论仍是对该规则的条件映射。

请求`kind`：

| kind | 核心输入 | 已实现范围 |
|---|---|---|
| ordinal | expression | 有限系数、有限指数的Cantor正规形（小于ω^ω）；非交换加乘、有限幂；ω有限塔的可数性及指定ω塔极限ε₀ |
| cardinal | expression, axioms | 有限整数、aleph0..aleph10000，加乘、幂集、部分基数幂；CH/GCH显式依赖 |
| inaccessible | facts, axioms | uncountable、regular、limit、strong_limit的定义检查与GCH条件推导 |
| formal_box | expression | N、整数及`+ * ^ ^^`，按所选规则的结构模式映射 |
| native | nodes, anchor_claims, character_relations | DAG、出处结构、原生操作、锚点候选／同一身份映射、角色属性桥接 |
| theory / proper_class | name, expression, axioms | 保留类型与原文，不输出伪标量 |

表达式指数右结合：`omega^2^3 = omega^(2^3)`，与`(omega^2)^3`不同。`tower(omega,3)`以`t0=1,t(n+1)=omega^t(n)`定义高度；`tower(omega,omega)`专指该序列的上确界。没有`eval`或任意Python执行；不认识的函数保留符号表达，非法语法返回`invalid`。

输出包含`status, mode, axioms, result, steps, assumptions, mappings, provenance, warnings, limits`。状态：

- `exact`：该数学片段中的精确结果／精确符号身份，不意味着角色判定毫无条件。
- `symbolic`：对象保留且可能知道可数性等性质；未声称解出全部精确运算。
- `conditional`：给定前提或原作解释下的结构推导。
- `invalid`：语法、类型、依赖环或显式矛盾条件出错；退出码2。

所有映射另有自身状态。`conditional_on_anchor_identity_and_source`表示同一具名锚点身份成立时；`candidate`表示跨构造比较还需审计。`source_present`只检查记录结构，工具不会在离线状态声称已读网页。

## 7. 不受内置算术片段限制的扩展流程

遇到Veblen、快速增长层级、超限迭代、大基数、公理模型等内置不精确计算的构造时，Agent继续完成任务：

1. 保存原始描述、符号、括号和源语言，确认是标准对象还是作品自创。
2. 查定义与原始数学资料，列背景公理；必要时使用论文、作者教材及数学数据库。
3. 写明后继步骤和极限步骤。只有有限迭代不冒称已完成极限；“所有”限定到已经给出的对象域。
4. 在`native`节点的`typed_object`或`theory`记录精确定义、定理及证明桥梁。若使用外部CAS／定理证明器，保存工具版本、代码、输入和输出。
5. 必须程序化求值的新重复运算，新增独立扩展模块，不覆盖通用定义。以小例、边界例和已知反例验证，预算限制写清。
6. 将已证部分与候选解释分别映射规则。若没有可证的标量，照样给原生偏序、条件上／下界、争议分支；不要强行制造小数或焦耳。

一致性强度论证还需区分“证明蕴含”“等可解释”“等一致性”“模型存在”；这些关系不能凭一个“等价”合并。可参考[Hamkins, A simple maximality principle](https://arxiv.org/abs/math/0009240)核对可能世界／力迫案例，区分不同参数版本。不可把人物知道一句数学术语直接转成拥有该理论一致性强度的攻击。

## 8. 给其他Agent的验收要求

换Agent只提供本Skill和未见过的请求时，应能：分开三模式；给每一步原作、解释、数学与规则来源；对CH/GCH删除作相应收缩；把虚构Φ与标准φ分开；保留版本边界；拦住旅行范围转攻击；接受原生论外推导且标明条件；遇到未实现运算继续研究，而不是伪称通用求解器已算完。
