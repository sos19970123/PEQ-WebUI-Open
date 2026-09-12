# -*- coding: utf-8 -*-
"""LS 中心频率扫描:Fc 40~80 @Q0.707,找最贴合残留缺口且零中频泄漏的点"""
import json, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

dev = af._interp(jp(BASE + r'\curves\devices\dt900prox.json'), grid)
tgt = af._interp(jp(BASE + r'\curves\targets\sony-mdr-mv1-oratory-原始频响.json'), grid)
bands = json.load(open(r'F:\MIMO-Space\PEQ-WebUI\measurements\_mv1_fit.json', encoding='utf-8'))['fit']['bands']

def shape(bs, extra=None):
    s = np.zeros_like(grid)
    for b in bs:
        s += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
    if extra:
        s += af._rbj_mag_db(grid, 'LS', extra[0], extra[1], 0.707, sr=48000)
    return s

def at(f, arr):
    return float(arr[int(np.argmin(np.abs(grid - f)))])

print('=== 残留缺口(现有 10 段之后,单位 dB,正=还差多少要补)===')
s0 = shape(bands)
res = dev + s0 - tgt
for f in [20, 25, 30, 40, 50, 60, 70, 80, 100, 150, 200, 300]:
    print(f'  {f:>4}Hz {res[int(np.argmin(np.abs(grid-f)))]:+6.2f}')

print()
print('=== Fc 扫描 @Q0.707(看各段残差 rms,越小越好)===')
hdr = f'{"Fc":>4} {"gain":>5} ' + ' '.join(f'{l:>9}' for l in ['20-60','60-100','100-300','300-1k','200Hz处'])
print(hdr)
for fc in (40, 50, 60, 70, 80):
    for g in (2.0, 2.5, 3.0):
        s = shape(bands, (float(fc), g))
        r = dev + s - tgt
        vals = []
        for lo, hi in [(20,60),(60,100),(100,300),(300,1000)]:
            sel = r[(grid>=lo)&(grid<hi)]
            vals.append(f'{np.sqrt(np.mean(sel**2)):>9.2f}')
        ls_self = af._rbj_mag_db(grid, 'LS', float(fc), g, 0.707, sr=48000)
        vals.append(f'{at(200, ls_self):>+9.2f}')
        print(f'{fc:>4} {g:>5} ' + ' '.join(vals))
    print()
