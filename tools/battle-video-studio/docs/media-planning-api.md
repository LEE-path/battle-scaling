# 候选片段编排接口

`prepareJob` / `POST /api/prepare` 现在在保存前生成逐段可播放的 `scenes[].media`。宿主先实际看素材、划出有效区间、标用途和质量，编排器消费这些判断；程序没有视频语义识别、水印识别或自动评级能力。

自动化可用 `node scripts/prepare-job.mjs 任务.json --json`，返回一个短JSON；失败时原样保留MEDIA_GAPS和gaps。`--no-activate`保留已有预览。Skill桥默认走此CLI，以免已运行工作台缓存旧模块；无需重启或关闭用户服务。JSON文件支持UTF-8 BOM。

## 候选的最小用法

```json
{
  "path": "D:/media/character-film.mp4",
  "role": "finish",
  "trimIn": 71.2,
  "trimOut": 77.6,
  "qualityTier": "S",
  "excitement": "exciting",
  "continuous": true,
  "cropUsable": true,
  "allowSlowdown": true,
  "qualityReason": "实际连续查看本区间；人物始终为主体，裁切可去除角标。"
}
```

- `role` 为 `intro / plate / highlight / finish / any`；`any` 表示宿主确认可承担任意用途。没有对应用途时返回补选材缺口，不改用标成其他用途的镜头。
- `qualityTier` 沿用 S/A/B/C/unrated/exclude。`excitement: exciting|ordinary`、`continuous`、`cropUsable` 由实际选片者判断；`cropUsable:false` 不使用。没有新增数值评分。
- `motion: native|animated|still` 表示原生动态、动图/已制作动效、静态图片。默认视频为 native、图片为 still；宿主应给动图/图片动效视频明确标 animated。静态图在渲染中继续使用现有推拉动效。
- 未提供 `excitement` 的老候选沿用宿主 S/A 档作为精彩候选、其他档作为普通候选；未提供 `continuous` 时按单条连续文件处理。预合成的拼接素材应写 `continuous:false`，不能声称编排器自动识别了其内部切镜。
- `speed` 默认 1，必须为有限数且至少 0.5。`allowSlowdown:false` 禁止程序进一步慢放。图片可填 `displayDuration`（秒），默认单次 4 秒；图片不会无限时长兜底。
- `trimIn/trimOut` 必须在实际文件时长内；有效区间向内对齐当前输出帧率。无效数值、零长区间、低于 0.5 的速度在 prepare 时直接报错。

长展示在同档优质候选内比较：精彩连续原速长段、精彩原速短段组合、最低 0.5 的精彩长段/组合、普通短段、动图动效、图片动效。同等精彩才优先连续。优质 S/A 静态图仍先于 B/C 实机；高档不够时才补低档。能使用一条精彩长段时不人为切碎。片尾可直接传多个 finish 候选，不必先用 FFmpeg 合成。

## 来源区间与防重复

同一个原始文件可按不同有效入出点出现多次。默认 `sourceId` 为首次导入时解析后的真实绝对路径，保存任务时保留它；同一路径即使被 staging 成不同名字也保持同一来源。

若输入是已裁切/变速的派生文件，宿主须说明它来自哪里。例如本地 `cut.mp4` 的 0—6.4 秒来自原片 71.2—77.6 秒：

```json
{
  "path": "D:/media/cut.mp4",
  "role": "finish",
  "trimIn": 0,
  "trimOut": 6.4,
  "sourceId": "original-film-A",
  "sourceIn": 71.2,
  "sourceOut": 77.6,
  "qualityTier": "S",
  "excitement": "exciting"
}
```

`sourceIn/sourceOut` 对应本候选有效 trim 区间，在取子段时按线性映射消费原片区间。拼接素材包含多个不连续来源时，拆成各自候选提供；不要给整个蒙太奇伪造一条连续原片区间。没有提供共同来源的改名/拼接文件，程序无法识别为同一画面，仍需宿主核对。

开场/底板/揭晓/收尾分别分配原片区间；开场和收尾内部不循环，不能和其他位置重复。底板固定可循环；高光默认两段优选短镜头，按每个角色自己的揭晓次数交替。明确提供更多互不重叠的 S/A 高光时继续轮换；只有一段好高光则返回简短补选提示并沿用该段。V05 的交替全屏开场会继续消费上次用到的原片位置，不在返回该角色时倒回第一帧。

## 返回与缺口

成功时任务正常返回，并增加 `compiled.mediaPlanning: {version:1, notes:[]}`。实际渲染读取 `scenes[].media.a/b` 的逐段 `{from,duration,clip,loop}`；`from/duration` 是 scene 内的帧数，`clip` 含实际区间及规划后的速度。这些是剪辑数据，不是验收回执。

素材不足时抛出 `MediaPlanError`；HTTP 返回 400：

```json
{
  "code": "MEDIA_GAPS",
  "error": "A / finish：仍缺 1.000 秒展示……",
  "gaps": [{"side":"a","character":"A","role":"finish","requiredSeconds":7,"availableSeconds":6,"missingSeconds":1,"action":"补充不重复的 finish 素材……"}],
  "notes": []
}
```

宿主只按 `gaps` 补对应角色、用途和缺少长度，再 prepare；不因此更换已选音乐模板。`planMedia` 导出为无文件写入的函数，可先消费已探测候选做规划。正式 prepare 同 ID 省略 templateId 时继承已有模板及原抽签信息；只有显式传其他模板 ID 或 `random` 才换。

## 导出与旧工程

旧 compiled 没有 `scenes[].media` 时仍走原有画面选择，以便继续打开、渲染已有工程。重新 prepare 会采用本次编排规则，因此旧演示里的跨用途复用、0.44 速度或只有单图的长展示可能需要按缺口补素材；程序不会静默保留不合规的新编排。

每次渲染使用独立 bundle 目录与唯一输出文件名，打开上次 MP4 的播放器不再占用下一次导出的固定文件。`progress.json` 指向最新成功输出，错误时保留 `lastSuccessfulOutput`。CLI 支持 `--out 独立输出目录`，不需关闭用户服务或浏览器。

```powershell
npm test
npm run typecheck
node scripts/audit-media-plan.mjs
node scripts/render-job.mjs --job 工程ID --range 0:90 --out "D:/独立预览"
```

小型实测只验证候选编排及画面消费；角色、精彩程度、版本、水印可裁切性和最终观感仍需要宿主实际看素材和导出接点。
