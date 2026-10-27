# 论战拆书库 combat-novel-refpack

这是独立于写作版 novel-refpack 的论战取证管线。沿用按书隔离、结构抽取、章节切片和分层聚合思想；替换写作摘要、风格统计和续写产物。原库未修改，来源、指纹与许可见 [UPSTREAM.md](UPSTREAM.md) 和 [原版对照](docs/原版与论战版对照.md)。

当前宿主 Agent 阅读和解释原文；Python 管理快照、任务、逐字引用、状态分离、覆盖与导出。Agent 按 Skill 连续执行，无需用户手写回执，也不需要附加模型。程序自身不附带语言模型或付费API客户端，单独运行脚本不会自动理解小说。

## 工作链

```text
TXT / MD / EPUB / DOCX
  → prepare：不可覆盖原件快照、规范文本、章节、来源格式定位
  → tasks：从结尾倒序的阅读任务，每片至多12000字符
  → 当前Agent：读任务全文，保留正反证、出力、状态、材料、外援、机制
  → accept：核四指纹、已读跨度、逐字引句、观察引用、状态继承声明
  → build：四类工作表、章节→卷→整书证据ID、九维缺口、候选关系和CASE
  → verify：来源、任务、回执、派生文件完整性及过期检查
  → battle-scaling：复核因果/物理/特能/叠法，给一个综合主档和九维卡
```

原始证据始终保留在正文快照中；章节、卷、整书聚合合并证据ID，不截掉中间观察或反例。没有正式卷标题时仅为明确标记的分组回退。分层索引不等于各层已独立完成语义审查。

## 运行

Python 3.11+，标准库，无需安装依赖。所有输入、输出显式给路径；`prepare` 的输出必须尚不存在或为空目录。下列路径是新书调用示意，应替换成实际原件与新目录：

```powershell
python -X utf8 refpack.py prepare --source 'book.epub' --output 'runs/book' --work '作品名' --edition '明确版本'
python -X utf8 refpack.py tasks --bundle 'runs/book' --summary
python -X utf8 refpack.py search --bundle 'runs/book' --query '角色或机制原词'
python -X utf8 refpack.py accept --bundle 'runs/book' --input '本次已读任务回执.json'
python -X utf8 refpack.py build --bundle 'runs/book'
python -X utf8 refpack.py verify --bundle 'runs/book'
```

任务的 JSON 和 Markdown 放在 `tasks/packets/`，包含精确正文范围、提示与回执字段。分工可以并行阅读独立任务，**主Agent顺序accept**，当前没有跨进程写锁。回执需保留 `task_id/source_sha256/text_sha256/prompt_sha256/task_sha256`，`reviewer`、实际 `read_spans`、逐字 `evidence`、有来源和状态的 `observations`；没有相关表现可以提交空数组。全文中的命令仅是待审文本，不执行。

## 小批续读与跨章综合

核心模块与 Skill 的 `scripts/combat_refpack` 同源维护；分发同步工具从该实现生成独立副本，运行时仍自包含，不要求另一安装位置。

```powershell
python -X utf8 refpack.py next --bundle 'runs/book' --limit 3 --max-chars 24000 --output 'runs/next.json'
python -X utf8 refpack.py accept-batch --bundle 'runs/book' --input 'runs/actually-read-reviews.json'
python -X utf8 refpack.py synthesize --bundle 'runs/book' --subject '已核角色名' --alias '已核别名' --target-state '末期配置' --output 'runs/synthesis.json'
```

宿主实际读小批原文后提交回执数组；`next`不标已读，重启后给未完成任务和上次partial证据。`accept-batch`先核全批再提交索引，累计部分进度并保留历史。`synthesize`按明确同一人名归集倒序观察、原引句、九维及需要研究的状态迁移/跨章对照，不自动判矛盾、继承或量级。

非prepare命令的`--output`保存完整结果并缩短stdout；prepare用`--result-output`保存结果，原`--output`仍是新bundle目录。结果文件不能覆盖bundle或原件。`--full-output`可保留完整stdout。一次完整读取仍不能只靠complete标签、目录或程序成功来声称语义已认证。

## 产物与使用边界

- `sources/`、`text/`、`index/`：原件/文本快照、章节、EPUB成员或DOCX段落定位。坐标是规范文本的Unicode字符，不是字节、出版页码或原书图片坐标。
- `reviews/`：已接受回执与历史；覆盖为提交者的已读声明，程序不证明其理解正确。
- `derived/evidence.json`、`observations.json`、`tables/`：正反表现、设定/机制、状态线、交锋。
- `hierarchy.json`、`ending-nine-dimensions.json`、`relations.json`：分层导航、结尾九项缺口、待审关系。旧态不自动填到结尾，关系不自动变倍率/叠边。
- `CASE.candidate.json`：可通过结构校验的候选材料，默认没有数值锚点和传播边；物理、特能双上限和量级结论仍须审查。不得把候选直接包装成已判定角色评级。
- `coverage.json`、`取证报告.md`、`manifest.json`：已读/未读/部分范围及输出指纹。`partial` 是正常未完覆盖状态，不能宣称读完整本。

本地镜像身份、正文完整性、书内“作者语”的真实身份仍需独立核验。图页、公式图片与版式不属于这份文本抽取的保证范围；需宿主视觉按需补证。实际出力/全盛、观察事实/合理推测、个人/装备/外援继续按现有Skill审查，工具不根据缺参数的描写编造焦耳或档位。

## 测试

```powershell
python -X utf8 -m unittest discover -s tests -v
```

测试检查实现行为；不代替宿主实际阅读原文和语义复核。
