# 宿主工具协议与本地接口

以下协议是宿主适配约定，不声称当前对话已经提供了同名工具。适配器必须把真实工具名、实际能力和调用结果写入记录；工具不存在时返回缺口。脚本不能直接调用模型对话工具，也不能靠写一个端点名就获得搜索或视觉能力。

## 调用与输出

按[执行效率规则](execution-efficiency.md)按需调用，复用未变化的成功分析；不为每个语义判断启动命令。有`--output`的统一CLI默认打印短摘要，完整结果保存到文件；需要原始完整stdout时加`--full-output`，无`--output`时保持完整输出。摘要不代替读取相关错误详情、关键来源或宿主实际验收。

## 通用封套

```json
{
  "status": "ok|partial|blocked|unavailable|unconfigured|unverified|error",
  "adapter": "实际工具或本机程序的名称",
  "capability_checked_at": "UTC ISO8601",
  "data": {},
  "sources": [],
  "assumptions": [],
  "needs": [],
  "errors": []
}
```

`ok`只表示该次调用成功。失败、空结果和能力不可用必须保留，不得输出虚假的引文、OCR、帧测量或已读取声明。协议中数组为空是明确结果，字段缺失表示未知；未知不能默认为零。

## host_search

输入：`query`、可选 `languages`、`domains`、`date_range`、`limit`。输出 `results[]` 的 `title/url/snippet/published_at/accessed_at/tool_name`，并记录是否只有摘要。日期没有证据时为 `null`。优先原始语言与官方域名，但也保留反例查询和来源失败记录。

搜索结果只能发现入口。要建立原作证据，继续用实际浏览器/连接器读取原文，或调用 `source` 保存内容；搜索摘要不能伪装成原作正文。网页拒绝访问时用 `blocked`，不声称已经取得其原作。

适配示例：宿主实际可用的网页搜索工具。不能在未配置搜索服务时，让脚本返回预制“搜索结果”。

## host_vision

输入：明确授权的 `images[]`（本地绝对路径或宿主可读取的附件ID）、任务 `ocr|inspect|measure|compare`、要检查的问题、可选标尺与裁切范围。视频先由宿主按真实时间基准抽帧；传入帧需携带原视频、时间戳、帧号。

输出：实际 `backend`（宿主视觉/本机模型/外部VLM）、模型名和版本（已知时）、逐图观察、OCR候选、识别置信度或“不确定”、测量端点/像素坐标、标尺、假设、原图定位及 `needs`。只凭单图不能生成持续时间或被遮挡部分的确定数据。

能力探测必须分三步：

1. 发现实际宿主视觉能力或已安装本机推理程序；外部VLM需已有合适的配置和素材发送授权。
2. 检查端点/模型配置；未配置返回 `unconfigured`，有配置但未成功调用返回 `unverified`。
3. 对本次实际图像成功调用后，才返回 `ok` 并记录真实结果。不能把“支持兼容API”“设置了环境变量”当作已可用。

外部VLM适配器负责鉴权与传输，但报告不得落盘密钥。默认不上传本地文件。无需视觉时不调用；OCR后仍核对关键数学符号、量词及否定词。

### 已实现的可选视觉客户端

`scripts/vision_adapter.py` 是真实的 OpenAI Chat Completions 兼容客户端，可连接已配置的云端或本机视觉模型；不用预制描述代替调用。优先使用宿主内置读图；只有用户授权外部发送素材且已有配置时调用此适配器。本机模型可使用兼容服务（例如 Ollama 的兼容入口），不要求下载任何特定模型。

PowerShell 临时配置示例（服务与模型必须实际存在）：

```powershell
$env:BATTLE_VISION_BASE_URL = 'http://localhost:11434/v1'
$env:BATTLE_VISION_MODEL = '你已经安装并验证支持视觉的模型名'
python scripts/battle.py vision --input vision-request.json --output vision-result.json
```

云端服务使用 HTTPS；需要密钥时由 `BATTLE_VISION_API_KEY` 提供，不能写入案例或报告。请求格式为 `{"images":["D:\\case\\panel.png"],"prompt":"逐格描述动作、文字与可见标尺；区分观察和推测","timeout_seconds":45}`。接受1–12张实际本地图片并记录原件哈希；动图先抽帧。无配置返回 `needs_configuration`，连接或模型不支持时如实返回错误；只有实际响应成功才返回 `ok`。客户端不验证模型描述正确性，Agent 仍需逐图核查角色、分镜顺序和关键符号。

