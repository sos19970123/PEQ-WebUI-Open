# PEQ-WebUI

[English](README.md) · [简体中文](README.zh.md)

Browser-based parametric EQ console for **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** on Windows.

Edit multi-band PEQ, manage presets, and activate a profile in one click — Equalizer APO applies it system-wide in real time.

## Features

- **Visual PEQ editor** — frequency-response chart, drag bands, adjust F / gain / Q
- **Presets** — create, rename, reorder, activate or bypass (`pure`)
- **Auto fit** — match a target curve (Harman, diffuse field, flat, custom, …)
- **Curve library** — sample device/target curves; import CSV or AutoEq data
- **Optional AutoEq search** — pull measurements & ready-made PEQ from a local [AutoEq](https://github.com/jaakkopasanen/AutoEq) tree
- **Local only** — listens on `127.0.0.1:9100`; no cloud account required

## Quick start

**Requirements:** Windows 10/11, [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) installed, Python 3.10+, `numpy` (`scipy` optional for precise fitting).

```powershell
cd PEQ-WebUI
py -m pip install numpy
.\start-webui.ps1
```

Open **http://127.0.0.1:9100**

Or double-click `启动PEQ-WebUI.cmd`.

### First-time APO takeover (once)

Equalizer APO normally reads `C:\Program Files\EqualizerAPO\config` (often not writable without admin). This app migrates config to the project folder and points the registry `ConfigPath` there — **one admin step**, then daily use needs no elevation.

See [部署手册.md](部署手册.md) (deployment pitfalls, rollback) and [用户操作手册.md](用户操作手册.md) (daily use).

```powershell
# Admin PowerShell, from the project root
py -c "from apo_backend import ApoBackend; a=ApoBackend(); a.set_auto_install_enabled(True); print(a.install(by='admin'))"
```

### Optional AutoEq database

Default path (override with `AUTOEQ_ROOT`):

```text
<repo>/../AutoEq-4.1.2/AutoEq-4.1.2
```

Clone/download AutoEq separately — the full database is large and is not shipped in this repo.

## Docs

| Document | Language | Contents |
|---|---|---|
| [README.zh.md](README.zh.md) | 中文 | 简介与快速开始 |
| [部署手册.md](部署手册.md) | 中文 | APO 安装 / 权限 / 接管 / 回滚 |
| [用户操作手册.md](用户操作手册.md) | 中文 | 日常操作 |
| [开发维护文档.md](开发维护文档.md) | 中文 | 模块与 API |
| [webui操作手册.html](webui操作手册.html) | 中文 | HTML 手册 |
| [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) | EN | Credits |
| [NOTICE.md](NOTICE.md) | EN | Third-party licenses & data sources |
| [LICENSE](LICENSE) | — | MIT |

## Acknowledgments

This project builds on excellent open work:

- **[AutoEq](https://github.com/jaakkopasanen/AutoEq)** — measurement catalog, target conventions, and precise PEQ optimizer ideas (MIT)
- **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** — the system audio engine this UI configures
- Measurement communities: oratory1990, crinacle, Rtings, InnerFidelity, Super\* Review / squig.link, Kuulokenurkka, Auriculares Argentina, and others (via AutoEq’s public dataset)
- Harman research target curves as redistributed in the AutoEq ecosystem (not an endorsement)

Full credits and legal notes: [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) · [NOTICE.md](NOTICE.md).

**Not affiliated** with Equalizer APO, AutoEq, Harman, Rtings, crinacle, or oratory1990.

## License

Code: [MIT](LICENSE). Third-party software and measurement data remain under their own terms — see [NOTICE.md](NOTICE.md).
