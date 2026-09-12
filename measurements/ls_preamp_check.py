# -*- coding: utf-8 -*-
"""加 LS 后的形状峰值 -> preamp 建议"""
import json, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

grid = af._log_grid()
bands = json.load(open(r'F:\MIMO-Space\PEQ-WebUI\measurements\_mv1_fit.json', encoding='utf-8'))['fit']['bands']

def shape(extra=None):
    s = np.zeros_like(grid)
    for b in bands:
        s += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
    if extra:
        s += af._rbj_mag_db(grid, 'LS', extra[0], extra[1], 0.707, sr=48000)
    return s

def at(f, arr):
    return float(arr[int(np.argmin(np.abs(grid - f)))])

for label, ex in [('现状(10段, 无LS)', None), ('+ LS 60Hz +3.0 Q0.707', (60.0, 3.0)),
                  ('+ LS 60Hz +2.5 Q0.707', (60.0, 2.5)), ('+ LS 40Hz +3.0 Q0.707', (40.0, 3.0))]:
    s = shape(ex)
    i = int(np.argmax(s))
    print(f'{label:26s} 峰值 {s.max():+.2f}dB @{grid[i]:.0f}Hz  ->  preamp 建议 {-(s.max()+0.2):.2f} dB')
    print(f'{"":26s} 60Hz {at(60,s):+.2f} | 100Hz {at(100,s):+.2f} | 3-6k 峰值 {s[(grid>=3000)&(grid<6000)].max():+.2f}')
