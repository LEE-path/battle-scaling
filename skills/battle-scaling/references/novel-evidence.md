# 小说原文阅读与拆书取证

仅在长篇小说、官方配套小说或现成拆书包需要本地正文定位时加载。沿用 [小说结尾状态](novel-ending-state.md)、[证据协议](evidence.md) 和 [单次表现审查](feat-review.md)，不另设量级、倍数或模式规则。外部摘要帮助找线索，定档回到实际正文、语境及可核来源；本地文件存在与哈希一致不认证作者、官方身份或文本完整性。

**首次完整评级／对战建档优先走[完整论战拆书流水线](novel-refpack-pipeline.md)。**先核是否有同版本、同终点、覆盖及宿主验收明确的能力与实绩档案；没有则主动取得原文并分任务实际阅读，形成末期能力时间线、逐能力正反表现、九维与交锋继承后再定级／VS。本文轻量检索和网页逐章查询用于原文发现、补缺章及核版本／引用，不能替代首次完整拆书。局部机制问答、已有合格档案的局部补证可定向核查；材料受阻时披露部分覆盖，不冒称完整。验收及组合方法见[能力实绩协议](ability-feats-and-combos.md)。

## 正文候选、派生资料与项目正典

| 层 | 可做什么 | 不能自动证明什么 |
|---|---|---|
| 原始 TXT/MD/EPUB/DOCX、refpack 的 `source/` | 保存本地原件快照，核版本、正文、目录和末章 | 文件名或来源目录不能证明正版、原作者、最新或完整 |
| `raw/_all.txt`、`raw/sections.json`、`chunks/` | 正文候选及抽取结构；读上下文、定位、比较遗漏与改写 | 不能因文件叫 raw/chunk 就跳过与原件的校勘；抽取行号不是出版页码 |
| `notes/`、卷纪要、`整书总结.md` | 找事件、别名、可能的结尾与相关章 | 不代替动作原文、实际出力、原版结尾或数学定义 |
| `canon/`、设定判据、编号账本、章节提示词 | 了解该写作项目选择的工作版本，发现版本冲突 | 名称“canon/正典”不等于官方正典；未经回溯的“作者确认”不是已验作者声明 |
| `out/`、续写、`例子.txt`、`stylefit` | 标记创作产物或风格导航 | 不能生成原作事实、数值、结尾或战力证据 |

这些是读取策略，不是从路径推断真实身份的自动分级。原作本身若含附录、设定或后记，仍分别审查来源身份、声明性质与适用范围。用户明确指定自设/续写版本时新建版本键，不混入原版。

**文件齐全检查通过，不等于原作结尾正确，也不等于原版已被读完。** 对任何书包都应核对原件目录、末章、派生摘要与所选版本；发现删改、续写或结局冲突时分别记录，不能把工作版本当成原版。

## 阅读顺序与证据链

1. **固定身份和终点。**记录作品、连续性、版本、完结/连载、正文来源及配置。小说默认原版本末尾状态；若有多年后尾声，先查尾声。连载取本次已核最新章节，不能用站点“最新”标签替代正文确认。
2. **先盘点再取末章。**对照原件目录、抽取章节和派生目录，记录缺章、重复、章节合并、删改、乱码、正文/续写混入及尚未确认项。先读结尾附近九项属性；结尾无表现，再逐项向前补，并论证能力、装备与状态能否延续。
3. **搜索只负责发现。**角色名/别名、能力原词、破坏/范围、命中/承受、失败/限制等词交叉使用。按章节倒序找，不因最末一次关键词命中就认定它是最终状态的最强表现。否定、引用、假设、回忆和旁观者发言均需读上下文。
4. **实际读取上下文。**命中前后 20–50 行可作起点；发话人、因果或战斗跨章时继续扩展。保存实际打开的范围和截断情况，分清原文引句、宿主观察、模型解释及参数假设。引用只摘必要短句，全文留在已有合法取得的本地证据中。
5. **建立可回溯定位。**原文件路径与字节 SHA-256、抽取文本路径与文本 SHA-256、编码/抽取方法、章名、实际行范围、关键段首及必要上下文一并保存。原件、抽取文本、chunk 的哈希各标所属文件，不能互相冒充。EPUB 另保留 spine 成员，DOCX 另保留实际 XML 段落定位；没有出版页码就不编。
6. **回到既有审查链。**将已核读段落纳入 `research` 记录和 `CASE.sources`，再以 `feat_reviews`、`review_requirements`、`anchors/edges/qualitative_claims`、`hax_checks/hax_requirements` 表示主张与依赖。单次实际结果、全力、状态延续和能力上限分别论证，不能由“结局最强”统一填满。