接口参考：[OpenAI 图像与视觉](https://developers.openai.com/api/docs/guides/images-vision)、[Ollama OpenAI 兼容接口](https://docs.ollama.com/api/openai-compatibility)。这两份文档说明协议能力，不代表任何特定模型已经在本机安装或本次已调用成功。

## source：获取与留存

已实现的Python入口：

```python
from sources import fetch_and_record
result = fetch_and_record(url_or_local_path, output_dir, max_bytes=2*1024*1024)
```

命令行：

```powershell
python scripts/sources.py --url "https://scp-wiki.wikidot.com/scp-3812" --output "D:\case\sources"
python scripts/sources.py --file "D:\input\work.pdf" --output "D:\case\sources" --max-bytes 4194304
```

返回字段：`schema_version/status/original_url/final_url/http_status/accessed_at/content_type/bytes_saved/truncated/sha256/paths/needs/errors/warnings/extraction/redirects`；另可有 `source_kind/content_encoding`。`paths` 的 `raw/text/metadata` 全位于指定输出目录；未收到原字节时 `raw=null`。`sha256`对应 `.raw` 已保存字节，不是抽取文本。`ok`退出码0，其他状态退出码2。

`fetch_and_record` 与两种 sources CLI 会把HTTP(S)真实回执自动追加到 [站点经验库](site-experience.md)，返回 `site_experience` 表示是否成功落档；本地文件不记成站点。下载成功只记 `fetched_unreviewed`，核读正文后由Agent追加可读/部分可读记录；失败和阻断也保留。日志写入失败会明确告警，原获取结果仍保留。低层 `fetch_source` 仍只取证、无经验库写入；若宿主直接使用它或其他浏览工具，须另调用 `sites record` 归档本批真实结果。Python可用 `site_db` 参数指定经验库；否则遵循BATTLE_SITE_DB或全局累计库。

状态：`ok`、`partial`（超过大小限制或内容不完整）、`blocked`（401/403/407/429或登录/验证码检测）、`needs_extractor`（PDF/二进制等缺少提取能力）、`error`。原始错误页可以保留，但不是目标作品正文。HTML阻断检测为启发式，疑似误报需人工核查原始内容，不自动绕过。

HTTP(S)要求公网且不含URL凭据；每次跳转重新校验，最多5次。禁用代理环境变量以免悄悄改变取证路径。默认2MiB、硬上限20MiB；15秒socket超时，DNS解析可能受系统时限影响。需要严格总时限/恶意PDF防护时，由宿主对子进程设资源和时间限制。依次尝试现装pypdf、PyPDF2、fitz，记录失败并回退；无库保留原件并返回需求，不安装、不把图片PDF假称已OCR。中英文验证码标题、登录和挑战页返回blocked。

## physics：物理估算

接口族的输入契约：`phenomenon/mechanism/parameters[]/units/source_ids/assumptions/mode`。每个参数带数值或区间、单位、测量/材料来源及可信度。输出至少含公式、逐步代入、维度检查、结果区间、敏感性、能证明的战斗属性和不能继承的属性。

当前统一入口为 `python scripts/battle.py physics --input INPUT.json`。模型不匹配时返回缺口，不能自动套常量造等级。力(N)、功/能量(J)、功率(W)、压强(Pa)分别输出。缺参数可采用有依据的合理假设，但假设值和条件结论需显式记录；不得把推算结果标为实测。

## high：高层结构与规则映射

新请求使用`mode:integrated`；旧模式只作兼容读取，不自动升级综合完成。输入契约：原作构造节点、`number_domain/background_axioms/base_object/successor_rule/limit_rule/operation_scope/native_transcendence`、角色归属、具名规则与版本、模式、证据及假设。输出契约：类型检查、作品内关系、可证明数学结论、条件桥接、规则映射、未定项与反例。

当前统一入口为 `python scripts/battle.py high --input INPUT.json`，规则清单为 `python scripts/battle.py rules`。不承诺把所有自定义构造化成单一数字。序数、基数、真类、理论/模型和作品自定义对象不能无类型混算；持续递归不能自动推出阿列夫一或不可达。按[综合选档](modes-scaling.md)同时审查有据强解释和反向限制链，声明适用状态与具体条件；不再分别输出最高／常态／扒下限角色档位。

## graph：证据与属性归属

输入契约：带ID的证据/结构/角色/结论节点；带类型、来源、适用版本状态和假设的边。边类型至少区分包含、超越、抵达、感知、创造、毁灭、支配、攻击、防御、速度、范围。

输出契约：每条结论的证据路径、缺边、循环、冲突、状态混用及被撤销假设影响。高层移动、作者视角或宇宙存在本身不自动生成攻击/耐久边。当前案例验证入口为 `python scripts/battle.py validate --input CASE.json`，Python入口为 `evidence.validate_case`；分析入口为 `evidence.analyze_case`。输入细节以根 `scripts/evidence.py` 的当前schema为准；该模块的来源字段使用 `access=verified|provided|indexed|blocked` 等、`origin=primary|community|measurement|assumption|synthetic`，每项提供 `locator`。来源抓取结果的 `status=ok` 不能直接等同于案例层面原作/版本已核验，转换时需补上人工/宿主核对。

## report：复核报告

输入契约：固定任务范围、规则版本、统一综合候选采纳表、来源包、计算/构造结果、证据图、假设及阻断状态。输出：可阅读报告及机器可读清单，包含结论、支持链、反例、撤销假设后的变化、文件链接和未完成项。

当前统一报告入口为 `python scripts/battle.py analyze --input CASE.json --mode integrated --output DIR`；预检使用 `python scripts/battle.py doctor`，媒体能力使用 `python scripts/battle.py media --input INPUT.json`，来源也可经 `python scripts/battle.py sources --url URL --output DIR` 或 `--file PATH` 调用。正文必须区分“原作已确认”“有依据的估计”“指定规则下的映射”“待核验”。自动报告只呈现已取得的数据，不能补造缺失场景或把 `blocked/partial/needs_extractor` 改写成完整核验。
