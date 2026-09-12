# -*- coding: utf-8 -*-
"""分析 dt900prox-harman(乐园2拟合)预设:形状残差 vs Para II 原始频响目标"""
import json, re, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

def load(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

dev = load(r'F:\MIMO-Space\PEQ-WebUI\curves\devices\dt900prox.json')
tgt = load(r'F:\MIMO-Space\PEQ-WebUI\curves\targets\moondrop-para-ii-原始频响.json')
txt = open(r'F:\MIMO-Space\PEQ-WebUI\apo-presets\dt900prox-harman.txt', encoding='utf-8-sig').read()

bands = []
for line in txt.splitlines():
    m = re.match(r'Filter \d+: ON (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
    if m:
        bands.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))))

grid = af._log_grid()
dev_g, tgt_g = af._interp(dev, grid), af._interp(tgt, grid)
shape = np.zeros_like(grid)
for t, fc, g, q in bands:
    shape += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
res = dev_g + shape - tgt_g   # 形状残差(无 preamp)

print(f'bands={len(bands)}  源 DT900(oratory) -> 目标 Para II')
print(f'{"freq":>7} {"raw":>6} {"EQ":>6} {"final":>6} {"target":>6} {"resid":>6}')
for f in [30, 60, 100, 150, 200, 300, 500, 800, 1000, 1500, 2000, 2500, 3000, 3500,
          4000, 4500, 5000, 5500, 6000, 6500, 7000, 8000, 9000, 10000, 11000, 12000]:
    i = np.argmin(np.abs(grid - f))
    print(f'{f:>7} {dev_g[i]:+6.2f} {shape[i]:+6.2f} {dev_g[i]+shape[i]:+6.2f} {tgt_g[i]:+6.2f} {res[i]:+6.2f}')

seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
print()
print('段形状残差 RMS / mean:')
for lo, hi in seg:
    sel = res[(grid>=lo)&(grid<hi)]
    print(f'{lo:>5}-{hi:<5}Hz  rms {np.sqrt(np.mean(sel**2)):5.2f}  mean {np.mean(sel):+5.2f}')