refpack 的 manifest `start/end` 可作为导航跨度，但 chunk 重组与 `strip` 会改变局部字符位置。本次检查已见 chunk 与对应 raw 子串不逐字相等。**不得用 `manifest.start + chunk局部offset` 冒充原文偏移。** 引用 chunk 就记 chunk 真实行；需要 raw 定位时在实际 raw 中另查、核对上下文并分别记录。

## 四张内部工作表

表用于本次工作文件或附录，按证据充分性展开，不要求固定条数；四表不是聊天默认全部展示。聊天按 [九属性量级卡](rating-card.md) 先给“角色（版本）量级：具体综合主档”，再给综合九维卡；高光、通常、低谷的表现和交手条件只在依据与限制中分析，不再内部另造三套角色档位，按[综合选档](modes-scaling.md)统一审查。

| 表 | 记录内容 | 对接 |
|---|---|---|
| 破坏/作用 | 事件、实际对象与受作用部分、几何/材料/状态、机制候选、公式和参数来源、结果范围、AP/AOE/破坏范围归属、替代解释 | `sources` → `feat_reviews` → `computations/anchors`；不适用物理换算的作用保留机制描述 |
| 能力 | 归属与配置、发动/接触/射程/持续、目标与抗性、已证影响上限、原世界最强角色已达上限、代价与失败、原文位置 | `hax_checks/hax_requirements` 及定性主张；世界观结构不替代角色已达量级 |
| 交战 | 双方当次版本/状态/出力、动作→传递→防御→结果、伤势/恢复、克制/偷袭/环境/伙伴、可传与不可传属性 | `feat_reviews`、具体 `edges`、条件与反例；胜败不自动换成倍数或固定升降档 |
| 最终九属性 | 输出、体防、智力、战斗智商、经验、特殊技能、破坏、速度、体量；每项给一个综合主判，记录来源／叠法／条件和相关高光、通常、低谷表现 | 同一结尾配置的量级卡；智力/经验无已核爆×口径时用有据等级，不能编造档名 |

可复制 [小说证据卡与四表模板](../assets/templates/novel-evidence-card.md)，所有占位由真实读取填写；模板本身不是原文、真实角色案例或可执行 CASE。

## 本地阅读工具与外部 refpack

全书分章任务、带指纹的宿主阅读回执、正反表现聚合和结尾九维缺口，使用新增的 [完整论战拆书流水线](novel-refpack-pipeline.md)：`scripts/novel_refpack.py prepare/search/tasks/accept/build/verify`。它已随Skill自包含安装，不依赖原写作工程或固定盘符；当前Agent负责逐任务语义阅读，工具负责原文快照、逐字位置、回执与覆盖校验。下面的轻量 `novel` 接口继续保留，适合既有书包盘点、临时检索与有界读段；两类包的字段、目录和坐标不能混用。

本 Skill 的轻量本地模块提供 `inventory/index/search/read/verify`：盘点层次、抽取/建立索引、发现候选、读指定上下文、复核快照及来源链。工具不联网、不加载语言模型，不替宿主做语义阅读、作者鉴真、角色状态判断或评级。统一入口为 `python -X utf8 SKILL_ROOT/scripts/battle.py novel --input request.json --output result.json`，可用 `battle.py novel --help` 查公共参数；`novel_evidence.py` 只导出 `run(request)`，没有独立 CLI。它与 `research` 的区别是直接操作显式提供的本地正文，而不是只索引宿主预填的证据记录。

### 可运行的隔离示例

下面在唯一的新目录创建**合成短文夹具**，与真实书及 Skill 安装目录分开；只演示接口，不是角色取证或评级。本次升级已在隔离目录实际跑过同样五个操作：倒序搜索命中第 6、3 行，读取第 4–6 行，快照校验通过，`original_verified` 仍为 false。

