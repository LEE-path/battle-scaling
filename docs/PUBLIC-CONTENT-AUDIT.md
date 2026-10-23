# Current-package content and provenance audit / 当前发布包内容审计

首次审计：2026-10-23；当前内容更新：2026-10-24，Asia/Shanghai。范围：battle-scaling 1.12.3 当前内容及其独立拆书工具；不涵盖 Git 历史，不是法律意见或无侵权保证。

## 核查结果与发布处理

| 内容 | 查到的实物／证据 | 当前发布处理 |
|---|---|---|
| 原作图片、影视片段、参考册 PDF／完整 OCR | 本地 Skill 存在电影接触表、参考册裁图及完整 `pages.jsonl`；不是公开再分发授权 | 不随公开包分发。必要来源链接、页码、哈希、已核规则与独立条件算例保留。 |
| 私有运行资料 | 累计站点 SQLite、主机验收与可选工具路径 | 排除运行库和本机回执；运行时可按用户授权新建本地档案。脱敏发布副本中的工作区路径，原始来源哈希不变。 |
| 四篇既有角色交叉同人全文 | 原先在本地获用户肯定的创作文稿；涉及第三方商业人物，部分还涉及 SCP 衍生许可 | 本地原稿不改动、不删除。1.12.2 曾用四篇原创教学故事替代；1.12.3 按用户要求撤下替代故事及全文索引，公开包仅提供独立表述的可复用写作经验，不附故事全文、对白或情节摘录。 |
| 汪吧参考册 | 有版本、原件哈希、实际阅读页号与短引；未见整册整体再授权证据 | 保留功能所需的数值、公式、具名档位、条件、必要短引与独立规则解释；排除完整原册、原图和非功能性的圈史／聊天／账号争议叙述。署名不被解释为取得整册版权。 |
| VSB 等公开规则说明 | 有原始链接、部分 revision 和读取范围 | 由仓库第三方许可说明分别披露实际来源、改编与适用许可；不能把所有外部来源统一套成软件 MIT，也不能以第三方规则代替原作核证。 |
| 外部项目目的与流程 | 包内已有九项公开来源与方法吸收边界 | 保留公开链接及独立实现边界，不要求已经清理的本机外部源码、模型或档案存在。实际依赖与仅参考来源在第三方说明分别列出。 |

上述处理不是“公开项目等于无版权”或“同人必然侵权”的判断。事实、数学公式、方法、短引、独立分析与受保护的具体表达应分开评估；不能靠加鸣谢给未经许可的完整作品清权。

原册结构化 JSON 的引文元数据在清理前有 437 处、含重复合计 5,483 字符；165 个不同引句合计 2,098 字符，最长 83 字。统计覆盖三个校勘 JSON 与八个汪吧 ruleset，不含已排除的完整 OCR。公开转换去除页级圈史引文以及超过 25 字的重复 `short_quote/short_excerpt` 元数据；运行条件、数字、公式、档名、页号、源哈希和独立解释不因删重复引文而改变。25 字是此次工程精简阈值，不是法律上的通用安全线；保留短引仍须结合引用目的与范围。

## 当前写作资料的边界

公开版只保留[可复用写作经验](../skills/battle-scaling/references/writing-experience.md)，覆盖人物声线、合理入场、动作空间、反馈变招、强弱差、未知信息、身份控制、幽默、对白与结局收束。写作经验使用独立表述，不复述原篇情节，不附原句、对白或换名故事；也不作为既有角色的量级、抗性或胜负证据。独立评级与原作人设核查继续执行。

本地私有版的四篇原稿及其索引均保留。此次仅更新当前公开内容与最新发布包，不改写历史版本。方法整理不能自动证明未来文笔与旧范例等同，具体创作仍须按本场人物和结果核稿。

## 可复核的官方许可入口

- [SCP Licensing Guide](https://scp-wiki.wikidot.com/licensing-guide)：衍生作品的来源／作者署名及 CC BY-SA 要求；因此本次不把未经处理的混合商业角色同人直接加一个 CC 标记后公开。
- [SCP-3143 原条目](https://scp-wiki.wikidot.com/scp-3143)：原作者 The Great Hippo；[SCP 官方作者索引资料](https://scp-wiki.wikidot.com/user-curated-lists)列出 SCP-096 作者 Dr Dan。这里提供来源事实，不分发条目全文。

按项目名称在仓库的第三方鸣谢页进入实际 GitHub 上游。未能证实的 GitHub 地址不编造；有些资料来源为网站、论文或本地原始工程，不存在已核 GitHub 上游。

## 发布转换边界

`sanitize_public.py --root PUBLIC_REPOSITORY` 仅作用于具有 `skills/battle-scaling/SKILL.md` 的公开仓库副本，拒绝直接编辑全局 Skill 安装路径，保留规则核心字段及原件页号／哈希。实际删改路径、原因、文件字节与哈希写入 `docs/public-content-transform.json`。

路径脱敏与公开材料缩减会改变分发字节；必须随后重新生成公开包清单，并重建／复核合成评级夹具的文件指纹、运行相关测试。旧本地校验哈希不能冒充新公开包校验。不会因为审计而删除独立搜证、物理推算、叠链、双标准评级、完整对战或写作流程。

## English summary

This review covers the current 1.12.3 distribution, not Git history. The original review was conducted on 2026-10-23 and this content update on 2026-10-24. Original book scans, full OCR, film contact sheets, private databases and host-only artifacts are excluded. Functional rules, mathematical methods, source locators and hashes remain. The four replacement teaching stories and their full-text index have now been removed. Public writing guidance consists of independently worded reusable methods, without story texts, dialogue excerpts or plot retellings; private originals are untouched. Nonfunctional community-history and account/chat summaries are omitted. Attribution and the actual terms of each reused component are documented separately; acknowledgement alone is not copyright clearance. No claim of non-infringement or comprehensive legal review is made. Rebuild the public manifest and synthetic-fixture fingerprints after transformation.
