# Current-package content and provenance audit / 当前发布包内容审计

审计更新：2026-10-24，Asia/Shanghai。范围：battle-scaling 1.12.3 发布包与随附拆书工具，不涵盖 Git 历史。

## 分发内容与权利边界

| 内容 | 发布处理 |
|---|---|
| 原作图片、影视片段、参考册 PDF／完整 OCR | 不随包分发；保留必要来源链接、页码、哈希、已核规则和独立条件算例。 |
| 站点运行数据库、验收日志、机器配置 | 不随包分发；安装后按工具文档建立运行资料。 |
| 完整同人作品与教学故事 | 不随包分发；写作参考采用独立表述的可复用方法，不附故事全文、对白或情节摘录。 |
| 汪吧参考册相关规则 | 保留数值、公式、具名档位、条件、必要短引、来源指纹与独立解释；未将整册或帖文声称为 MIT 授权。 |
| VSB 改编说明与配置 | 保留原始链接与已核修订；按第三方说明标注 CC BY-SA 3.0、署名和修改范围。 |
| 外部工具与研究项目 | 区分实际可选依赖和方法参考，保留真实上游链接及各自许可；不预置模型权重或外部项目全库。 |

事实、数学方法、必要引用与受保护的具体表达分别处理。鸣谢不等于取得完整作品的再分发授权，独立程序的 MIT 许可也不覆盖第三方内容。详见[第三方说明](../THIRD_PARTY_NOTICES.md)与[来源回执](../UPSTREAM-SOURCES.json)。

## 写作资料

[可复用写作经验](../skills/battle-scaling/references/writing-experience.md)覆盖人物声线、合理入场、动作空间、反馈变招、强弱差、未知信息、身份控制、幽默、对白和结局收束。方法不作为既有角色的量级、抗性或胜负证据，完整独立评级与原作人设核查继续执行。

## 引用与版本完整性

结构化参考规则保留功能所需字段、页号与原件指纹，排除完整原册 OCR 和非功能性的聊天／账号叙述。引用元数据的精简不改变数值门槛、公式或独立解释；任何字符阈值均不是法律上的通用安全线。

发布文件的字节数与 SHA-256 由 `skills/battle-scaling/package-manifest.json` 记录，可使用 `python tools/verify_package.py` 检查。分发字节变化后须更新清单；合成评级夹具变化时须复核其指纹及导入结果。程序校验不替代原作核查、文笔评价或法律判断。

[SCP Licensing Guide](https://scp-wiki.wikidot.com/licensing-guide)说明相关衍生作品的署名与相同方式共享要求；SCP 的许可不自动授予其他商业角色的权利。

## English summary

This review covers the current v1.12.3 distribution and bundled novel tools, excluding Git history. Original scans, complete OCR, source screenshots, model weights, runtime databases and machine-specific configuration are not bundled. Writing guidance contains reusable methods without full stories, dialogue excerpts or plot retellings. Functional rules, mathematical methods, source locators and fingerprints remain.

Original software and documentation use MIT with explicit third-party exceptions. Adapted VSB references retain CC BY-SA 3.0, attribution and source links. Optional dependencies and research references are separately identified. Acknowledgement is not redistribution permission. File manifests validate package integrity, not semantic correctness, literary quality or legal clearance. This review is not a warranty of non-infringement.
