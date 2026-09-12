# PEQ WebUI

基于 **EqualizerAPO** 的本地调音台：浏览器编辑多段参数 EQ、管理预设、一键激活，写入系统音频引擎实时生效。

- 仅监听 `127.0.0.1:9100`
- 不连接 Reaper、不切换默认输出设备
- 日常使用无需管理员（**首次接管** APO 配置目录需要一次 UAC，见部署手册）

## 文档

| 文档 | 用途 |
|---|---|
| [部署手册.md](部署手册.md) | EqualizerAPO 安装坑、权限、接管、回滚、排查 |
| [用户操作手册.md](用户操作手册.md) | 日常调音操作 |
| [开发维护文档.md](开发维护文档.md) | 模块、API、数据契约 |
| [webui操作手册.html](webui操作手册.html) | HTML 版操作说明（浏览器打开） |

## 快速开始

```powershell
cd F:\MIMO-Space\PEQ-WebUI
py -m pip install numpy          # 可选: py -m pip install scipy
.\start-webui.ps1
# 浏览器打开 http://127.0.0.1:9100
```

或双击 `启动PEQ-WebUI.cmd`。

**首次部署请先读[部署手册.md](部署手册.md) §5「首次接管」**，否则预设可编辑但系统声音不会变。

## 目录结构

```text
PEQ-WebUI/
├── mixer_web.py          # HTTP :9100（REST + SSE + 静态托管）
├── apo_backend.py        # APO 渲染/原子写/激活/接管/迁移/状态
├── autoeq_store.py       # 本地 AutoEq 数据访问
├── autoeq_engine.py      # 可选精确拟合（scipy + AutoEq PEQ）
├── autofit.py            # 纯 numpy 快速拟合
├── curve_store.py        # 设备/目标曲线库
├── eq_parser.py          # APO/AutoEq/CSV/JSON → bands
├── apo-presets/          # 预设 *.txt + presets.json + apo-state.json
├── apo-config/           # APO ConfigPath 迁移后的可写配置目录
├── curves/               # devices/ 与 targets/ JSON
├── measurements/         # 历史测量数据与一次性分析脚本
├── webui/                # 纯静态前端
├── tools/                # 导入/播种脚本
├── start-webui.ps1
└── 启动PEQ-WebUI.cmd
```

## AutoEq 依赖（可选）

默认在同级查找：

```text
F:\MIMO-Space\AutoEq-4.1.2\AutoEq-4.1.2
```

用环境变量覆盖：

```powershell
$env:AUTOEQ_ROOT = "D:\your\AutoEq-4.1.2"
```

需要其中的 `results/`、`targets/`；精确拟合还需要 `autoeq/` 包。  
**完整 AutoEq 约 800MB+，请勿提交进本仓库。**

## 环境变量

| 变量 | 默认 |
|---|---|
| `APO_PRESET_DIR` | `<项目>/apo-presets` |
| `APO_CONFIG_DIR` | `<项目>/apo-config` |
| `AUTOEQ_ROOT` | `<项目>/../AutoEq-4.1.2/AutoEq-4.1.2` |
| `MIXER_STATE_FILE` | `<项目>/state.json` |

## 主要 API（摘要）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 后端 + APO 状态 |
| GET | `/api/presets` | 预设列表 |
| POST | `/api/preset/activate` | 激活 / 直通 |
| POST | `/api/eq/apply` | 保存预设 |
| POST | `/api/eq/autofit` | 自动拟合 |
| POST | `/api/admin/install` / `uninstall` | APO 接管 / 回退 |

完整契约见《开发维护文档.md》。

## 铁律

1. 只监听本机 `127.0.0.1:9100`
2. 不访问 Reaper、不切默认播放设备
3. 所有 APO 写 = 原子文件替换（temp + `os.replace`）
4. 预设内容只由本后端写；外部程序只做激活（写 `hl-active.txt`）时遵守开发文档 §7.9

## 许可与数据

- 代码：按你的仓库许可证发布
- 曲线/预设：含个人测量与调优结果；**公开分享前请自行清理** `state.json`、个人 `apo-presets/` 等
- AutoEq 数据：遵循上游 [jaakkopasanen/AutoEq](https://github.com/jaakkopasanen/AutoEq) 许可，独立获取
