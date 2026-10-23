# 公开发布范围 / Public distribution

本仓库发布 **battle-scaling 1.12.3** 与自包含的 combat-novel-refpack。只审计和整理当前发布包，不改写 Git 历史。公开包有独立文件清单，不能用本地全量资料的manifest覆盖它。

The repository distributes **battle-scaling 1.12.3** and the self-contained novel dossier library. This review covers the current distribution, not Git history. Its manifest describes public files only.

## 保留 / Included

Agent入口、完整独立评级和九维、汪吧/VSB双标准、物理与高层计算、关系搜证、特能审查、三种对战输出、小说拆书、工具源码、合成测试、可复用写作经验、具名规则、原件指纹及必要上游许可均保留。除已说明的权利/隐私内容转换外，运行规则核心不因公开发布而降级。

The entrypoint, integrated ratings and nine attributes, both standards, calculations, evidence relations, ability checks, three matchup outputs, novel pipeline, tools, synthetic tests, reusable writing methods, named rules, source fingerprints and required notices are included.

## 不随包分发 / Not bundled

- 完整小说、用户书包、参考册PDF与310页完整OCR、原作或参考册截图。
- 第三方模型权重、虚拟环境、外部项目源码全库、机器配置、私人访问数据库和验收日志。
- 权利边界未核清的完整交叉同人娱乐作品；写作参考提供独立表述的方法指导，不附故事全文或故事摘录。
- 非功能性的圈史、聊天、账号争议叙述。规则事实、必要短引、页号、哈希及数学桥保留。

Complete works and OCR, source screenshots, third-party weights, private environments/databases and clearance-unresolved crossover stories are excluded. Writing guidance contains independently worded methods, without story texts or story excerpts. Nonfunctional account/chat narratives are omitted while functional rules, locations and hashes remain.

## 可选手册语料 / Optional local handbook corpus

默认有限/高层规则从随包具名配置读取，不需要完整PDF或OCR。正文搜索和未校勘原页核验需要匹配版本、指纹和读取权限的本地资料。已校勘规则直接使用；仅未校勘内容回看原图。

Default rule evaluation uses bundled configurations without the full PDF/OCR. Full-text lookup and uncurated-page verification require matching local material that you have rights to use. Curated rules are used directly.

```powershell
python -X utf8 tools/import_handbook_corpus.py --source-dir "你的合法本地OCR目录"
```

导入器只读取明确本地输入，核对锁定语料SHA，不下载原册，也不把不匹配内容冒充默认版本。只有PDF时先依[量级册协议](../skills/battle-scaling/references/handbook.md)准备原件和提取结果。发布中的`LOCAL_*`路径是脱敏的历史定位标识，不是需要创建的目录。

The importer checks an explicitly supplied local corpus against its locked hash. It neither downloads a handbook nor accepts a mismatched edition. `LOCAL_*` strings are anonymized historical locators, not installation requirements.

## 许可 / Licensing

[MIT](../LICENSE)只覆盖原创部分。VSB改编资料、上游软件和可选外部数据保留各自条款；依赖许可、真实上游仓库、来源匹配和分发边界见[第三方说明](../THIRD_PARTY_NOTICES.md)、[拆书来源](../tools/combat-novel-refpack/UPSTREAM.md)与[当前包审计](CURRENT-RELEASE-AUDIT.md)。PyMuPDF等可选依赖的copyleft/商业要求不因“未打包”或鸣谢而自动消失。

The MIT license covers original material only. See the linked notices for third-party licenses and source provenance. Optional status and acknowledgement do not replace applicable copyleft or commercial-license requirements.
