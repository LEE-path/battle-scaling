# B站媒体：扫码登录与实际高清下载

只用于媒体素材取得，不重跑角色评级。适配器 `scripts/bili_media.py` 直接请求B站扫码接口，再由独立的 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 提取当前会话可用的音视频流。无须操作下载器或浏览器窗口；不依赖 JiJiDown 可执行文件，也不分发其代码。依赖为 requests（Apache-2.0）、qrcode（BSD）、yt-dlp（其上游许可），以及FFmpeg/ffprobe；复用宿主已有环境。

```powershell
# 推荐：本机二维码展示页会自动刷新过期码；由用户在B站App扫码并确认
python scripts/bili_media.py login --port 3212
# 无法展示本机页面时，可生成静态二维码并一次查询状态
python scripts/bili_media.py qr-start --out "B站登录.png"
python scripts/bili_media.py qr-status
python scripts/bili_media.py status

# 先看真正返回的轨道，不把标题“4K”当实际画质
python scripts/bili_media.py search "角色名 对手 场景" --limit 6 --out "候选.json"
# 也可不带角色名，用其出场影视与场景找原片
python scripts/bili_media.py search "作品名 具体场景" --limit 6
python scripts/bili_media.py formats "BV链接" --page 1 --out "可用画质.json"
python scripts/bili_media.py download "BV链接" --page 1 --height 2160 --min-height 1080 --out "原片.mp4"
```

登录需用户手机确认；Agent不代输密码、验证码，不读取其他程序的历史凭据。Windows凭据使用当前用户DPAPI加密，保存在用户数据目录；其他系统使用权限600的私有文件。可用 `BATTLE_BILI_STATE_DIR` 指定私有状态位置。不得把该目录、Cookie、二维码密钥或临时认证文件打入Skill、报告、Git或发布包。短时登录状态和账号权限分开；登录不会凭空提供会员或付费资源权限。

`formats`只列当前真正可用的视频轨道；下载默认选择不高于2160p的最佳轨道，最低要求1080p。达不到要求就说明实际可用画质与登录／源片限制，不把480p放大后标为高清；若当前任务明确允许低清，可显式降低最低值。下载音视频后合并，并报告实际解码尺寸与音轨。下载成功仍须按[媒体选材](media-selection.md#干净片源与精彩优先)查看水印、硬字幕、画面质感与连续性，登录或下载工具本身不保证无水印。

本机曾观察到继承的海外代理使B站扫码TLS连接失败，适配器因此只为自己的B站请求使用直连，不改变全局代理；其他网络环境按实际情况调整。遇到服务风控、访问权限或验证要求，报告具体状态，不反复刷接口。公开视频与账号本来可访问的内容按正常权限取得，不加入付费绕过或DRM处理。

软件方法来源：只借鉴下载器“登录会话→解析分P与画质→选择当前允许轨道→下载／合并”的工作方式；本适配器为独立实现，不复制 JiJiDown 混淆代码、内嵌密钥或私有解析服务。现有 bilibili-api-python 是另一条历史可选路线，其上游已于2026年7月归档；不要继续称为维护中的首选，也不将其GPL代码随本适配器复制分发。

## 合集分P选择

链接已有`?p=N`时默认保留，包括短链解析后的目标；只有显式`--page N`才覆盖，两者都没有才默认P1。BV/av标识和视频URL按实际视频身份规范化，不从其他网站含BV字样的文本猜片源。无效或歧义分P直接说明，不静默下载第一段。
