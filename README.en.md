# PEQ-WebUI

[简体中文](README.md) · [English](README.en.md)

Browser-based parametric EQ console for **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** on Windows.

Edit multi-band PEQ, manage presets, and activate a profile in one click — Equalizer APO applies it system-wide in real time.

## Features

- **Visual PEQ editor** — frequency-response chart, drag bands, adjust F / gain / Q
- **Presets** — create, rename, reorder, activate or bypass (`pure`)
- **Auto fit** (core) — match device raw response to a target curve and generate multi-band PK/LS/HS
- **Curve library** — sample device/target curves; import CSV or AutoEq data
- **Optional AutoEq search** — pull measurements & ready-made PEQ from a local [AutoEq](https://github.com/jaakkopasanen/AutoEq) tree
- **Local only** — listens on `127.0.0.1:9100`; no cloud account required

## Auto fit (core feature)

In one sentence:

> **Given the headphone’s raw frequency response (Raw) and a target curve (Target), compute parametric EQ bands so that Raw + EQ tracks Target as closely as possible.**

![Auto-fit illustration: Raw / Target / EQ / Equalized](docs/autofit-preview.svg)

The figure is an **illustration** generated from public sample curves in this repo (not a live optimizer run):

| Curve | Meaning |
|---|---|
| Gray solid **Raw** | Measured device response |
| Blue dashed **Target** | Target curve (e.g. Harman over-ear 2018) |
| Orange solid **EQ** | Combined filter response from the fit |
| Blue thick **Equalized** | Predicted Raw + EQ |

### Pipeline

1. **Align** — shift both curves so the mean in ~500 Hz–2 kHz is 0 dB  
2. **Error field** — sample `Target − Raw` on a log-frequency grid  
3. **Place & optimize** — Peaking (optional shelves) where error is large; refine F / Gain / Q  
4. **Preamp** — suggest negative preamp from max positive gain to reduce clipping  
5. **Write APO text** — `Filter: ON PK Fc … Gain … Q …`; activation atomically writes `hl-active.txt`

### Two engines

| Engine | Needs | Notes |
|---|---|---|
| **Fast** | `numpy` only | Low-frequency anchors + greedy peaks + coordinate descent |
| **Precise** | `scipy` + local AutoEq `autoeq` package | Bridges AutoEq SLSQP joint optimization; falls back if missing |

### Typical usage

1. Pick device curve (or import raw from AutoEq)  
2. Pick target (Harman / diffuse field / flat / custom CSV)  
3. Open **Auto fit** or **Fit preview**  
4. Check Equalized vs Target on the chart; hand-tweak bands if needed  
5. **Adopt draft** → **Save preset** → double-click to activate  

More: [用户操作手册.md](用户操作手册.md) (Chinese) · [README.md](README.md)

## Quick start

**Requirements:** Windows 10/11, [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) installed, Python 3.10+, `numpy` (`scipy` optional for precise fitting).

```powershell
cd PEQ-WebUI
py -m pip install numpy
.\start-webui.ps1
```

Open **http://127.0.0.1:9100**

### First-time APO takeover (once)

```powershell
# Admin PowerShell, from the project root
py -c "from apo_backend import ApoBackend; a=ApoBackend(); a.set_auto_install_enabled(True); print(a.install(by='admin'))"
```

Details: [部署手册.md](部署手册.md).

### Optional AutoEq database

```text
<repo>/../AutoEq-4.1.2/AutoEq-4.1.2
```

Override with `AUTOEQ_ROOT`. Full AutoEq tree is **not** shipped here.

## Docs

See [README.md](README.md) for the full Chinese doc index, [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md), [NOTICE.md](NOTICE.md), [LICENSE](LICENSE) (MIT).

## Acknowledgments

- **[AutoEq](https://github.com/jaakkopasanen/AutoEq)** — measurement layout, target conventions, precise PEQ ideas (MIT); auto-fit parameter semantics largely follow this project  
- **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** — system audio engine this UI configures  
- Measurement communities (via AutoEq public data): oratory1990, crinacle, Rtings, InnerFidelity, Super\* Review / squig.link, Kuulokenurkka, Auriculares Argentina, …  
- Harman research targets as redistributed in the AutoEq ecosystem (not an endorsement)

**Not affiliated** with Equalizer APO, AutoEq, Harman, Rtings, crinacle, or oratory1990.
