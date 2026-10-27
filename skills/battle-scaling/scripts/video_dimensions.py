"""Optional video-comparison research directions. Never decides winners or invents evidence."""
from __future__ import annotations

# attribute is an index/search tag; the nine core rating dimensions remain unchanged.
METHODS = {
    'attack': ('output', '徒手、武器、能量或机制的哪种输出；同一配置能实际发挥到哪里？',
               '沿用独立评级的原作锚和叠链，分清身体、装备与特殊作用。'),
    'defense': ('durability', '比较肉身、装甲、护盾还是包含规避／转移的综合防御？',
                '追受击状态、命中部位、剩余功能与对应抗性；恢复不能自动当作未破防。'),
    'destruction': ('destruction', '摧毁什么、达到何终态、覆盖多远、持续多久、贡献归谁？',
                    '区分集中输出与环境破坏，沿用已有物理／机制模型，不把场景后果无证分给本人。'),
    'physical_strength': ('physical_strength', '本场比较举托、推拉、角力、抓握控制还是打击？',
                          '核质量、支撑、重力、摩擦、加速、杠杆与辅助；共同动作或成立关系优先，N/J/W分别使用。'),
    'speed': ('speed', '本页的速度是哪种运动，怎样与感知、反应、动作和传播区别？',
              '对齐距离、动作、准备与发动；不把预知／传送自动换作身体速度。'),
    'reaction': ('speed', '从察觉什么到作出何种有效回应，是否提前知情？',
                 '核感知、决策与动作环节及反例；同类威胁或有据共同参照比较。'),
    'attack_speed': ('speed', '比较出招动作、连击频率还是攻击传播？',
                     '剥离蓄力、冷却、距离、预先瞄准和对手状态，不以剪辑时长当世界内时间。'),
    'agility': ('agility', '如何变向、急停、调整重心、避障及衔接落地？',
                '查具体动作与空间约束，区分反应和直线速度；有比例／时间才计算相应加速度。'),
    'intelligence': ('intelligence', '在哪个领域、信息与资源约束下，独立解决了怎样的任务？',
                     '对齐任务复杂度、解法与结果；分清知识授予、AI代算、预知和本人推理，处理重要反例。'),
    'battle_iq': ('battle_iq', '知道什么→如何试探／决策→对手怎样反制→如何修正？',
                  '回到交手因果，剥离开局情报、属性碾压和外援；查失败后的调整与反制质量。'),
    'experience': ('experience', '哪些训练、敌手、机制和场地经验能迁移到本场？',
                   '核有效实战、独立运用、广度与近期更新；岁数／击杀／复制记忆不直接等于全部熟练度。'),
    'burst': ('burst', '爆发指快速建立力量、短时输出、增幅形态还是一招全力？',
              '起始状态→准备／增幅→发挥多久→作用→复用与代价；有据倍率照用，W与J不混填。'),
    'stamina': ('stamina', '在何种强度、补给和休息条件下，能保持何种行动多久？',
                '对齐连续性、资源消耗、功能衰减和恢复；无限能源不表示结构、技能与承伤都无限。'),
    'lethality': ('lethality', '本场如何命中、突破相关防御并造成损害或失能？',
                  '具体目标、部位、机制、射程和代价决定效能；伤害、范围、击杀数量不是同一个排名。'),
    'hax': ('hax', '能力的影响、发动、作用对象、抗性和限制怎样影响本场？',
            '采用所选汪吧／VSB规则与实际能力实绩；不能数技能数量判本场更有效。'),
    'skill_damage': ('skill_damage', '比较哪一招／技能组，以何机制对哪个适用对象生效？',
                     '核发动、命中、穿防、作用、持续与代价；控制／删除等非物理作用有效，但不自动叠成同档拳力。'),
    'combat_skill': ('combat_skill', '距离、时机、重心、骗招、防守、擒控或兵器中，技术实际贡献是什么？',
                     '回看成功和失败，剥离速度、力量、构造、人数与地形；不虚构同属性对局作证。'),
    'physiology': ('physiology', '体质具体指结构、耐伤、恢复、环境适应还是生存需求？',
                    '优先改成具体项目；若保留综合称呼，说明组成与本场权重，不造万能身体总分。'),
    'psychology': ('psychology', '受压、痛苦、恐惧、受挫或信息突变后，判断与执行如何变化？',
                   '核触发、维持、失误、恢复及反例；表情冷静不证明稳定，愤怒不自动等于失去战术。'),
    'courage': ('courage', '明确知道风险后，为何目标承担何种代价，是否真正存在恐惧／痛感？',
                '不以无知、无痛、失控或不撤退代替勇气；也不把战术撤退自动判为胆怯。'),
    'intimidation': ('intimidation', '比较观感／声望、真实威胁下的行为，还是超常恐惧作用？',
                     '核对象为何退缩与相反表现；异常恐惧走特能与抗性，自然气质不自动影响本场强敌。'),
    'weapons': ('weapons', '本场实际持有哪种形态，效能、操控和对方反制如何？',
                 '分性能、持有者使用水平与本场威胁；核距离、消耗、冷却、可靠性及损坏，不按材料名和名气排名。'),
    'weakness': ('weakness', '弱点能否被本场对手得知、制造条件、接近、执行并转成胜利？',
                  '存在弱点不等于可利用；原作反例与有效作用条件必须保留。'),
    'age': ('age', '所选版本的实际年龄或可确认范围是什么？',
             '作为事实呈现，不自动变成经验或胜率优势。'),
}
GROUPS = {
    'attack': ['攻击', '攻击力', 'attack', 'ap'], 'defense': ['防御', 'defense'],
    'destruction': ['破坏力', '破坏', 'destruction'], 'physical_strength': ['力量', '举力', 'strength'],
    'speed': ['速度', 'speed'], 'reaction': ['反应力', '反应', 'reaction'],
    'attack_speed': ['攻击速度', 'attack speed'], 'agility': ['敏捷', 'agility'],
    'intelligence': ['智商', '智力', 'intelligence'], 'battle_iq': ['战斗智商', 'battle iq'],
    'experience': ['战斗经验', '经验', 'experience'], 'burst': ['爆发力', '爆发', 'burst'],
    'stamina': ['耐力/续航', '耐力', '续航', 'stamina'], 'lethality': ['杀伤力', 'lethality'],
    'hax': ['特殊能力', '能力', 'hax'], 'skill_damage': ['技能伤害', 'skill damage'],
    'combat_skill': ['格斗体术', '近战格斗', '技巧', 'combat skill'], 'physiology': ['体质', 'physiology'],
    'psychology': ['心理素质', 'psychology'], 'courage': ['勇气', 'courage'],
    'intimidation': ['威慑力', 'intimidation'], 'weapons': ['武器', 'weapons'],
    'weakness': ['明显弱点', '弱点', 'weakness'], 'age': ['年龄', 'age'],
}
ALIASES = {label.lower(): key for key, labels in GROUPS.items() for label in labels}
COMPOSITES = {'攻击/防御': ['attack', 'defense'], '敏捷/反应力': ['agility', 'reaction']}
SUMMARIES = {'全面/量级', '优势', '全面', '量级'}
VERDICTS = {'胜者', '完胜', '胜', 'winner'}
THEMES = {'野心', '真实', '正义', '人气', '月牙天冲'}


