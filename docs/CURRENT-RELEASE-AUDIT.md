# Current-package content and provenance audit / 当前发布包内容审计

审计日期：2026-10-23，Asia/Shanghai。范围：拟发布的 battle-scaling 1.12.2 当前内容及其独立拆书工具；不涵盖 Git 历史，不是法律意见或无侵权保证。

## 核查结果与发布处理

| 内容 | 查到的实物／证据 | 当前发布处理 |
|---|---|---|
| 原作图片、影视片段、参考册 PDF／完整 OCR | 本地 Skill 存在电影接触表、参考册裁图及完整 `pages.jsonl`；不是公开再分发授权 | 不随公开包分发。必要来源链接、页码、哈希、已核规则与独立条件算例保留。 |
| 私有运行资料 | 累计站点 SQLite、主机验收与可选工具路径 | 排除运行库和本机回执；运行时可按用户授权新建本地档案。脱敏发布副本中的工作区路径，原始来源哈希不变。 |
| 四篇既有角色交叉同人全文 | 原先在本地获用户肯定的创作文稿；涉及第三方商业人物，部分还涉及 SCP 衍生许可 | 本地原稿不改动、不删除。公开副本采用四篇独立原创合成教学全文与新索引，不逐字换名，也不冒称新稿已获原有文笔认可。物理、未知反馈、身份控制、喜剧四类方法完整保留。 |
| 汪吧参考册 | 有版本、原件哈希、实际阅读页号与短引；未见整册整体再授权证据 | 保留功能所需的数值、公式、具名档位、条件、必要短引与独立规则解释；排除完整原册、原图和非功能性的圈史／聊天／账号争议叙述。署名不被解释为取得整册版权。 |
| VSB 等公开规则说明 | 有原始链接、部分 revision 和读取范围 | 由仓库第三方许可说明分别披露实际来源、改编与适用许可；不能把所有外部来源统一套成软件 MIT，也不能以第三方规则代替原作核证。 |
| 外部项目目的与流程 | 包内已有九项公开来源与方法吸收边界 | 保留公开链接及独立实现边界，不要求已经清理的本机外部源码、模型或档案存在。实际依赖与仅参考来源在第三方说明分别列出。 |

上述处理不是“公开项目等于无版权”或“同人必然侵权”的判断。事实、数学公式、方法、短引、独立分析与受保护的具体表达应分开评估；不能靠加鸣谢给未经许可的完整作品清权。

原册结构化 JSON 的引文元数据在清理前有 437 处、含重复合计 5,483 字符；165 个不同引句合计 2,098 字符，最长 83 字。统计覆盖三个校勘 JSON 与八个汪吧 ruleset，不含已排除的完整 OCR。公开转换去除页级圈史引文以及超过 25 字的重复 `short_quote/short_excerpt` 元数据；运行条件、数字、公式、档名、页号、源哈希和独立解释不因删重复引文而改变。25 字是此次工程精简阈值，不是法律上的通用安全线；保留短引仍须结合引用目的与范围。

## 范例替换的具体目的

- `original-load-path.md`：持续拉力与冲击吸能分开、支点与关节控制、明确非致命结果。
- `original-feedback-and-disable.md`：从当场失败获得线索，资源和时间有代价，确认失能而不冒称死亡。
- `original-role-control.md`：自设控制机制先明确，受控身份内保留性格与反抗，线索及现实拘束清楚闭合。
- `original-comic-causality.md`：自设纸偶的媒介认知与幽默实际影响事件，但不获得全知、控稿或不败。

这些教学文本是原创设定示范，不是任何第三方作品的表现、评级、抗性或胜负证据。既有作品角色在实际任务中仍须使用完整独立评级与原作人设核查，不能拿教学设定替代。

## 可复核的官方许可入口

- [SCP Licensing Guide](https://scp-wiki.wikidot.com/licensing-guide)：衍生作品的来源／作者署名及 CC BY-SA 要求；因此本次不把未经处理的混合商业角色同人直接加一个 CC 标记后公开。
- [SCP-3143 原条目](https://scp-wiki.wikidot.com/scp-3143)：原作者 The Great Hippo；[SCP 官方作者索引资料](https://scp-wiki.wikidot.com/user-curated-lists)列出 SCP-096 作者 Dr Dan。这里提供来源事实，不分发条目全文。

按项目名称在仓库的第三方鸣谢页进入实际 GitHub 上游。未能证实的 GitHub 地址不编造；有些资料来源为网站、论文或本地原始工程，不存在已核 GitHub 上游。

## 发布转换边界

`sanitize_public.py --root PUBLIC_REPOSITORY` 仅作用于具有 `skills/battle-scaling/SKILL.md` 的公开仓库副本，拒绝直接编辑全局 Skill 安装路径，保留规则核心字段及原件页号／哈希。实际删改路径、原因、文件字节与哈希写入 `docs/public-content-transform.json`。

路径脱敏与公开材料缩减会改变分发字节；必须随后重新生成公开包清单，并重建／复核合成评级夹具的文件指纹、运行相关测试。旧本地校验哈希不能冒充新公开包校验。不会因为审计而删除独立搜证、物理推算、叠链、双标准评级、完整对战或写作流程。

## English summary

This review covers the current 1.12.2 distribution, not Git history. Original book scans, full OCR, film contact sheets, private databases and host-only artifacts are excluded. Functional rules, mathematical methods, source locators and hashes remain. Four crossover fanfiction samples are replaced in the public copy by independently written original teaching stories; the private originals are untouched. Nonfunctional community-history and account/chat summaries are omitted. Attribution and the actual terms of each reused component are documented separately; acknowledgement alone is not copyright clearance. No claim of non-infringement or comprehensive legal review is made. Rebuild the public manifest and synthetic-fixture fingerprints after transformation.
