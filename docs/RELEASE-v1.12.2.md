# v1.12.2 — Integrated scaling, battle writing and audited distribution

## 中文

本次将最新全局 Skill 的完整流程同步到公开仓库：一个综合主档、九维评级、汪吧／完整 VSB 双标准、独立评级先行的 PK 与故事版、证据补齐及小说拆书档案。故事版保留完整评级要求，并取消强制新增读图。

- 原创代码与原创文档采用 MIT；补齐真实上游、依赖和方法参考的链接及鸣谢。
- VSB 改编资料明确标注 CC BY-SA 3.0；修复 Cited Feats 导入器对普通数据／SCP 数据的逐条许可、署名与未决状态处理。
- 保留 novel-refpack 上游 MIT 通知；说明 PyMuPDF 的 AGPL／商业许可与其他可选工具各自条款。
- 公开包排除原作图片、完整 OCR、模型、私有运行资料；以独立原创教学故事替代未完成公开授权处理的交叉同人范例，本地原稿不变。
- 新增中英 README 与原创中英头图。修复公开同步后的可选原册支持，并重建可移植的合成测试档案指纹。

验证：Skill 848 项测试，2 项需可选原资料而跳过，其余通过；独立拆书库 24 项通过；包清单、链接、脱敏和素材排除检查通过。测试不代替宿主对原作和评级的语义核查。

审计仅覆盖当前发布包，不包括 Git 历史，不构成无侵权保证。详细许可见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)，当前审计见 [CURRENT-RELEASE-AUDIT.md](CURRENT-RELEASE-AUDIT.md)。

## English

This release syncs the latest complete Skill: one integrated character tier, nine attributes, Wangba and full VSB standards, independent ratings before VS/story writing, evidence-gap recovery and the novel evidence pipeline. Story mode retains complete internal ratings without mandatory new image reading.

Original code and documentation use MIT, with third-party exceptions and verified upstream links. VSB adaptations retain CC BY-SA 3.0. The Cited Feats adapter now preserves per-record licensing, attribution and unresolved provenance instead of applying a blanket license. The novel-refpack MIT notice and optional dependency terms are documented.

The public package excludes original scans, full OCR, model weights and private runtime records. Independently written original teaching stories replace crossover samples whose public redistribution terms were incomplete; private originals remain unchanged. Bilingual READMEs and original bilingual banners are included.

Validation: 848 Skill tests (2 optional-original-source tests skipped; all others passed), 24 standalone novel-tool tests passed, plus manifest, link, privacy and excluded-media checks. Tests do not replace the host's semantic review of canon or ratings. The audit covers the current distribution only, not Git history, and is not a warranty of non-infringement.