def build_plan(labels, target=None, definitions=None):
    if not isinstance(labels, list) or any(not isinstance(x, str) or not x.strip() for x in labels):
        raise ValueError('video_dimensions must be a list of nonempty display labels')
    target, definitions = target or {}, definitions or {}
    if not isinstance(definitions, dict):
        raise ValueError('dimension_definitions must be a label-to-method object')
    rows, tasks, used = [], [], set()
    for original in labels:
        label = original.strip()
        override = definitions.get(label)
        if override is not None and override not in METHODS:
            raise ValueError(f'Unknown method definition for {label}: {override}')
        ids = [override] if override else COMPOSITES.get(label, [ALIASES[label.lower()]] if label.lower() in ALIASES else [])
        kind = 'comparison' if ids else 'summary' if label in SUMMARIES else 'verdict' if label in VERDICTS else 'theme' if label in THEMES else 'needs_definition'
        if label == '技能' and not override:
            kind = 'needs_definition'
        if len(ids) > 1:
            kind = 'composite'
        if ids == ['age']:
            kind = 'fact'
        rows.append({'label': label, 'kind': kind, 'methods': ids,
                     'presentation_note': '复合项分别比较；有相反优势时拆页或明确各有所长' if len(ids) > 1 else (
                         '先定义：技巧、特能或组合；不要重复给分' if label == '技能' and not override else (
                             '不是独立战斗票；总胜负及难度仍按完整胜路' if kind in ('theme', 'fact', 'summary', 'verdict') else '按任务与证据作双方比较'))})
        for key in ids:
            if key in used:
                continue
            used.add(key)
            attribute, question, method = METHODS[key]
            tasks.append({'task_id': f'video:{key}:comparison', 'attribute': attribute,
                'source_family': 'original', 'polarity': 'comparison', 'status': 'pending',
                'scope': dict(target), 'purpose': question, 'method': method,
                'query_hint': f"{target.get('name', target.get('entity_id', '角色'))} {question}",
                'reuse_existing_first': True, 'reference': 'references/video-dimensions.md',
                'completion': '宿主复用／读取来源，对齐条件并解释双方排序与反例；任务生成不等于已研究或已判胜'})
    return {'display_dimensions': rows, 'tasks': tasks,
            'decision_route': 'independent_ratings_or_rigorous_pk → targeted_pairwise_comparison → ordinary_pk_verdict_and_difficulty → editing',
            'never_votes': True, 'research_executed': False,
            'difficulty': ['no', 'low', 'mid', 'high', 'extreme']}
