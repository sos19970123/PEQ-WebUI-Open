# Third-party notices

PEQ-WebUI is an independent project. It is **not affiliated with**, endorsed by, or sponsored by any of the projects or organizations below.

## Software this project talks to or builds upon

| Project | Role | License / terms | Link |
|---|---|---|---|
| **Equalizer APO** | System-wide audio engine. This app writes plain-text APO config files; it does **not** bundle Equalizer APO binaries. | GPL-3.0 (see upstream) | https://sourceforge.net/projects/equalizerapo/ |
| **AutoEq** (jaakkopasanen) | Local measurement/PEQ database and optional precise PEQ optimizer (`autoeq` package). **Not vendored** in this repo; obtain separately and set `AUTOEQ_ROOT`. | MIT | https://github.com/jaakkopasanen/AutoEq |
| **numpy / scipy** | Numerical fitting (scipy optional for precise mode). | BSD-style (upstream) | https://numpy.org/ · https://www.scipy.org/ |
| **Peace GUI** | Optional third-party Equalizer APO front-end. **Binaries and Peace assets are not redistributed** here. | See Peace / Equalizer APO distribution terms | via Equalizer APO distribution |

## Measurement sources & target curves

Sample curve JSON under `curves/` is derived from **public** headphone measurement communities and databases, including (non-exhaustive):

- [oratory1990](https://www.reddit.com/r/oratory1990/) measurement archive / AutoEq mirror  
- [crinacle](https://crinacle.com/graphs/headphones/)  
- [Rtings](https://www.rtings.com/headphones)  
- InnerFidelity archives (via AutoEq)  
- [Super* Review / squig.link](https://squig.link/)  
- [Kuulokenurkka](https://kuulokenurkka.com/)  
- Auriculares Argentina squig  
- Headphone.com legacy data (via AutoEq)  
- Harman International research target curves **as redistributed by AutoEq** (e.g. Harman over-ear / in-ear targets). Harman targets remain subject to Harman’s own rights and terms; inclusion here is for interoperability with the open AutoEq ecosystem and does **not** grant any Harman trademark or endorsement.

**You are responsible** for complying with each source’s license, terms of use, and attribution requirements when redistributing or commercially using measurement data.

## What this repository does *not* include

- Equalizer APO / Peace installers or binaries  
- Full AutoEq database (~800MB+)  
- Personal listening presets, private measurement dumps, or machine-specific paths  

## Algorithm inspiration

The fast fitter (`autofit.py`) and the optional AutoEq PEQ bridge (`autoeq_engine.py`) follow ideas and parameter conventions widely used in the open AutoEq / parametric-EQ community (multi-band PK/LS/HS, preamp headroom, frequency-weighted fitting). We credit AutoEq as the primary open-source reference implementation.