```powershell
# 从仓库根目录执行；独立安装者把这一行改为自己的Skill目录。
$skillRoot = (Resolve-Path -LiteralPath './skills/battle-scaling').Path
$demoRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('novel-demo-' + [guid]::NewGuid().ToString('N'))
$inputDir = Join-Path $demoRoot 'input'
New-Item -ItemType Directory -Path $inputDir -Force | Out-Null
$sourcePath = Join-Path $inputDir '合成短文.md'
@'
第一章 夹具开端
此文本为合成测试，不是作品原文。
木片出现裂纹。
第二章 夹具结尾
角色并未出手。
旧木片裂纹仍在。
尾声 若干年后
这里没有战斗，只测试倒序定位。
'@ | Set-Content -LiteralPath $sourcePath -Encoding utf8

function Invoke-NovelDemo($stepName, $request) {
    $requestPath = Join-Path $demoRoot ($stepName + '-request.json')
    $resultPath = Join-Path $demoRoot ($stepName + '-result.json')
    $request | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $requestPath -Encoding utf8
    python -X utf8 "$skillRoot/scripts/battle.py" novel --input $requestPath --output $resultPath | Out-Null
    if ($LASTEXITCODE -ne 0) { throw ('novel CLI failed: ' + $stepName) }
    Get-Content -LiteralPath $resultPath -Raw -Encoding utf8 | ConvertFrom-Json
}

$inventory = Invoke-NovelDemo '01-inventory' @{op='inventory'; source=$sourcePath}
$indexed = Invoke-NovelDemo '02-index' @{
    op='index'; source=$sourcePath; output_dir=(Join-Path $demoRoot 'snapshots')
    work_id='synthetic:demo'; edition_id='synthetic:v1'
}
$found = Invoke-NovelDemo '03-search' @{
    op='search'; bundle=$indexed.bundle; keywords=@('裂纹')
    limit=20; context_lines=1; order='ending_backward'
}
$read = Invoke-NovelDemo '04-read' @{
    op='read'; bundle=$indexed.bundle; source_id=$indexed.sources[0].id
    line_start=4; line_end=6; context_lines=0
}
$verified = Invoke-NovelDemo '05-verify' @{
    op='verify'; bundle=$indexed.bundle; check_originals=$true
}
$found.results | Select-Object source_id,chapter,match,line_start,line_end,exact_text
$read.window
$verified | Select-Object snapshot_integrity,original_verified,originals
```

真实任务把 `source` 改为显式本地 TXT/MD/EPUB/DOCX、refpack 根目录或其 chunks 目录；`work_id/edition_id` 改为实际作品与版本 ID。`output_dir` 必须在原书/refpack 工程之外，每次 index 新建 `novel-<UUID>` 快照；后续 `bundle` 使用实际返回路径，不猜目录名。

不使用 PowerShell 辅助函数时，将下表**单个对象**保存为 `request.json`，把路径与 ID 换成实际值，再分别运行统一命令；`<实际bundle>` 来自 index 返回，`<实际source_id>` 来自其 `sources[].id`，不能照字面提交占位：

| 操作 | 单个 JSON 请求 |
|---|---|
| 盘点 | `{"op":"inventory","source":"D:/小说/原文.txt"}` |
| 建索引 | `{"op":"index","source":"D:/小说/原文.txt","output_dir":"D:/论战输出/本次任务/snapshots","work_id":"作品ID","edition_id":"版本ID"}` |
| 搜索 | `{"op":"search","bundle":"<实际bundle>","query":"裂纹","limit":20,"context_lines":10,"order":"ending_backward"}` |
| 读段落 | `{"op":"read","bundle":"<实际bundle>","source_id":"<实际source_id>","line_start":4,"line_end":6,"context_lines":0}` |
| 复核 | `{"op":"verify","bundle":"<实际bundle>","check_originals":true}` |

```powershell
python -X utf8 "$skillRoot/scripts/battle.py" novel --input request.json --output result.json
```

