# 已审定角色档案与共用交接

本页在真实单人研究、候选取舍和宿主实读验收完成后使用。`independent_ratings`中的当前行是评级权威；报告展示、普通PK角色视图、process演员和故事人物卡由它派生。`fighters[].ratings`等旧摘要不再具有独立定档权，不能将旧摘要覆盖新结论。同配置、同属性的已选结论相互矛盾时返回研究复核；高光、反例、其他状态及明确的候选并不要求与主档相等。

## 纯定性研究：一个真实dossier即可

不需要数值模型的角色，可以保存一份实际完成的`dossier.json`。它承载真实报告及既有评级数据，不要求再复制十条主张、空CASE或八份重复文件：

```json
{
  "schema_version": 1,
  "character": {"id":"角色ID","name":"角色名","version":"已定版本","state":"已定状态","equipment":[]},
  "ruleset_profile": "从本次plan取得的规则ID",
  "rules_fingerprint": "从本次plan取得的规则指纹",
  "rating": {"character_id":"既有独立评级行，格式见character-rating-workflow.md"},
  "sources": [],
  "report": "宿主实际完成并可独立交付的报告正文",
  "acceptance": {"status":"accepted","reviewer":"实际验收人","reviewed_revision":"与评级行一致的修订","content_sha256":"受审内容的digest"}
}
```

上面只示意容器；`rating/sources/report`须放完整真实研究成果，不能照抄占位。`acceptance.content_sha256`用`rating_pipeline.digest({k:v for k,v in dossier.items() if k!='acceptance'})`计算；接受人及修订须与`rating.host_review`一致。先研究和实读验收，再写接受；指纹证明文件绑定，不证明原作真实或论证正确。

有物理、高层或其他需复算的模型时，增加`calculation_case:{"path":"既有CASE.json","sha256":"该文件哈希"}`，直接引用已有产物；相对路径按dossier目录解释。工具读取并重算该CASE，绑定所引字节。可选内嵌`case`仍兼容，但不能与`calculation_case`同时提供。没有计算就不虚称已重放计算，也不制造空计算以求通过。

小说规范文本来源沿用`path/text_sha256/start/end/quote`，按零起点Unicode左闭右开坐标核引句；`source_sha256`用于原始文件，有`source_path`时才对该原件比对，不能误比到规范全文。多条引句引用同一文件时，每次交接只读取哈希一次，下一次公开调用重新检查当前字节和撤回状态。

## 导入同一产物，再按呈现分流

```json
{
  "operation":"assemble",
  "rating_request":{"purpose":"rating","standard":"wangba","mode":"integrated","characters":[]},
  "artifacts":[{"character_id":"角色ID","dossier_file":"该角色/dossier.json"}]
}
```

`characters`填所评对象及完整配置。普通PK在该请求中保留既有`matchup`等字段；返回`rating_request`包含真实导入的评级、来源与`rating_execution`。故事改用`writing_request`，仍导入相同角色档案；`operation:assemble-and-prepare`可一次完成导入和写作准备。直接`process`也须携带相同`rating_execution`及角色配置，不能只凭评级声明启动战斗。

运行：`python scripts/battle.py rating-pipeline --input request.json --output assembled.json`。把返回的请求交相应`analyze/process/writing`入口，不将整个工具外壳当作CASE。命令生成研究计划不等于实际研究；公开调用会核当前档案，包装调用在同次私有上下文内复用未变结果，不信任用户填写的ready标记。

旧的`artifacts:[{character_id,artifact_dir}]`八文件档案继续读取、验证和复用；无需重写历史接受来迁移格式。新研究优先使用满足实际需要的轻量容器。正式PK与故事都验证真实档案；明确隔离的合成回归夹具仅用于开发测试，不能给真实角色免研究。

## 作者局部改编

在故事人物上显式给`author_rating_overrides`，只列作者确实改动的主档或九维节点。每个节点使用既有assessment结构、`basis_type:author_settings`，引用实际`origin:author_settings/access:provided`的作者设定来源及具体位置。它只替换该场派生视图的对应字段，原作独立档和接受记录保留；其余属性继续继承已验收档。作者指定胜者不是属性覆盖，也不自动赋予抗性或新技能。

## 完成的含义

程序能确认真实档案被读取、所用规则与配置匹配、引用和必要计算一致；不能从这些结果宣称原作已穷尽或逻辑已被机器认证。宿主仍实读决定性原文，沿独立锚、真实关系、属性和候选取舍复演结论。只有真实研究充分后才进行战术与写作。
