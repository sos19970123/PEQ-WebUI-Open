# PEQ-WebUI

[English](README.md) · [简体中文](README.zh.md)

基于 **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** 的本地参数 EQ 控制台：在浏览器中编辑多段 PEQ、管理预设、一键激活。

- 仅监听 `127.0.0.1:9100`
- **不**控制 Reaper / Peace，不切换系统默认输出设备
- 日常使用无需管理员（**首次**接管 APO 配置目录可能弹一次 UAC）

> **公开示例版**：不含个人预设与本机专属数据。测量请自行通过 [AutoEq](https://github.com/jaakkopasanen/AutoEq) 或 CSV 导入。

## 文档

| 文档 | 说明 |
|---|---|
| [部署手册.md](部署手册.md) | Equalizer APO 安装坑、ConfigPath、UAC、回滚 |
| [用户操作手册.md](用户操作手册.md) | 日常操作 |
| [开发维护文档.md](开发维护文档.md) | 模块与 API |
| [webui操作手册.html](webui操作手册.html) | HTML 手册 |
| [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) | 致谢 |
| [NOTICE.md](NOTICE.md) | 第三方许可与测量数据来源 |
| [LICENSE](LICENSE) | 代码 MIT |

## 快速开始

```powershell
cd <你的路径>/PEQ-WebUI
py -m pip install numpy
# 可选精确拟合: py -m pip install scipy
.\start-webui.ps1
# 浏览器打开 http://127.0.0.1:9100
```

或双击 `启动PEQ-WebUI.cmd`。

**首次部署**请先读[部署手册.md](部署手册.md) §5「首次接管」，否则预设可编辑但系统声音不会变。

## 目录结构

```text
PEQ-WebUI/
├── mixer_web.py          # HTTP :9100
├── apo_backend.py        # APO 渲染/原子写/激活/接管
├── autoeq_store.py       # 本地 AutoEq 数据访问（可选）
├── autoeq_engine.py      # 精确拟合（可选，需 scipy）
├── autofit.py            # 纯 numpy 快速拟合
├── curve_store.py        # 设备/目标曲线库
├── apo-presets/          # 预设
├── apo-config/           # 接管后的 APO 配置目录
├── curves/               # 示例曲线（见 NOTICE.md）
├── webui/                # 静态前端
├── tools/
├── start-webui.ps1
└── 启动PEQ-WebUI.cmd
```

## 可选 AutoEq 数据库

默认路径（可用环境变量 `AUTOEQ_ROOT` 覆盖）：

```text
<仓库>/../AutoEq-4.1.2/AutoEq-4.1.2
```

请自行获取 [AutoEq](https://github.com/jaakkopasanen/AutoEq)。完整库体积很大（约数百 MB），**不**纳入本仓库。

## 环境变量

| 变量 | 默认 |
|---|---|
| `APO_PRESET_DIR` | `<仓库>/apo-presets` |
| `APO_CONFIG_DIR` | `<仓库>/apo-config` |
| `AUTOEQ_ROOT` | `<仓库>/../AutoEq-4.1.2/AutoEq-4.1.2` |
| `MIXER_STATE_FILE` | `<仓库>/state.json` |

## 主要 API（摘要）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/status` | 状态 |
| GET | `/api/presets` | 预设列表 |
| POST | `/api/preset/activate` | 激活 / 直通 |
| POST | `/api/eq/apply` | 保存 |
| POST | `/api/eq/autofit` | 自动拟合 |
| POST | `/api/admin/install` / `uninstall` | 接管 / 回退 |

完整契约见《开发维护文档.md》。

## 铁律

1. 只监听本机 `127.0.0.1:9100`  
2. 不访问 Reaper、不切默认播放设备  
3. 所有 APO 写 = 原子替换  
4. 预设**内容**只由本后端创作；外部程序只做激活（写 `hl-active.txt`）

## 许可与致谢

- **代码：** [MIT](LICENSE)  
- **第三方软件与测量数据：** 见 [NOTICE.md](NOTICE.md)、[ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md)  
- 与 Equalizer APO、AutoEq、Harman、Rtings、crinacle、oratory1990 等**无官方关联**

本项目的拟合思路与数据组织大量借鉴 AutoEq 及公开测量社区的成果，在此诚挚致谢。若你认为署名不完整，请开 Issue/PR，我们会尽快修正。

## 贡献指南

欢迎 Issue / PR，请：

- 不要提交个人听音 dump、本机绝对路径、商业二进制  
- 新增曲线数据时保留来源署名  
- 路径优先使用环境变量或相对路径