| 操作 | 请求与结果要点 |
|---|---|
| `inventory` | `source` 必填。返回 `candidates`、`derived_navigation`、`warnings`。项目根优先 raw，再考虑 chunks；不会递归猜哪份稿件是原件。项目配置不执行，也不自动跟随其中的外部 source 路径。 |
| `index` | `source/output_dir/work_id/edition_id` 必填；文本非 UTF-8 时显式给 `encoding`，不丢乱码。返回 `bundle` 与 `sources[].id`、原件/文本哈希、章索引。原件身份仍未认证。 |
| `search` | `bundle` 加单个 `query` 或字面 `keywords` 数组；`keywords` 按任一词命中，非语义/正则搜索。`limit` 为 1–200，`context_lines` 为 0–50；`order` 默认 `ending_backward`，另可 `forward`。结果在 `results`，不是 `hits`；每项有 `exact_text/chapter/match`、上下文行/字符范围、两种哈希与 `role`。 |
| `read` | `bundle/source_id/line_start` 必填，`line_end` 默认同一行；每次显式范围最多 500 行，另可 `context_lines:0..50`。结果为 `window`，不是 `results`。行从 1 起，字符位置为抽取文本 Unicode 字符左闭右开范围；不能当字节、出版页码或其他 chunk 坐标。 |
| `verify` | `bundle` 必填；`check_originals:true` 另外比较原路径文件是否 `unchanged/changed/unavailable`。`snapshot_integrity:true` 仅说明保存的原件/文本及清单哈希一致，不保证签名真实性、抽取完整性或语义正确。 |

窗口若 `truncated:true`，不得把请求范围当全部已展示；实际 `line_start/line_end/char_start/char_end/exact_text` 才是返回内容。`search.match` 指命中本身，窗口范围包含上下文；涉及跨章判断时实际扩展 read。显式索引派生文件时仍保留 `role:derived_navigation_only`，不能靠 index 把摘要/项目 canon 升级成原文。所有操作的 `original_verified` 始终为 false；宿主完成原件身份核查后另记录依据，不能改说工具已认证原作。

已有可读正文或 refpack 时优先读取，完整论战任务包优先使用上面的自包含新库，不重跑写作流水线。以下原工程命令仅用于用户明确要求操作该工程时的兼容说明，`<...>` 必须替换，不是已执行回执：

```powershell
# 在现有 LOCAL_UPSTREAM_ROOT/novel-refpack 工程目录；新建写入独立书包。
python -X utf8 tools/book.py new --source "<正文绝对路径>"
# 上一步实际生成的 book.json 路径用于下面两步。
python -X utf8 scripts/00_extract.py --config "<work/书包/book.json的实际路径>"
python -X utf8 scripts/01_split.py --config "<同一book.json的实际路径>"
python -X utf8 tools/book.py verify --slug "<实际书包slug>"
```

本次未运行这条生成流水线；审查仅对既有包运行了只读 `verify`，并核对代码、原件和派生产物。`00_extract` 支持删标题参数，必须记录是否使用和删去内容，不能静默删去原作结尾。不要为取证默认运行 `12_run_all --no-llm`：本机该参数只跳过两个模型步骤，仍执行摘要合并、卷映射、台词/文风/例子/整书总结等派生步骤，不能保证已经读懂全文。外部工程路径是本机已核入口，不是可移植依赖；其他机器先查实际路径与帮助。

## 覆盖记录与停止条件

分开保存：盘点范围、建立索引/关键词扫描范围、实际逐段读取范围、已核版本/结尾范围、未读或改写范围。全书已索引、七种渠道搜过、哈希校验通过、关键词命中很多，均不等于全书精读或表现穷尽。

沿用 [research.coverage](research-workflow.md) 的 `plan/tasks/attempts`：实际查询、工具/平台、日期、已查章节范围、来源 IDs、阻断和未命中都记录。精读范围放工作表/证据卡并由来源定位引用，不能把未执行计划填作完成。主要结论已有可追溯支持、关键冲突已处理，或资料/预算耗尽时可停止；交付原因与缺口。预算耗尽、关键词无命中不证明角色没有能力。

首次小说完整档案尚未通过宿主验收时，上述停止只能形成部分覆盖的暂定交付，并保留完整拆书待办；不因局部已有结论就宣布完成完整评级或取消建档优先级。

## 吸收来源与边界

借鉴用户提供的 combat-scaling 第18章（来源定位标识） 的“结构拆书→关键词→回原文→四表”思想，并结合本机 novel-refpack 审计（来源定位标识） 修正正文与项目 canon 的关系。该本地审计链接只用于追溯本次升级，不是 Skill 运行依赖。

不移植固定证据条数、被秒降两档、被压制差一档、hax 一数量级容差、固定媒介优先级和源方量级表；按用户最新确认保留统一综合主档、三类表现参考、九属性、结尾倒查、表现优先及特能双上限。1.6.0轻量模块未复制写作流水线；1.7.0新增独立论战拆书库，保留MIT来源通知并替换摘要压缩、写作和文风验收用途，未引入上游模型。源码审查差异、许可与实际边界见 [完整流水线](novel-refpack-pipeline.md)。
