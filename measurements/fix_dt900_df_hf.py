# -*- coding: utf-8 -*-
"""手动克制档候选验证:固定低频骨架(LS -2.0),3.5k+ 补刀用手动增益,算残差对比"""
import json, re, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
def load(p):
    o = json.load(open(os.path.join(BASE, p), encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

dev = load('curves/devices/dt900prox.json')
tgt = load('curves/targets/diffuse_field_gras_kemar.json')
txt = open(os.path.join(BASE, 'apo-presets', 'dt900-pro-x-哈曼校准.txt'), encoding='utf-8-sig').read()

fixed = []
for line in txt.splitlines():
    m = re.match(r'Filter \d+: ON (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
    if m:
        fixed.append([m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))])
for b in fixed:
    if b[0] == 'LS':
        b[2] = -2.0

grid = af._log_grid()
dev_g, tgt_g = af._interp(dev, grid), af._interp(tgt, grid)
shape_fixed = np.zeros_like(grid)
for t, fc, g, q in fixed:
    shape_fixed += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)

def evaluate(label, adds):
    shape = shape_fixed.copy()
    for t, fc, g, q in adds:
        shape += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    res = dev_g + shape - tgt_g
    print(f'== {label} ==')
    for f in [3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 8000, 9000, 9500, 10000, 11000]:
        i = np.argmin(np.abs(grid - f))
        flag = ' ' if abs(res[i]) < 2.5 else '⚠️'
        print(f'{f:>6}Hz {res[i]:+6.2f} {flag}')
    seg = [(3500,6000),(6000,9000),(9000,14000)]
    print('  段RMS:', end=' ')
    for lo, hi in seg:
        sel = res[(grid>=lo)&(grid<hi)]
        print(f'{lo//1000}k-{hi//1000}k {np.sqrt(np.mean(sel**2)):.2f}', end='  ')
    print(f'\n  preamp 建议: {-(np.max(np.maximum(shape,0))+1):.1f} dB\n')

# 组 B: 克制档
evaluate('组B: 4k+4.0 Q3.5 / 5.1k-1.5 / 6.1k-5.0 Q1.8 / 9.75k+3.5 Q2.5', [
    ('PK', 4050, 4.0, 3.5), ('PK', 5100, -1.5, 2.2), ('PK', 6100, -5.0, 1.8), ('PK', 9750, 3.5, 2.5),
])
# 组 D: 务实听感档——4k 填到不山洞,5-7k 压平,9-10k 只轻提(接受残余,不强追曲线)
evaluate('组D: 4k+5.5 Q3.5 / 5.1k-1.2 / 6.1k-5.0 Q1.8 / 9.7k+3.0 Q2.0', [
    ('PK', 4050, 5.5, 3.5), ('PK', 5100, -1.2, 2.2), ('PK', 6100, -5.0, 1.8), ('PK', 9700, 3.0, 2.0),
])
# 组 E: 4k 再加强,5.6k 双峰压(参考 4k 谷窄而深)
evaluate('组E: 4k+6.0 Q4.0 / 5.6k-2.5 Q3.0 / 6.3k-5.0 Q1.6 / 9.7k+2.5 Q2.5', [
    ('PK', 4050, 6.0, 4.0), ('PK', 5600, -2.5, 3.0), ('PK', 6300, -5.0, 1.6), ('PK', 9700, 2.5, 2.5),
])
