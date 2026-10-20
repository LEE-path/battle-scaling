# 配套案例及复算

以下路径相对Skill根目录。输出写本次工作目录。案例是2026-10-18研究快照，资料有读取状态和定位；新任务先按需复核原作。包内保留推导与网址，不把原作整书、电影或原始验证缓存全部打包。

| 案例 | 文件 | 实际学习点／运行入口 |
|---|---|---|
| 死星毁奥德朗、卢克命中反应堆弱点 | `assets/cases/research-deathstar.json` | `battle.py analyze --mode all`；官方作品说明、条件均匀球结合能与弱点连锁反应隔离 |
| MCU美队双手分开木段 | `assets/cases/research-captain-wood.json` | `battle.py analyze --mode all`；[完整读图与模型说明](captain-wood-case.md)、随包接触表、材料表核对、线弹性条件近似，N不转TNT |
| 银背西部低地大猩猩vs十只斑鬣狗 | `assets/cases/research-animals.json` | `battle.py analyze --mode all`；数量、行为、获胜路径、最可能判断及未校准部分 |
| Franx短暂白光状态与alef-one到达 | `assets/cases/research-franx.json` | `battle.py analyze --mode all`；三模式、高层请求、受伤反例与版本／形态分离 |
| 旧神盒第四阶段 | `assets/cases/high-godbox-stage4.json` | `battle.py high`；Φ构造、闭包、整体重设及具名AOS锚点，原章校勘缺口明确 |
| White Light结构映射 | `assets/cases/high-whitelight.json` | `battle.py high`；可数ε₀与不可数基数分开；范围不自动传攻击 |
| 单篇SCP-3812 | `assets/cases/high-scp3812.json` | `battle.py high`；原生叙事超越与特殊作用范围；不虚构具体基数 |
| 地球均匀球模型基准 | `assets/cases/physics-earth-binding.json` | `battle.py physics`；NASA参数与公式、TNT仅作能量单位 |
| 假设木梁工况 | `assets/cases/physics-wood-bending-conditional.json` | `battle.py physics`；假设支承、截面和材料敏感性，明确非美队实测 |

例如：

```powershell
python scripts/battle.py analyze --input assets/cases/research-deathstar.json --mode all --output D:/case/deathstar
python scripts/battle.py high --input assets/cases/high-godbox-stage4.json --output D:/case/godbox.json
```

数值模型和case包的JSON接口不同：`physics/high`接受对应模型请求；`analyze`接受含characters/sources/anchors/edges的完整证据包。合成测试位于`tests/`，不能当作真实角色战绩。

独立测试已经发现并修复高层主模式传递、对战逐模式判断、中文验证码误报、现装PDF库回退、来源退出码及Windows Unicode输出问题。机器验证只确认已写明的数值、类型、引用与传播条件；案例中的语义判断、原作覆盖和物理适用性仍须阅读对应证据。
