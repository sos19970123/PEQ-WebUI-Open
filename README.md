# PEQ-WebUI

[English](README.md) · [简体中文](README.zh.md)

Local parametric EQ console for **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)**: edit multi-band PEQ in the browser, manage presets, activate with one click.

- Listens on `127.0.0.1:9100` only  
- Does **not** control Reaper, Peace, or system default output devices  
- Day-to-day use needs no admin rights (**one-time** APO config takeover may prompt UAC)

> Public sample build: personal presets and machine-specific dumps are **not** included. Bring your own measurements via [AutoEq](https://github.com/jaakkopasanen/AutoEq) or CSV import.

## Docs

| Doc | Purpose |
|---|---|
| [README.zh.md](README.zh.md) | Chinese quick start |
| [部署手册.md](部署手册.md) | APO install pitfalls, ConfigPath migration, UAC, rollback (ZH) |
| [用户操作手册.md](用户操作手册.md) | Daily use (ZH) |
| [开发维护文档.md](开发维护文档.md) | Modules & API (ZH) |
| [webui操作手册.html](webui操作手册.html) | HTML manual (ZH) |
| [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) | Credits |
| [NOTICE.md](NOTICE.md) | Third-party licenses & measurement sources |
| [LICENSE](LICENSE) | MIT (code) |

English deployment guide: see **Deployment** below and the ZH 部署手册 for full Equalizer APO caveats (most pitfalls are tool-specific, not language-specific).

## Quick start

```powershell
cd <path-to>/PEQ-WebUI
py -m pip install numpy
# optional precise fitter:
# py -m pip install scipy
.\start-webui.ps1
# open http://127.0.0.1:9100
```

Or double-click `启动PEQ-WebUI.cmd`.

**First deploy:** follow [部署手册.md](部署手册.md) §5 (one-time admin takeover). Until then, presets can be edited but system audio will not change.

## Layout

```text
PEQ-WebUI/
├── mixer_web.py          # HTTP :9100 (REST + SSE + static)
├── apo_backend.py        # APO render / atomic write / activate / install
├── autoeq_store.py       # local AutoEq index (optional)
├── autoeq_engine.py      # optional precise fit (scipy + AutoEq PEQ)
├── autofit.py            # pure-numpy fitter
├── curve_store.py        # device/target curve library
├── eq_parser.py
├── apo-presets/          # preset texts + manifests
├── apo-config/           # writable APO config dir after takeover
├── curves/               # sample curves (see NOTICE.md)
├── webui/                # static frontend
├── tools/
├── start-webui.ps1
└── 启动PEQ-WebUI.cmd
```

## Optional AutoEq database

Default search path (override with `AUTOEQ_ROOT`):

```text
<repo>/../AutoEq-4.1.2/AutoEq-4.1.2
```

Clone/download [AutoEq](https://github.com/jaakkopasanen/AutoEq) separately. The full database is hundreds of MB and is **not** committed here.

## Environment variables

| Variable | Default |
|---|---|
| `APO_PRESET_DIR` | `<repo>/apo-presets` |
| `APO_CONFIG_DIR` | `<repo>/apo-config` |
| `AUTOEQ_ROOT` | `<repo>/../AutoEq-4.1.2/AutoEq-4.1.2` |
| `MIXER_STATE_FILE` | `<repo>/state.json` |

## API (summary)

| Method | Path | Notes |
|---|---|---|
| GET | `/api/status` | backend + APO status |
| GET | `/api/presets` | list |
| POST | `/api/preset/activate` | activate / bypass |
| POST | `/api/eq/apply` | save preset |
| POST | `/api/eq/autofit` | auto PEQ |
| POST | `/api/admin/install` / `uninstall` | APO takeover / restore |

Full contract: 开发维护文档.md.

## Hard rules

1. Bind localhost only (`127.0.0.1:9100`)  
2. No Reaper control, no default-device switching  
3. All APO writes are atomic file replaces  
4. Preset **content** is authored by this backend; external tools may only activate (`hl-active.txt`)

## License & attribution

- **Code:** [MIT](LICENSE)  
- **Third-party software & measurements:** see [NOTICE.md](NOTICE.md) and [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md)  
- Not affiliated with Equalizer APO, AutoEq, Harman, Rtings, crinacle, or oratory1990

## Contributing

Issues and PRs welcome. Please:

- Do not commit personal listening dumps, absolute machine paths, or proprietary binaries  
- Keep attribution intact when adding curve data  
- Prefer env-var / relative paths over hard-coded drive letters
