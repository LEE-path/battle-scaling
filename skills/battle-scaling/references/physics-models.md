# 物理表现：建模、参数、计算与可复核边界

仅在具体表现需要时加载。本文件与 `scripts/physics.py` 配套。脚本用 Python 3.11 标准库运行，不需要安装 SymPy、Pint 或数值软件。它验证数值、单位、模型条件并输出过程；模型选择、原作阅读、参数研究由调用它的 Agent 负责。工具执行成功不代表作品事实已核实。

## 使用顺序

1. **先描述现象。**谁在何种状态下，对什么对象做了什么；明确原作章节、页码、视频时间戳和前后文。把观察与解释分开。
2. **提出候选机制。**劈裂、弯曲折断、剪断、冲击、熔化、汽化、爆炸、重力解体不是同一个模型。魔法删除、传送、封印等通常不适用能量等价；列在特殊能力而非强行算焦耳。
3. **制作参数账本。**每个参数记录数值、单位、来源定位、测量方法、假设、合理区间及适用条件。原作未知时主动查官方、论文、材料手册；以有理由的候选情景继续计算，不把候选说成已鉴定事实。
4. **选择合理主估计。**优先与已知画面、材料状态和工况相符的方案；若没有证据判断哪种更可能，就报告并列情景而不伪造概率。保留对关键参数和替代模型的敏感性。
5. **运行并复算。**公式、代入、单位、中间值和全部假设入报告。报告有效位数取决于证据误差，不保留无意义的十几位小数。
6. **最后映射属性与量级。**外力 N、力矩 N·m、能量 J、功率 W、应力 Pa、冲量 N·s 分开。某动作做功不能无证据迁移到拳击输出、耐久或全身破坏范围。

三种论战口径与物理参数误差独立。最高模式可以采用更激进但有标注的解释；不可为提高量级同时选互不相容的参数。扒下限不等于测量区间的最小端点。

## 接口

```json
{
  "model": "kinetic",
  "inputs": {
    "mass": {"value": 2, "unit": "kg", "source": "测量记录 m-01", "assumption": "运动质量含全部携带物"},
    "speed": {"value": 3, "unit": "m/s", "source": "PTS 与位移记录 v-01"}
  },
  "assumptions": ["同一惯性参照系"],
  "intervals": {"mass": [1.8, 2.2], "speed": [2.5, 3.5]}
}
```

```text
python scripts/physics.py --input request.json --output calculation.json
```

API 为 `calculate(request: dict) -> dict`。支持 `--input -` 读 stdin。裸数字按下表的 SI 单位解释；带元数据的参数必须同时有 `value` 与正确的 `unit`，先显式换算 cm、km/h、MPa 等单位，脚本不会猜测。拒绝布尔值、数值字符串、NaN、无穷大、缺失项、未知参数和越界组合。输入元数据里的 `source` 只保存，不会自动验证其真实性。

输出固定有 `model`、`inputs`、`steps`、`result`、`assumptions`、`limitations`、`sources`。`steps` 包含公式、代入、中间值及单位。`intervals` 最多枚举 8 个标量参数、256 个端点组合，保存逐案结果；这是采样端点范围，只有另证模型单调性后才能称全区间边界。相关参数采用独立的完整情景请求，不盲目做笛卡尔积。不提供假精确的概率区间。

## 已实现模型

