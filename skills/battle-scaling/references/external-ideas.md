# 外部思想的吸收、替代与边界

本轮升级为1.2.0，借鉴目的与流程后独立实现。九项外部项目的模型、权重、API调用均不进入本Skill运行链；外部归档不成为默认依赖。无许可证项目不复制源码，论文不冒称已安装作者实现。资料引用不表示原作事实已核验。

| 材料 | 吸收的目的 | 本Skill落点 | 舍弃的逻辑 |
|---|---|---|---|
| [AutoSkill fictional_battle_simulation](https://github.com/ECNU-ICALK/AutoSkill/blob/main/SkillBank/ConvSkill/english_gpt3.5_8_GLM4.7/fictional_battle_simulation/SKILL.md) | 按需把能力卡转为观众可读战况 | process轨迹之后的简短叙述 | 故事充当新表现 |
| [OmniBattle AI](https://github.com/Zerhal/omnibattle-ai) | 分阶段检索、配置与能力关系 | research索引、交互表、推导缺口任务 | Wiki档位捷径、能力名称固定相克、字符串速度误判 |
| [VS Simulator／vskill](https://github.com/GentleClash/vskill) | 意图、裁决、状态、叙事分开 | combat_trace状态结算及时间边界 | 双倒默认判第二方赢、新效果当步过期 |
| [Fictional Character Ranking](https://github.com/BenCantCode/fictional-ranking) | 每次对战与资料版本可追查 | run-ledger输入/条件指纹和宿主元数据 | 单个排名分数代表物理档位或克制 |
| [Animal Battle Stats](https://github.com/RamiNoodle733/animal-battle-stats) | 物种/性别/年龄、实测/估计、未知值与论文发现 | 九维计划、字段来源、Europe PMC发现入口 | 未校准评分转精确胜率、未知填零 |
| [Cited Feats](https://citedfeats.com/about/) | 作品/连续性/表现与章节引用索引 | 显式按需导入社区线索，保留定位、原记录与署名 | 社区排名映射汪吧、同名自动合并 |
| [QuantiPhy](https://github.com/Paulineli/QuantiPhy) | 已知先验下测尺寸/运动，检验误差 | 现有PTS测量＋参数账本、同条件回归 | 帧号/平均FPS替代PTS、无单位答案、旧预测冒充本机推理 |
| [MangaLMM／MangaVQA](https://github.com/manga109/MangaLMM) | 漫画文本、框和语境接口 | 宿主读图记录、上下文与框校核 | 运行外部模型、OCR结果直接当正确剧情 |
| [ManGo](https://arxiv.org/abs/2608.29865) | 按问题主动选格、存线索、再决定继续/停止 | 媒体协议的主动取证循环 | 冒称自动分格或复现论文训练收益 |

外部项目通过本页公开来源链接重新获取；不要求本机历史轻量档案存在，也不把早期下载、测试数量或complete标记当作当前安装事实。仅借鉴目的与流程，运行时不依赖它们的源码、环境、模型、权重或社区全库；许可与依赖披露以仓库的第三方说明为准。

## 按需工作链

新角色：research plan → 宿主多渠道搜证/视觉 → research index/search → 物理或叠链候选 → derivation审查 → 将缺口回送research → 原有汪吧规则定档 → 宏观判胜。

只有明确请求具体战况时，在宏观机制结论后再构建对应模式的动作分支 → combat_trace结算 → 检查恢复/反例/截断 → 短叙述。工具不会从角色名自行生成原作事实，也不会以轨迹条数计算概率。

双模式可执行格式见 `assets/cases/pk-dual-presentation-synthetic.json`；它是合成规则测试，不含真实角色评级。可以对同一个文件运行：

```text
python scripts/battle.py analyze --input assets/cases/pk-dual-presentation-synthetic.json --mode integrated --output RUN_DIR/overview
python scripts/battle.py analyze --input assets/cases/pk-dual-presentation-synthetic.json --mode integrated --pk process --output RUN_DIR/process
```

测试能证明程序对指定输入的结算与来源约束，不能证明任意作品都已搜尽、任意物理模型都适用，或主观胜率已被实战校准。实际搜证覆盖范围必须随每次报告披露。
