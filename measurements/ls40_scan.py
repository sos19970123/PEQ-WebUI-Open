# -*- coding: utf-8 -*-
"""LS 40Hz 加多少增益/Q 才不会影响中频:扫描 gain × Q,看各频点实际增益与中频泄漏"""
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
        s += af._rbj_mag_db(grid, extra[0], extra[1], extra[2], extra[3], sr=48000)
    return s

def at(f, arr):
    return float(arr[int(np.argmin(np.abs(grid - f)))])

freqs = [20, 30, 40, 60, 80, 100, 150, 200, 300, 500, 1000]
print('LS Fc40 各 Q/增益的实际频响(只看这一段的贡献,不算已有 10 段):')
print(f'{"Q":>5} {"gain":>5} ' + ' '.join(f'{f:>6}' for f in freqs))
for q in (0.5, 0.707, 1.0, 1.5):
    for g in (2.0, 2.5, 3.0):
        arr = af._rbj_mag_db(grid, 'LS', 40.0, g, q, sr=48000)
        print(f'{q:>5} {g:>5} ' + ' '.join(f'{at(f, arr):>+6.2f}' for f in freqs))
    print()

print('=== 选定候选对"整体残差"的影响(需考虑已有 10 段) ===')
def resid(label, extra):
    s = shape(bands, extra)
    res = dev + s - tgt
    out = []
    for lo, hi in [(20,60),(60,100),(100,300),(300,1000),(1000,3000)]:
        sel = res[(grid>=lo)&(grid<hi)]
        out.append(f'{lo}-{hi}Hz {np.sqrt(np.mean(sel**2)):.2f}')
    print(f'{label:28s} ' + ' | '.join(out))

resid('现状(不加 LS)', None)
for q in (0.707, 1.0):
    for g in (2.0, 2.5, 3.0):
        resid(f'LS 40Hz {g:+.1f}dB Q{q}', ('LS', 40.0, g, q))

print()
print('=== 中频泄漏自查:LS 对 200/300/500/1k 的影响幅度 ===')
for q in (0.5, 0.707, 1.0, 1.5, 2.0):
    arr = af._rbj_mag_db(grid, 'LS', 40.0, 3.0, q, sr=48000)
    print(f'  Q{q:<5} @200Hz {at(200,arr):+.2f} | @300Hz {at(300,arr):+.2f} | @500Hz {at(500,arr):+.2f} | @1kHz {at(1000,arr):+.2f}')
