# VSB：对战默认、等化及结果边界

<!-- VSB-LICENSE-NOTICE -->
> 改编资料 / Adapted reference: © VS Battles Wiki contributors, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). 本项目作中文翻译、摘要与执行适配 / Project changes: translation, summarization and execution guidance. 原页／修订见本页引用，作者记录见原页历史 / Sources and revisions appear below; contributors are credited through the source-page histories. [许可与署名](../THIRD_PARTY_NOTICES.md#5-vsb-模式改编资料的许可例外--vsb-mode-adapted-reference-material)。


仅适用于 `standard: "vsb"`。用户明确指定的角色版本/状态、装备和场景优先；缺项再用下列 [Standard Battle Assumptions](https://vsbattles.fandom.com/wiki/Standard_Battle_Assumptions?oldid=9377396)（SBA），不能沿用汪吧案例的开局距离或外援配置。这里的“最强版本”是**已列的最强正史版本/键值**，不是跨连续性大拼盘，也不代表将全部高光、争议解释和互斥配置强行合并；按[统一综合评级](modes-scaling.md)处理。

| 项目 | 未另指定时的 VSB 默认 |
|---|---|
| 版本 | 已列正史中 Tier 最高者；同 Tier 时取最近版本。已指定“某作品末尾/某形态”的，不擅自换人。无 VSB 页面时可按该规则做独立研究，但标为自行评定，不能称 Wiki 已接受。 |
| 状态与战意 | 保留性格，但主动求胜；将对方视为会严重伤害自己的敌人，不因友善、无兴趣或认为打不过而自发离场。不等于无条件杀意、理性最优或自动熟练全部技能；心理/恐惧/劝服等可按能力实际奏效。 |
| 装备/准备 | 标准装备、无准备；按所用形态到场，开局不因突然转移而眩晕/惊讶。原页未明写“所有伤势自动治愈”或“资源无限”，不可据此新增。 |
| 知识 | 知起始方向与可识别外观，除此无对方情报；这点识别资料不能预先触发信息分析或感知负面能力。开战后再按能力实际侦察。 |
| 时地 | 纽约中央公园，可离开；日期/时间使双方处于有利时段，严重偏置则说明并讨论平衡替代。 |
| 起距 | 双方较高射程，最多 4 km。若较高射程方只有近战、无远程招式或延伸武器，则为其触及距离＋步幅较短一方的 3 步。缺射程/步幅数据时标待核，不把 4 km 无条件用到所有角色。 |
| 场外干涉 | 默认无；角色本人的既有能力中所列祝福、召唤、借高位存在的法术、角色型装备等可构成例外，须核能力归属及条件；无关队友不能临场帮忙。 |
| 胜利 | 放逐离场至少 1 周；昏迷至少 1 小时；进入无法伤及对手的失能状态超过 1 天。死亡可立即判胜，但假如继续战斗，死后状况最终仍须满足前述至少一项；会立即复活反击的“杀一次”不自动赢。先达到有效胜利条件者胜。 |

## 胜利条件包的实际字段

`condition` 为 `bfr | knockout | incapacitation | death`；`status` 为 `supported | assumed | unknown | blocked`。已支持判断用可读 `evidence_ids` 绑定实际持续时间／回归或恢复限制；`assumed` 须给非空 `assumptions` 字符串列表，并只得到条件判断。`duration_seconds` 是有依据的实际或前瞻持续时长，不是步骤数。默认 SBA 自动边界：**KO ≥ 3600、BFR ≥ 604800、incapacitation > 86400 秒**。

宏观 CASE 片段（字段演示；`s-duration` 必须替换成本案已读来源）：

```json
{
  "matchup": {
    "teams": ["a", "b"],
    "win_paths": [{
      "id": "a-knocks-out-b", "winner": "a", "affected_target": "b",
      "evidence_ids": ["s-duration"],
      "requirements": [{"status": "supported", "evidence_ids": ["s-duration"]}],
      "vsb_victory": {
        "condition": "knockout", "status": "supported",
        "duration_seconds": 3600, "evidence_ids": ["s-duration"]
      }
    }],
    "mode_assessments": {
      "integrated": {
        "status": "reasoned_estimate", "winner": "a",
        "reasoning": "宿主依据双方胜路与恢复实绩给出的判断。",
        "evidence_ids": ["s-duration"],
        "vsb_victory": {
          "condition": "knockout", "status": "supported",
          "duration_seconds": 3600, "evidence_ids": ["s-duration"]
        }
      }
    }
  }
}
```

每条 `win_paths[]` 与当前 `mode_assessments[mode]` 各自绑定其胜利包，不能只给总评补一个条件就让所有胜路通过。有关 `sources` 的真实来源、requirements 的具体机制、特能门槛和反制仍须完整填写；上述片段不证明命中、昏迷或优势。

过程 CASE 合并片段；角色、行动与来源依 [过程协议](combat-process.md)另备：

```json
{
  "matchup": {
    "presentation": "process",
    "mode_processes": {
      "integrated": {
        "victory": {
          "defeated_states": ["incapacitated"],
          "vsb_checks": {
            "b": {
              "condition": "knockout", "status": "supported",
              "duration_seconds": 3600, "evidence_ids": ["s-duration"]
            }
          }
        }
      }
    }
  }
}
```

`vsb_checks` 按**败方角色 ID**索引，不是胜者或队名；过程已经记录的失败状态也须匹配：KO→`incapacitated`，incapacitation→`incapacitated/sealed`，BFR→`withdrawn/sealed`，death→`dead`。一个 `sealed` 标签不自动是一天失能或一周放逐。

死亡包另需独立的 `post_death`，例如：

```json
{
  "condition": "death", "status": "supported", "evidence_ids": ["s-death"],
  "post_death": {
    "condition": "incapacitation", "status": "supported",
    "duration_seconds": 86401, "evidence_ids": ["s-no-return"]
  }
}
```

`post_death` 只能证明最终满足 BFR／KO／失能之一，不能再嵌一个 death。被杀后立即复活、死后仍能反击、远处真体续战、已经发出的延迟攻击等必须一起审。两者同时失能仍须核各自**首次满足有效条件的先后、恢复及延迟效果**；终局都不 active 不代表平局或互败。缺时序证据保留未决，`mutual_outcome` 的一句文字也不能免除这项审查。

**自动门槛只审核默认 SBA。** 用户另定擂台、HP 归零、击倒即胜、缩短失能时长等可以保留为赛制，但须由宿主另行审查并明确为自订条件，不能靠填一个自订字段宣称引擎已实现该胜利规则。这里的通过仍只检查包内引用和条件，不验证原作语义或统计胜率。标准切换见 [VSB 模式](vsb-mode.md)，量级／材料和政策计算见 [VSB 属性与计算](vsb-attributes.md)。

当前过程引擎对**双方同时失能**一律保守返回未决，尚无自动时序裁决输入；即便双方时长包齐全，也不能靠填写它们自动得到互败。宿主若能另行证明先满足条件者，须把独立时序分析与引擎未决结果一起披露。

## 等化的界限

**速度不默认等化。** 显式指定速度等化时按 [Versus Thread Rules](https://vsbattles.fandom.com/wiki/Versus_Thread_Rules?oldid=9123844)：把快方战斗速度降到慢方，快方其他速度按同倍率缩放；原有增速保留相同比例，基于速度的技能仍保留。不是直接把所有人的移动/反应/弹速强制变成一个数字。引入其本来不承受的速度劣势、因等化后的增速碾压、将无限制速度角色输给被动等情形，还涉及 Wiki 结果收录限制。

SBA 的 **verse equalization** 合理等同相近且机制兼容的超自然能量/方面；不赠送或删除固有技能、抗性，不取消有效且无矛盾的能量差或生理门槛。跨作品特殊能力仍按 [VSB 特能审查](vsb-hax.md)分项核对象/发动/范围/机制/抗性。

另一个 **[Reality Equalization](https://vsbattles.fandom.com/wiki/Reality_Equalization?oldid=9019162)** 指有重要虚拟世界视角的合格角色按其世界内相对表现与普通现实基线相交互。它不是“所有高层叙事差自动抹平”，也不因是 AI/电子程序就自动适用；只是平行宇宙的“数码世界”本就不需该等化。需逐作品确认该 key 适用条件。

## 叠加、异常与过程

按 [Powerscaling](https://vsbattles.fandom.com/wiki/Powerscaling?oldid=9566433) 只传递实际涉及的属性。体防绕过杀伤不反叠普通 AP，受伤/留手目标不反叠全盛输出，击败身体不继承其未使用的强念力。档位广，不把每次胜利自动当晋档或固定倍率；设定数值也不默认线性。

按 [Outliers](https://vsbattles.fandom.com/wiki/Outliers?oldid=9660702) 审查矛盾：跳幅、是否孤例、是否有变身/弱点/限制解释、是否破坏既有叠链、是否冲突叙事。孤例本身不是自动废弃理由；先尝试和原作调和。高光、通常和低谷的表现参考不能把已排除的 outlier 偷渡成“VSB 默认认可”；争议解释保留条件和采纳理由，统一参与综合选档，不另建最高／最低角色档位。

沿用本 Skill 的展示选择：普通 VS 宏观；用户要求详细过程时，内部先审优势，展示优势方的一条胜局，再解释总体胜率及对方翻盘路线。该单局是证据约束的推演，不能冒充跨作原典、Wiki 已投票结果或统计样本。过程步骤不是现实持续时间：封印一回合不证明超过 1 天，BFR 一瞬间不证明 1 周回不来；须另给持续/回归能力依据。若关键机制未决，不凭编好的胜局补造胜负或百分比。

Wiki 的投票数、宽限期、页面收录与 CRT 审批是社区治理规则，不是物理定律或胜率模型；本地 Agent 不声称得到社区批准。Tier 0 或高层不可比对战不凭档名/层数总数硬排，按已核适用规则保留未决。

核读日 2026-10-21；以上链接锁定本次 revision，另见包内 VSB 来源目录。快照覆盖 SBA、Versus Thread Rules、Powerscaling、Outliers 和 Reality Equalization 全文；其他作品专属标准仍按需查原站。
