# PEQ-WebUI

[English](README.md) · [简体中文](README.zh.md)

Windows 上面向 **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** 的浏览器参数 EQ 控制台。

在网页里编辑多段 PEQ、管理预设、一键激活；Equalizer APO 会实时把配置作用到系统音频。

## 功能

- **可视化 PEQ 编辑** — 频响曲线、拖点改频率/增益/Q
- **预设管理** — 新建、重命名、排序、激活或直通（`pure`）
- **自动拟合** — 对齐目标曲线（Harman / 扩散场 / 平直 / 自定义等）
- **曲线库** — 示例设备/目标曲线，支持 CSV 与 AutoEq 导入
- **可选 AutoEq 检索** — 从本地 [AutoEq](https://github.com/jaakkopasanen/AutoEq) 库搜索耳机并导入测量/PEQ
- **纯本地** — 仅监听 `127.0.0.1:9100`，无需账号、不上传云端

## 快速开始

**环境：** Windows 10/11，已安装 [Equalizer APO](https://sourceforge.net/projects/equalizerapo/)，Python 3.10+，`numpy`（可选 `scipy` 用于精确拟合）。

```powershell
cd PEQ-WebUI
py -m pip install numpy
.\start-webui.ps1
```

浏览器打开 **http://127.0.0.1:9100**

也可双击 `启动PEQ-WebUI.cmd`。

### 首次接管 APO（仅一次）

Equalizer APO 默认读取 `C:\Program Files\EqualizerAPO\config`（普通权限常写不进）。本项目会把配置迁到项目内目录，并把注册表 `ConfigPath` 指过去——**需要一次管理员操作**，之后日常使用无需提权。

细节见 [部署手册.md](部署手册.md)（安装坑 / 回滚）与 [用户操作手册.md](用户操作手册.md)（日常操作）。

```powershell
# 管理员 PowerShell，在项目根目录执行
py -c "from apo_backend import ApoBackend; a=ApoBackend(); a.set_auto_install_enabled(True); print(a.install(by='admin'))"
```

### 可选 AutoEq 数据库

默认路径（可用环境变量 `AUTOEQ_ROOT` 覆盖）：

```text
<仓库>/../AutoEq-4.1.2/AutoEq-4.1.2
```

请自行获取 AutoEq 完整库；体积较大，**不**随本仓库分发。

## 文档

| 文档 | 语言 | 内容 |
|---|---|---|
| [README.md](README.md) | EN | Overview |
| [部署手册.md](部署手册.md) | 中文 | APO 安装 / 权限 / 接管 / 回滚 |
| [用户操作手册.md](用户操作手册.md) | 中文 | 日常操作 |
| [开发维护文档.md](开发维护文档.md) | 中文 | 模块与 API |
| [webui操作手册.html](webui操作手册.html) | 中文 | HTML 手册 |
| [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) | EN | 致谢 |
| [NOTICE.md](NOTICE.md) | EN | 第三方许可与数据来源 |
| [LICENSE](LICENSE) | — | MIT |

## 致谢

本项目站在许多优秀开源与测量工作的肩膀上：

- **[AutoEq](https://github.com/jaakkopasanen/AutoEq)** — 测量库组织、目标曲线约定与精确 PEQ 优化思路（MIT）
- **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** — 本 UI 所配置的系统音频引擎
- 测量社区：oratory1990、crinacle、Rtings、InnerFidelity、Super\* Review / squig.link、Kuulokenurkka、Auriculares Argentina 等（经由 AutoEq 公开数据集）
- Harman 研究目标曲线（经 AutoEq 生态再分发；**非**官方背书）

完整署名与法律说明：[ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) · [NOTICE.md](NOTICE.md)。

与 Equalizer APO、AutoEq、Harman、Rtings、crinacle、oratory1990 等**无官方关联**。

## 许可

代码：[MIT](LICENSE)。第三方软件与测量数据版权归各自权利人，详见 [NOTICE.md](NOTICE.md)。