| model | 输入 SI | 公式／输出 | 适用条件 |
|---|---|---|---|
| `kinetic` | `mass` kg，`speed` m/s | (K=mv^2/2)，J | 非相对论实体平动；速度 ≥ 0.1c 要改用相对论模型 |
| `relativistic_kinetic` | 同上，0 ≤ v < c | (K=(\gamma-1)mc^2)，J | 稳定计算低速的 γ−1；不适用传送、空间膨胀、视运动或超光速 |
| `mass_energy` | `mass` kg，`conversion_fraction` 无量纲 0～1 | (E=fmc^2)，J | 必须证明实际质量转能量；湮灭质量要含双方 |
| `work` 常力 | `force` N，`displacement` m，`angle` rad，默认 0 | (W=Fd\cos\theta)，J | 力及相对位移夹角恒定；负功保留符号，不算破坏能量 |
| `work` 采样 | `samples:[{displacement:m,force:N},...]` | 梯形积分 (int F_\parallel dx)，J | 位移严格递增；力是沿位移方向的有符号分量 |
| `impulse` | `mass` kg，`delta_velocity` m/s 有符号，`contact_time` s | (I=m\Delta v,F_{avg}=I/\Delta t)，N | 非相对论、质量不变、单轴，需排除其他同时作用的冲量 |
| `torque` | `force` N，`lever_arm` m，`angle` rad，默认 π/2 | (	au=rF\sin\theta)，N·m | lever_arm 是支点到受力点的距离，夹角另给；不是能量 |
| `bending` | `length` m，`failure_stress` Pa，截面尺寸 | (sigma=M/S)，给出破坏载荷 N | 理想梁弯曲；材料强度与实际含水率、纹理、缺陷和工况相符 |
| `fracture_I` | `toughness` Pa√m，`crack_length` m，`geometry_factor` 1，`young_modulus` Pa，`poisson_ratio` 1，选填 `area` m² | (sigma_c=K_c/(Y\sqrt{\pi a}),G_c=K_c^2/E')，Pa、J/m² | I 型、线弹性、小范围屈服、显式各向同性近似；不是木材通用精确公式 |
| `thermal` | `mass` kg，`specific_heat` J/(kg K)，`delta_temperature` K，选填 `latent_heat` J/kg 默认 0、`phase_fraction` 1 默认 1 | (Q=mc\Delta T+mfL)，J | 依阶段分开累加；有变温热容时需积分扩展；未计热损、反应和额外冲击 |
| `gravitational_binding` | `mass` kg，`radius` m | (U=3GM^2/(5R))，J | 牛顿均匀球体，碎片被分散至无穷远；非真实分层天体的精确值 |
| `explosion_scaled_distance` | `reference_mass` kg TNT，`reference_distance` m，`target_distance` m | (Z=R/W^{1/3},W_2=W_1(R_2/R_1)^3)，kg TNT | 相同已标定冲击波端点、爆炸物、几何和环境；不得当火球半径万能核爆公式 |

其中 `bending.geometry` 必须为：

```json
{"section": "rectangular", "loading": "simply_supported_center"}
```

- `rectangular`：额外给 `width` 与 `height`，(S=bh^2/6)；height 是弯曲方向的截面高度。
- `circular`：额外给 `diameter`，(S=\pi d^3/32)；假设实心截面。
- `simply_supported_center`：跨中集中力，(M_{max}=FL/4)。
- `cantilever_end`：悬臂端部集中力，(M_{max}=FL)。
- `simply_supported_uniform`：均布载荷，(M_{max}=F_{total}L/8)，输出是**总载荷**而非 N/m。

只算弯曲不足以检查剪切、局部压溃、屈曲、滑动、既有裂纹或大变形。看见双手“掰木头”不能自动选择某一种支承方式。

`fracture_I.applicability` 必须显式说明：

```json
{
  "linear_elastic": true,
  "small_scale_yielding": true,
  "isotropic_approximation": true,
  "plane_condition": "plane_strain",
  "material": "wood — approximation only; actual grain and crack direction recorded separately"
}
```

平面应力取 (E'=E)，平面应变取 (E'=E/(1-\nu^2))。平面应变 (K_{Ic}) 与一般 (K_c) 的材料测定条件不可互换。木材正交各向异性，沿纹劈裂需要相应方向的模型及数据；本脚本条件近似不应包装成严格木材解。裂纹增长的 (G_c) 也不能在未知新裂面、裂纹路径与耗散时直接变成总做功。

`mass_energy.applicability`：

```json
{"physical_mass_conversion_established": true, "conversion_evidence": "原作位置及为何确为物理质能转换"}
```

`explosion_scaled_distance.applicability`：

```json
{
  "calibration_source": "原始实验／标定曲线及具体端点",
  "same_overpressure": true,
  "similar_charge_geometry": true,
  "same_environment": true
}
```

这些布尔值是待审计的研究结论，不是为了让脚本通过而随手填写的开关。量级规则与爆炸物的工况差异应在报告解释。

## 具体案例的正确复用

- `assets/cases/physics-earth-binding.json`：NASA 地球质量及平均半径 → 均匀球引力结合能，约 (2.24×10^{32}) J。它是地球类行星完全分散的**模型基准**。用于虚构角色时，另证目标的质量、半径和解体终态；不能宣称该文件已经证实任何角色有此输出。
- `assets/cases/physics-wood-bending-conditional.json`：完全标明为假设工况的木材梁弯曲估算。它检验支承方式及参数敏感性，未读取美队电影画面，也不代表该角色的实际成绩。
- 若只有峰值力，`work` 缺位移会拒绝；`bending`、`impulse`、`torque` 不附 TNT。已得到 J 时附带的 TNT 只作能量单位换算，不能自动推出冲击波、毁伤范围或角色量级。

## 破碎、粉碎、熔化、汽化与其他新机制

不要使用“任意岩石每立方米固定多少 J”的万能常数。对破碎，应查实际材料、粒径分布、初始裂纹、载荷速率、约束与试验能量口径；行业粉碎指标常含机器效率、循环破碎工况，不能未经论证迁移到角色一拳。若采用 (E=V e_v)，需有与该材料、终态和试验条件匹配的单位体积有效耗能标定，展示为何适用，并独立计算碎片动能，避免重复计入。

对量热与相变，先确定被作用质量而非整个画面体积；查对应相态、压力、温区的热容和潜热，必要时做 (int c(T)dT)、多阶段相变与反应能计算。可从 [NIST Chemistry WebBook](https://webbook.nist.gov/chemistry/) 找具体物质和原始实验引用。消失画面不自动证明汽化，汽化不自动证明完全质量转能。

对爆炸，区分冲击波、热辐射、碎片、地面耦合、反射、建筑坍塌和二次爆炸。选用 UFC 或原始实验的具体标定，在其有效域内插值并记录压力端点；只有看见火球或破坏半径时不能捏造当量。

对任何未覆盖机制，按以下流程自主补齐，不因工具清单有限就停止研究：

1. 检索论文、官方手册、教材或经验证的求解器原始文档，记录网址、版本、页码／式号、材料与工况。
2. 写出方程、假设、量纲、边界条件、所需参数和可观察终态；并列有竞争力的模型。
3. 用公开解析案例／实验标定、单位检验、极限情况和误用案例验证；不能用同一错误公式复制出期望值作为唯一测试。
4. 简单模型可写独立可审计 Python 脚本；复杂数值问题按需调用 SymPy、SciPy、有限元等，记录工具版本、网格／步长收敛与误差。保留精确运行命令和输入，不下载执行不可信脚本。
5. 输出使用同一 `model/inputs/steps/result/assumptions/limitations/sources` 结构，随报告附脚本。必要时返回“条件结论／当前不可识别”，不造公式凑档位。
6. 扩展共享 Skill 前补文档及独立测试；单次研究可把自定义模型保存在该次工作目录，无需修改已安装全局工具。

## 原始来源

- [NIST SI 单位](https://www.nist.gov/pml/special-publication-811/nist-guide-si-chapter-4-two-classes-si-units-and-si-prefixes)：力、应力、能量、功率和力矩的区分。
- [NIST 换算附录 B.8](https://www.nist.gov/pml/special-publication-811/nist-guide-si-appendix-b-conversion-factors/nist-guide-si-appendix-b8)：每吨 TNT 能量当量 (4.184×10^9) J，属于约定单位换算而非实际毁伤模型。
- [MIT Classical Mechanics](https://ocw.mit.edu/courses/8-01sc-classical-mechanics-fall-2016/) 与 [Special Relativity](https://ocw.mit.edu/courses/8-20-introduction-to-special-relativity-january-iap-2021/)：力学与相对论模型基础。
- [USDA Wood Handbook Ch. 5](https://research.fs.usda.gov/treesearch/62244) 及 [Ch. 9](https://research.fs.usda.gov/treesearch/62251)：材料差异与结构方程；取材料值时须回到表格和试验条件。
- [MIT／Roylance Fracture Mechanics](https://ocw.mit.edu/courses/3-91-mechanical-behavior-of-plastics-spring-2007/ca3759efc1b8fd66d57dce1147d4a1db_23_frac.pdf) 与 [INL MOOSE Fracture Integrals](https://mooseframework.inl.gov/releases/moose/2022-06-13/modules/tensor_mechanics/FractureIntegrals.html)：裂纹几何及能量释放率。扫描、OCR 的式子可能有误，交叉复核符号与平面应力／应变关系。
- [MIT 8.901 笔记，式 224](https://www.mit.edu/~iancross/8901_2019A/notes_midterm.pdf)：均匀球引力结合能；[NASA Earth Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html)：地球质量及体积平均半径。
- [UFC 3-340-02](https://www.wbdg.org/ffc/army-coe/ufc/ufc-3-340-02)：条件爆炸相似律；[BIPM JCGM 100](https://www.bipm.org/en/doi/10.59161/jcgm100-2008e)：测量不确定度。

来源核验日期：2026-10-18。相关材料参数不从本文件的示意数值自动继承。
