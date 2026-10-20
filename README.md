# battle-scaling：论战评级与 VS Agent Skill

为能搜索网页、读取原作和理解图片的 Agent 提供论战工作流，配套可复算的 Python 工具与独立小说拆书库。默认使用当前 Agent 完成搜证和语义判断，不需要下载其他项目的模型。

## 能做什么

- **角色评级**：常态、最高、扒下限三种取证口径独立；默认先给一个明确常态主档，再列输出、体防、智力、战斗智商、经验、特殊技能、破坏、速度、体量及来源和叠法。
- **表现审查与物理推算**：审查因果链、实际出力、疲劳/伤势/战意、材料和外援；区分力、功、能量、功率、作用范围，保存公式、参数来源、假设及中间值。
- **关系叠加与高层结构**：按属性、版本和状态建证据关系，核查循环、倍率和继承条件；使用具名规则分析有限量级、数学结构和高层叙述。
- **VS**：默认宏观胜负推演；明确要求具体战况时，按行动→命中→防御/反制→伤势与状态→后续行动展开。叙述不产生新战绩，分支数量不直接变胜率。
- **小说取证**：TXT/MD/EPUB/DOCX快照、结尾倒序阅读任务、精确引句定位、正反表现、状态线、交锋、九维缺口、候选CASE与覆盖审计。

工具验证数值、定位、结构和依赖；原文语义、建模是否适用、跨作品兼容与最终裁决由宿主 Agent 负责。索引生成、哈希校验和程序测试不代表自动读懂全部作品或证明任意评级正确。

## 目录

```text
skills/battle-scaling/           Agent Skill、规则、工具、模板与测试
tools/combat-novel-refpack/      可独立运行的论战拆书库
tools/import_handbook_corpus.py  从用户本地导入可选量级册OCR资料
tools/verify_package.py          检查发布版静态文件指纹
docs/public-distribution.md      公开版资料范围与可选依赖
NOTICE.md                       来源及许可边界
```

## 安装到 Agent

克隆本仓库后，将 `skills/battle-scaling` 整个文件夹安装到你的 Agent 技能目录。Codex 的典型位置为 `~/.codex/skills/battle-scaling`；其他支持 `SKILL.md` 的 Agent 按各自规则安装。已有同名技能时，先比较或备份，避免直接覆盖本机数据。

支持通过 GitHub 路径安装技能的工具可使用：

```text
https://github.com/LEE-path/battle-scaling/tree/main/skills/battle-scaling
```

Python 3.11+。核心工具和小说管线使用标准库；视频、图像/OCR、科学计算等具体任务可能按需使用 ffmpeg/ffprobe、Pillow、PyMuPDF 或其他工具。宿主需自行提供实际可用的网页搜索和视觉能力。

## 快速验证

从仓库根目录运行：

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py doctor
python -X utf8 tools/verify_package.py
python -X utf8 skills/battle-scaling/scripts/battle.py physics --input skills/battle-scaling/assets/cases/physics-earth-binding.json
```

运行合成对战夹具，输出放到新的目录：

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py analyze --input skills/battle-scaling/assets/cases/pk-dual-presentation-synthetic.json --mode all --output runs/demo-overview
```

这些夹具验证工具行为，不是新的真实角色评级。真实任务由 Agent 搜集证据、编制 CASE，并按 `SKILL.md` 接续审查。

## 小说拆书

详细说明见 [独立拆书库](tools/combat-novel-refpack/README.md) 与 [Skill小说管线](skills/battle-scaling/references/novel-refpack-pipeline.md)。

```powershell
python -X utf8 tools/combat-novel-refpack/refpack.py prepare --source book.txt --output runs/book-bundle --work 作品名 --edition 明确版本
python -X utf8 tools/combat-novel-refpack/refpack.py tasks --bundle runs/book-bundle
```

当前 Agent 按任务实际读原文、填写回执并顺序 `accept`，随后 `build/verify`。该脚本没有内置语言模型；单独运行 `tasks` 不会完成语义阅读。`partial` 明确保留未读范围，`CASE.candidate.json` 还需表现、物理、特能和量级审查。

## 公开版资料范围

保留代码、规则表、必要来源指纹、测试、模板、使用说明和第三方许可通知。公开包不附原小说全文、量级册PDF/完整OCR、原作截图、模型权重、站点运行数据库、密钥或原机器的可选工具路径。

默认有限/高层规则计算仍可运行。**量级册全文检索和原图回看需要你另行提供对应本地资料**，不能把未安装资料说成已经读过。导入方式及限制见 [公开版说明](docs/public-distribution.md)。

## 测试

```powershell
python -X utf8 -m unittest discover -s skills/battle-scaling/tests -v
python -X utf8 -m unittest discover -s tools/combat-novel-refpack/tests -v
```

测试覆盖具体输入的计算、约束、证据定位与状态结算，不保证任意作品的取证完整性、视觉测量准确率或未经校准的胜率。需要本地可选资料的测试会明确跳过，不将跳过计作功能通过。

## 来源与许可

外部研究只吸收目的、资料结构与流程，详见 [吸收边界](skills/battle-scaling/references/external-ideas.md)。上游模型不进入运行链。整个仓库尚未统一指定开源许可证；既有第三方许可保留并分别适用，见 [NOTICE](NOTICE.md)。
