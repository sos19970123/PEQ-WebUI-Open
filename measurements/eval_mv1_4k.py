# -*- coding: utf-8 -*-
"""评估 4k 谷填充分寸:4045Hz 保持 +6 / +5 / +4 的残差代价"""
import json, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
bands = json.load(open(r'F:\MIMO-Space\PEQ-WebUI\measurements\_mv1_fit.json', encoding='utf-8'))['fit']['bands']
preamp = json.load(open(r'F:\MIMO-Space\PEQ-WebUI\measurements\_mv1_fit.json', encoding='utf-8'))['fit']['preamp_db']

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]
dev = af._interp(jp(BASE + r'\curves\devices\dt900prox.json'), af._log_grid())
tgt = af._interp(jp(BASE + r'\curves\targets\sony-mdr-mv1-oratory-原始频响.json'), af._log_grid())
grid = af._log_grid()

def shape(bs):
    s = np.zeros_like(grid)
    for b in bs:
        s += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
    return s

def ev(label, bs):
    s = shape(bs)
    res = dev + s - tgt
    seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
    out = []
    for lo, hi in seg:
        sel = res[(grid>=lo)&(grid<hi)]
        out.append(f'{lo//1000 if lo>=1000 else lo}-{hi//1000 if hi>=1000 else hi}k {np.sqrt(np.mean(sel**2)):.2f}')
    i4 = int(np.argmin(np.abs(grid-4000)))
    print(f'{label:26s} 全段rms {np.sqrt(np.mean(res**2)):.3f} | ' + ' | '.join(out))
    print(f'{"":26s} 4kHz处残差 {res[i4]:+.2f} | 形状最大正增益 {s.max():+.2f}')

ev('A: 4045Hz +6.0(原样)', [dict(b) for b in bands])
b5 = [dict(b) for b in bands]
for b in b5:
    if abs(b['freq']-4044.94) < 1: b['gain_db'] = 5.0
ev('B: 4045Hz +5.0', b5)
b4 = [dict(b) for b in bands]
for b in b4:
    if abs(b['freq']-4044.94) < 1: b['gain_db'] = 4.0
ev('C: 4045Hz +4.0', b4)

print()
print(f'原拟合 preamp = {preamp} (形状最大正增益决定)')
for lbl, bs in [('A', bands), ('B', b5), ('C', b4)]:
    s = shape(bs)
    print(f'  {lbl}: max{s.max():+.2f} -> 建议 preamp {-(s.max()+0.8):.2f}')
