# Acknowledgments / 致谢

PEQ-WebUI stands on the shoulders of generous open-source and measurement communities. Thank you.

## Core inspirations

- **[AutoEq](https://github.com/jaakkopasanen/AutoEq)** — Jaakko Pasanen  
  Primary reference for parametric-EQ generation, measurement catalog layout, target-curve conventions, and the optional precise optimizer path (`autoeq.peq`). MIT licensed.

- **[Equalizer APO](https://sourceforge.net/projects/equalizerapo/)** — Jonas Thedering  
  The system audio engine this UI configures. We only write text configuration; all credit for the APO engine belongs upstream.

- **[Peace GUI](https://sourceforge.net/projects/equalizerapo/)** (distributed with Equalizer APO ecosystem)  
  Historical inspiration for APO config UX. Not redistributed in this repository.

## Measurement communities (data not authored here)

Sample curves may incorporate public measurements and/or targets from:

- oratory1990  
- crinacle  
- Rtings  
- InnerFidelity  
- Super\* Review (squig.link)  
- Kuulokenurkka  
- Auriculares Argentina  
- Headphone.com legacy  
- Harman International research targets (via AutoEq’s public dataset; not an endorsement)

Please support the original reviewers and labs: buy their reviews, follow their terms, and do not present their measurements as your own work.

## Libraries

- [NumPy](https://numpy.org/)  
- [SciPy](https://www.scipy.org/) (optional, precise fitting)

## People

- Everyone who filed issues, shared EQ tips, and documented APO config-path pitfalls in public forums.  
- You, for reading the source and keeping attributions intact when you fork or ship.

---

If you believe your work should be listed here or that attribution is incomplete, please open an issue or pull request — we will fix it promptly.
