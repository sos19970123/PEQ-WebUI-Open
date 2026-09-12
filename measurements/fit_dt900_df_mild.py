# -*- coding: utf-8 -*-
import json, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

def load(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

dev = load(r'F:\MIMO-Space\PEQ-WebUI\curves\devices\dt900prox.json')
tgt = load(r'F:\MIMO-Space\PEQ-WebUI\curves\targets\diffuse_field_gras_kemar.json')

for n in (10, 12):
    r = af.autofit(dev, tgt, filters=n, fmin=100.0, fmax=12000.0,
                   max_gain_db=6.0, max_q=3.0, auto_shelf=False,
                   sanitize=True, smooth_oct=1/12)
    print(f'--- filters={n} rms={r["rms_db"]:.3f} weighted={r["weighted_rms_db"]:.3f} preamp={r["preamp_db"]:.2f} engine={r["engine"]}')
    for b in r['bands']:
        print(f'  {b["type"]} {b["freq"]:8.1f}Hz {b["gain_db"]:+6.2f}dB Q{b["q"]:.2f}')
    print()
