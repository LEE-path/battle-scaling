# 真实语义边界对抗题

这六题来自已有实际研究中的原作/官方资料争点：武器对波、灾难贡献、星灵与星座、叙事与肉身、局部数学模型、最强声明。短摘录、来源性质、固定范围及定位在 `prompts.json`；合理解释集合和关键边界在独立的 `answers.json`。题目围绕推理链，不预定当前某个档位、胜者或历史报告必须正确。待评的两端推断是编写者制作的对抗文本，不冒称原研究的逐字引用。

本题集不是模型、自动原作阅读器或语义认证程序。一次合理作答须解释来源命题、实际关系、可传属性、未立桥梁和可接受分支；不能仅提交几个布尔字段。对于不在参考解释中的新证据，宿主可采纳并说明来源和改变了哪一步。

## 盲答与复核

在 Skill 根目录运行，Python 3.11+、标准库即可；不依赖主评级入口，也不要求每次评级执行：

```powershell
python scripts/semantic_benchmark.py list
python scripts/semantic_benchmark.py packet --ids SB-01,SB-03 --output packet.json
```

只把 `packet.json` 交给独立 Agent 或受测宿主；不要同时交 `answers.json`、旧评级结论或本题集的参考复核。`packet` 命令只读题面资源，完全不打开答案。可选任意题或删去 `--ids` 一次运行六题。题面已携带所需短摘录及自己概述，能离线答边界；若结论依赖题外细节，明确缺口并按原始定位补查，不能把提及的来源当作已阅读。

受测者按 packet 中 `response_format` 产出 JSON。复制准确的 `packet_sha256`，对每题填写 `analysis`，以及字符串列表 `supported_conclusions`、`rejected_inferences`、`missing_bridges`、`conditional_alternatives`。空列表允许，但不能省略分析。自由推理是实际考察对象，列表仅便于复核。

```powershell
python scripts/semantic_benchmark.py record --packet packet.json --response response.json --respondent "independent-agent-or-host" --output response-record.json
python scripts/semantic_benchmark.py rubric --output reviewer-rubric.json
```

`record` 只验证选题和记录绑定，保存原回答并标记 `recorded_unreviewed`；不读取答案，不自动打分。随后由宿主或另一个独立复核者对照实际作答、原始来源及参考解释，准备 `judgments.json`：

```json
{
  "reviewer": "named-host-or-reviewer",
  "response_sha256": "复制response-record中的摘要",
  "judgments": [
    {
      "case_id": "SB-01",
      "assessment": "acceptable",
      "rationale": "引用受测者实际论证，说明关键链是否完整；不要求和参考措辞相同。",
      "evidence_comparison": "指出哪些源段支持、限制或改变了该推理；新来源应给定位。"
    }
  ]
}
```

每个选中题目各写一条。`assessment` 可以是 `acceptable`、`needs_revision`、`unresolved`；未知不是被迫通过，也不是被迫否定全部能力。不要把参考答案本身当原作证据。

```powershell
python scripts/semantic_benchmark.py review --record response-record.json --judgments judgments.json --output host-review.json
python scripts/semantic_benchmark.py audit
python -m unittest discover -s tests -p test_semantic_benchmark.py
```

最后的记录保存具名复核者给出的判断和理由，明确 `semantic_certification: false`。`audit` 和单测只检查可判定不变量：选题/版本一致、题面不含答案字段、摘要绑定、完整记录及程序不自动按档位/关键词评分。它们不声称机器验证了原作真实性、跨章理解、合理解释或结论。实际行为测试应保存原始盲答及实读复核；没有完成这一过程，不能称六题语义已通过。不要把录入一份自写合格回答当独立行为测试。

## 来源与版本

固定的是随题交付的短摘录、题面和其内容摘要。公开作品会更新；这不表示本题锁定了每一整页的当前修订。`research_snapshot_sha256` 是实际研究全文快照的指纹，作为历史来源线索，不谎称为随包短摘录哈希，也不要求用户拥有旧工作目录。资料来自官方文章、官方剧本、官方原作页面/数据，以及明确标注的第三方电影台词转写。转写只提供台词证据，不能替代原片视觉核查。题面已区分本轮重新打开的来源与复核既有快照。

SCP-3143 作者 The Great Hippo，SCP-3812 作者 djkaktus，原作链接见题面。两题摘录及改述按原作 [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) 署名和相同方式共享；本目录的题面与参考解释统一按 CC BY-SA 3.0 提供。Disney/Marvel、Riot Games 的短摘录保留权利人权利，仅作必要的研究评议引用，不含全文、完整故事、图片或视频。脚本的许可遵循项目代码许可。
