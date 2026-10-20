# 模式、版本与量级传播

小说默认按[结尾时点倒序取证](novel-ending-state.md)，常态/最高/扒下限均固定该时点。旧表现仅在有延续理由时补证；历史虚弱和缺资源不能无条件约束结局。

角色记录包含作品/连续性、时期、状态、装备/招式。给同名角色的新版本建新ID；显式引用的成长、继承或跨版本关系另建边。最高模式的“最强反派”记录声明者、当时比较集合、时期及比较的是综合威胁还是具体属性。将综合定位扩张到AP/体防/速度时，各属性分别列假设。

normal优先repeated_feat与有重复支持的calculation；同一属性已有重复支持群时，不以单次credible_feat替换其最高。没有重复群才使用可信单次并标覆盖不足。冲突statement不压过表现。highest纳入outlier与statement；lowball优先anti_feat，否则报告最低已收集表现，不宣称是实际能力的数学下界。电影、漫画、动画、游戏机制、过场和小说译本各自建范围。

每次受击记录攻击者能力、这次出力、是否命中、作用面积、受击机制和后果。tanked边需actual_scale/effective_hit/body_only；damaged需effective_hit/non_hax/comparable_mechanism。defeated边需direct_power/matched_state。strongest/same_tier需corroborated/scope_compatible/attribute_coverage。failure反向边需maximal_attempt/opportunity/matched_state。

这些条件应由 [单次表现审查](feat-review.md) 的出处与因果链支持，不能为使传播器运行而随手填true。记录疲劳/伤势/资源/形态与战意/杀意/留手两个维度；当次有输出可作为该配置的表现，不能仅因未摧毁更多而设置上限。证明“尽力”还须排除任务限制、保护对象、缺乏机会、机制不适用和外部干扰；同样，疲劳或无杀意不自动证明出力很低。跨到所评时点或全盛配置，另给state_transfer，不按虚弱标签猜倍率。

conditions true表示已核实，false表示有明确相反观察，省略表示未定。normal不采用缺条件的边；highest与lowball可对未定项作显式激进假设。false不能直接假设成true；争议观察要保留双方证据并另建条件分支。

上界不能当作下界传递。低位攻击破防可支持特定部位/机制的上界分支；没有尝试或没造成范围破坏可进入扒下限争点，但写出应当尽力的前提。反向声明/同级边写reverse_lowball:true及来源。脚本只执行已提供的边，不独立证明该场战斗的语义。

有环可以存在于原作关系记录中，传播路径不重复经过同一属性节点；不靠环凭空放大。显式倍数需multiplier_evidence_ids；tier rank不能相乘。多条引用共用同一原作时标同一来源，不能提高独立支持数量。角色各最高属性可能互斥，对战前检查装备、蓄力、持续时间、消耗和状态可同时实现。

叠盒分为两类：战绩属性传递使用evidence.py；宇宙包含、操作闭包、叙事超越、原生φ等使用high_tier.py。不能把“在某结构生活”当作“能摧毁该结构”。与高层结构的关系包括到达、感知、支配、创造、破坏，逐项证明。

完整撤销：保留case输入和每条trace；删除某锚点/边、修改来源状态或假设后重新运行analyze。比较新旧derivations.json得到受影响结论。资源上限触发时报告未穷尽，不把截断前最高当全量最高。
