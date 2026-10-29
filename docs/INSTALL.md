# 安装与能力配齐 / Setup and capability coverage

Download the **full distribution** ZIP from [Releases](https://github.com/LEE-path/battle-scaling/releases/latest), extract it and keep the whole folder. The Skill-only ZIP contains rating, writing, image templates and media workflows; the full ZIP additionally provides the video project, standalone novel tool, installer and release checks. A compatible host Agent must provide reasoning, web search and file/tool access.

下载完整 ZIP，解压后保留整个目录。只安装 Skill 文件夹不会自动安装视频工程。先安装 Python 3.11+；视频另需 Node.js 22.18+、npm、FFmpeg/ffprobe 和 Chrome/Edge。系统依赖从各自官网获取：[Python](https://www.python.org/downloads/)、[Node.js](https://nodejs.org/)、[FFmpeg](https://ffmpeg.org/download.html)。安装器不会静默安装系统软件或大型模型。

## Recommended full setup / 推荐完整安装

Run from the extracted repository root:

```powershell
python -X utf8 tools/setup.py check
python -X utf8 tools/setup.py install --profile full
python -X utf8 tools/setup.py check --skill-dir "~/.codex/skills/battle-scaling"
```

`install` creates an isolated `.venv`, installs lightweight media/research packages, runs the pinned video project's `npm ci`, installs the full Skill into the Codex skills folder and writes private runtime pointers to this extracted project. Use `--skill-dir <your-agent-skill-directory>` for another compatible Agent. Keep the extracted folder: its video code and `.venv` remain in use.

`install` 创建隔离环境、安装轻量依赖和视频 npm 依赖，复制完整 Skill，并绑定本次解压目录；`research/full`还将贴吧worker绑定到该隔离Python，避免宿主默认Python未装aiotieba而失效。其他 Agent 用 `--skill-dir` 指定技能目录。安装目标已有内容时需显式 `--upgrade`；替换的静态文件先备份到目标 `runtime/install-backups/`，运行数据库、用户素材、凭证及其他设置不被清空。依赖安装失败时会停止，不宣称安装完成。

```powershell
# Existing installation / 已有安装：保留运行数据，备份被替换文件
python -X utf8 tools/setup.py install --profile full --upgrade
# Only the standard-library rating/writing/novel core
python -X utf8 tools/setup.py install --profile core --skill-dir "your-agent-skills/battle-scaling"
# Media packages without npm; install npm dependencies separately
python -X utf8 tools/setup.py install --profile media --skip-npm --skill-dir "your-agent-skills/battle-scaling"
```

The full profile installs both `tools/requirements/media.txt` and `research.txt`. It does not download neural model weights, copy account sessions, configure a paid provider or install another Agent. Upstream packages retain their own licenses. Remotion eligibility follows its bundled license.

Python installation uses the successful Windows/Python 3.11 snapshot in `constraints-tested.txt`, and npm uses its lockfile. When adapting to a different platform or a changed site's extractor, update and test the relevant dependency deliberately; do not mistake the recorded snapshot for an assurance about future service behavior.

All installer profiles use an isolated environment with Pillow for inspecting bundled images before copying the Skill. The core rating/novel scripts themselves still use only the Python standard library.

## What is included, and what needs your input

| Capability / 能力 | Included / 随包提供 | Setup / 使用者准备 |
|---|---|---|
| Rating, VSB/Wangba, physics and high-tier chains / 定档、物理与叠链 | Python core, reviewed rules, references, synthetic examples | Host research/reading tools; full source works only when needed |
| Novel evidence / 论战拆书 | Shared core, standalone project, evidence tasks and acceptance workflow | Your permitted novel source; the host must actually read it |
| Stories / 战斗写作 | Full research-first workflow, characterization and reusable writing techniques | Host language model and research tools |
| Posters / 海报 | Native transparent default and alternative PNGs, layout/prompt instructions, licensed font | Character images, or an image backend for characters without an established image |
| One-image comparison / 一图流 | Pillow collage CLI, localized text, bundled font | Winner/loser images and a surrender sticker you may use (`--surrender`); no copyrighted manga panel is bundled |
| Media collection / 素材搜寻 | Site catalog, multilingual queries, selection and reveal rules, HTML extraction, clip/frame/download helpers, yt-dlp/gallery-dl dependencies | Network access and any account or site-specific authorization you need |
| Bilibili HD / B站高清 | QR login, search, formats and download code | Scan with your own account; available quality depends on actual platform access |
| Comparison video / 卡点视频 | Editable Remotion project, V01–V09 timings/effects, VS graphics, watermark and font | Matching permitted audio edit and selected character clips/images |
| Template replication / 模板复刻 | Full-length analysis-to-editable-template workflow | Your reference video/audio and a host able to inspect them |
| Image/video generation / 生图、生视频 | Backend connection, consistent-character design, model selection and fallback workflows | A working host tool, API/MCP/CLI or user-selected local model; no universal provider is implied |

The same workflows and reusable assets are available after setup; a repository cannot supply another host's model, browser permission, service quota or your media licenses. Generation backends are connected on demand. Exact provider APIs differ, so the Agent reads the actual API/CLI documentation and tests an output rather than treating a provider name as a working connection.

## Run tools through the isolated environment

```powershell
python -X utf8 tools/setup.py run battle doctor
python -X utf8 tools/setup.py run bili_media --help
python -X utf8 tools/setup.py run media_acquire --help
python -X utf8 tools/setup.py run one_image --help
python -X utf8 tools/setup.py run poster --help
python -X utf8 tools/setup.py run video_studio select-template
```

For the installed Skill, the installer records its isolated Python in `runtime/media-tools.local.json`; use that interpreter for optional media commands. Core scripts remain usable with the host Python. The video bridge auto-discovers the repository layout or uses the installed runtime pointer. Without the installer, set `BATTLE_VIDEO_STUDIO_ROOT` to the actual video project and use `--font` or the bundled font for collage output.

```powershell
# QR login / 扫码登录；credentials remain in your user environment
python -X utf8 tools/setup.py run bili_media login
# Video workbench / 视频工作台
cd tools/battle-video-studio
npm start
```

Open <http://127.0.0.1:3210>. Import authorized audio and character assets, then prepare and export. See [video instructions](../tools/battle-video-studio/README.md) for music import and editable projects. Matching only BPM or duration is insufficient for a fixed timing preset.

## Troubleshooting / 缺项处理

`setup.py check` reports actual packages, executable paths, Node compatibility, browser detection and npm installation. A present source file is not a verified online download or a working model. If the current shell cannot find Node/FFmpeg, restart it after installing or put the executables on PATH. On Linux/macOS, start the video workbench with `npm start`; the convenience `.ps1` launcher is Windows-specific. A headless environment may need its browser/system dependencies configured separately.

User runtime settings, acquisition histories, credentials, source media and outputs are excluded from distribution. Do not put secrets in prompts, public jobs or static package files. Release verification is separate from normal rating, storytelling and media creation; it is not a per-output acceptance gate.

The installer verifies the shipped static files while preserving additional user runtime files; `verify-static` is only this installation check. Public release preparation still uses `tools/verify_package.py`, which checks all upload candidates and is never replaced by the installer check.

## Optional OCR environments / 按需安装OCR与公式环境

默认`full`不安装神经OCR或生成模型。下列兼容环境需Python 3.11/3.12，使用独立`.venv-ocr`／`.venv-formula`，不改主环境。显式选择这些命令会安装上游包；这些包可能自带或获取识别模型资源，不能将它们理解为零模型下载。公式适配器仍只加载已经提供的四个本地模型文件，未配置不隐式下载。

```powershell
python -X utf8 tools/setup.py optional ocr
python -X utf8 tools/setup.py run ocr_pdf --input book.pdf --output ocr-new
python -X utf8 tools/setup.py optional formula --skill-dir "your-agent-skills/battle-scaling" --model-dir "your-existing-formula-models"
python -X utf8 tools/setup.py run formula_adapter --help
```

The OCR recipes preserve the existing adapters' compatible APIs; they do not claim these older packages are the latest recommended OCR stack. RapidOCR now develops its unified package rather than the legacy ONNX-specific package; migration needs a separately validated adapter. See [upstream installation guidance](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/) and [RapidLaTeXOCR](https://github.com/RapidAI/RapidLaTeXOCR). PyMuPDF's AGPL/commercial terms remain applicable. These optional recipes do not install an image/video generation backend.

完整能力、安装入口与必须自行提供的内容见[能力对照表](CAPABILITIES.md)。隔离环境中的`setup.py run`会为OCR/公式选择对应可选解释器；没有安装时不冒充可推理。其他API/MCP/CLI由Agent按照随包接入流程绑定实际可用工具。
