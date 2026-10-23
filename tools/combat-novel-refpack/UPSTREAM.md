# novel-refpack 来源与论战改造 / Provenance and combat adaptation

核查日期 / Reviewed: **2026-10-23**。仅针对当前发布包；没有扫描 Git 历史。 / Current release package only; Git history was not scanned.

## 已确认来源 / Confirmed upstream

上游为 **[scp3500/novel-refpack](https://github.com/scp3500/novel-refpack)**，采用 [MIT 许可证](https://github.com/scp3500/novel-refpack/blob/main/LICENSE)，版权通知为 **2026 novel-refpack contributors**。

The upstream project is **[scp3500/novel-refpack](https://github.com/scp3500/novel-refpack)**, licensed under [MIT](https://github.com/scp3500/novel-refpack/blob/main/LICENSE), with the notice **2026 novel-refpack contributors**.

早期本地参考工程没有 `.git`，此前只能记录文件指纹，不能从该现场确定远端。此次找到公开上游，并将公开 `main` 原件与原本地参考副本逐字节比对，确认如下来源关系。这不意味着知道历史下载所用的提交号；**旧下载提交号仍为未知**，不使用今天的分支状态冒充它。

The earlier local reference directories had no `.git`, so their remote could not originally be established from the checkout. The public upstream has now been located and its `main` files compared byte for byte with the original local copies. This establishes the source relationship below, but **the commit used by the historical download remains unknown**. Today's branch state is not substituted for that missing revision.

| 原文件 / Source file | 本次读取的公开文件 / Public file inspected | SHA-256 | 比对结论 / Match |
|---|---|---|---|
| `LICENSE` | [raw source](https://raw.githubusercontent.com/scp3500/novel-refpack/main/LICENSE) | `ccb9eb4a40e1bbccd09555ed5bad1b532729c67eac349022735ee53eba7f425f` | 两份原本地参考副本字节一致 / Exact match to both original local copies |
| `README.md` | [raw source](https://raw.githubusercontent.com/scp3500/novel-refpack/main/README.md) | `16df958a3e3913c0fb97f8e776b028cb8914e58b3cabbf72e5e9be4b89b77ec5` | 与早期原样参考副本字节一致；后续本地扩展版不同 / Exact match to the early unmodified copy; the later locally extended edition differs |
| `scripts/00_extract.py` | [raw source](https://raw.githubusercontent.com/scp3500/novel-refpack/main/scripts/00_extract.py) | `1edf94dfd4f78c054be0c5eba0200efea1f0c387e645418576a1600191bfa0bb` | 两份原本地参考副本字节一致 / Exact match to both copies |
| `scripts/01_split.py` | [raw source](https://raw.githubusercontent.com/scp3500/novel-refpack/main/scripts/01_split.py) | `a03ee7895c3d06ebe3f348fb6acfc93bf795363a6e65e49cd8c3b63d72d53023` | 两份原本地参考副本字节一致 / Exact match to both copies |
| `lib/textio.py` | [raw source](https://raw.githubusercontent.com/scp3500/novel-refpack/main/lib/textio.py) | `a6d780018821853e878bd78a2ace882650998e8773a2621899ecfc902e2d571c` | 两份原本地参考副本字节一致 / Exact match to both copies |

这些指纹仅证明被读取文件的身份与匹配关系，不表示逐行安全审计、原作认证或完整语义阅读。 / These fingerprints establish the inspected files' identity and matching relationship, not a line-by-line security audit, canon certification or complete semantic reading.

## 参考、保留与改造 / Influence, retention and changes

| 上游目的 / Upstream purpose | 本论战版 / Combat edition |
|---|---|
| 单书隔离、显式原件与结构抽取 / Single-book isolation, explicit source and extraction | 保留设计目的；原件快照、来源哈希与输出目录分离 / Retains the design goal; separates source snapshots, source hashes and outputs |
| 分章与有界切片任务 / Chapter and bounded chunk tasks | 用于逐段实际阅读、逐字定位与覆盖核查 / Used for actual reading, exact locations and coverage review |
| 分片、卷、整书摘要 / Chunk, volume and whole-book summaries | 改为能力、表现、反例、状态、关系和终点档案；摘要不能替代原文 / Reorganized into ability, feat, counterexample, state, relation and endpoint records; summaries do not replace the source |
| 写作、文风例子与工作 canon / Writing examples, style and working canon | 不作为原作事实；不移植上游书包、续写内容或私有 canon / Not treated as original-work facts; upstream book packs, continuations and private canon are not bundled |
| 模型摘要后端 / Model summarization backend | 不内置或分发模型；由宿主 Agent 实际阅读，脚本负责定位、任务和产物验证 / No bundled model; the host Agent performs actual reading while scripts manage locations, tasks and artifact checks |
| 文件存在与流程完成检查 / File and workflow completion checks | 增加输入指纹、来源版本、回执和宿主验收；程序通过不等于语义正确 / Uses input fingerprints, source versions, receipts and host acceptance; structural success does not prove semantic correctness |

当前 `combat_refpack` 是随包自包含的论战实现，正常运行不需要安装原 novel-refpack，不执行其配置，不访问旧工程目录，不要求固定盘符，也不继承其 API 密钥。保留 MIT 通知是来源与许可记录，**不表示原项目承担本论战版结果的责任**。

The packaged `combat_refpack` is a self-contained combat-research implementation. It does not require the original novel-refpack installation, execute upstream configuration, access historical directories, require fixed drive letters or inherit API credentials. The preserved MIT notice records provenance and licensing; **it does not make the upstream authors responsible for this edition's results**.

## 许可与数据边界 / License and data boundaries

`LICENSE.upstream-novel-refpack` 原样保留上游 MIT 通知；Skill 副本为 `assets/licenses/novel-refpack-MIT.txt`。项目原创代码的根 MIT 许可不撤销或替换这份通知。上游软件许可不覆盖所处理小说的著作权；使用者须有相应原文访问与处理权，发布分析不等于可发布整书或原书包。

`LICENSE.upstream-novel-refpack` preserves the upstream MIT notice unchanged; the Skill copy is `assets/licenses/novel-refpack-MIT.txt`. The root MIT license for original project code does not remove or replace that notice. The upstream software license does not license the novels being processed. Users need appropriate rights to access and process their inputs; publishing an analysis does not authorize redistribution of complete books or source packs.

发布包没有附带原工程、小说原文、模型权重、训练数据、凭据或外部服务配置。更广的第三方来源与许可证见仓库根目录的 `THIRD_PARTY_NOTICES.md`；实际核查回执见 `UPSTREAM-SOURCES.json`。

The release includes no original upstream installation, novel texts, model weights, training data, credentials or external service configuration. See the repository root's `THIRD_PARTY_NOTICES.md` for other sources and licenses and `UPSTREAM-SOURCES.json` for the actual verification receipts.
