# -*- coding: utf-8 -*-
"""候选 B(放开 sanitize,原样) vs 候选 C(删掉 >10k 的 +3.2) —— 看 9-14k 代价"""
import json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

depp = jp(os.path.join(BASE, 'curves', 'devices', 'dt900prox.json'))
tgp = jp(os.path.join(BASE, 'curves', 'targets', 'sony-mdr-mv1-oratory-原始频响.json'))
dev, tgt = af._interp(depp, grid), af._interp(tgp, grid)

A = [('PK',102,2.6,0.39),('PK',1404,1.7,1.93),('PK',2218,-3.2,1.04),('PK',2731,3.2,3.0),
     ('PK',4045,6.0,3.0),('PK',4759,-5.9,3.0),('PK',5910,2.6,3.0),('PK',8181,2.5,2.31),
     ('PK',9755,2.5,3.0),('PK',11634,-4.3,1.30)]
B = [('PK',102,2.7,0.43),('PK',1376,1.1,2.61),('PK',2083,-2.3,1.53),('PK',2792,2.1,3.23),
     ('PK',4045,4.8,4.0),('PK',4759,-5.1,3.6),('PK',5910,1.5,4.0),('PK',8181,4.2,2.29),
     ('PK',11186,3.2,0.90),('PK',11634,-6.0,2.58)]
C = [b for b in B if b[1] != 11186]          # 删掉 >10k 的 +3.2
D = [b for b in B if b[1] != 11186] + [('PK',10439,2.5,3.0)]   # 换成 10.4k 的温和补层

def rep(label, bands):
    eq = np.zeros_like(grid)
    for t, fc, g, q in bands:
        eq += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    res = dev + eq - tgt
    def rr(lo, hi):
        s = res[(grid >= lo) & (grid < hi)]
        return float(np.sqrt(np.mean(s ** 2)))
    print(f'{label}')
    print(f'   rms {rr(20,20000):.3f} | 100-1k {rr(100,1000):.2f} | 1-3k {rr(1000,3000):.2f} | 3-6k {rr(3000,6000):.2f} | 6-9k {rr(6000,9000):.2f} | 9-11k {rr(9000,11000):.2f} | 11-14k {rr(11000,14000):.2f}')
    print(f'   最大正增益 {max(g for _,_,g,_ in bands):+.1f}')
    print('   ', ', '.join(f'{fc:.0f}Hz{g:+.1f}Q{q:.2f}' for _, fc, g, q in bands))

rep('A 现状(预设原样)', A)
rep('B 放开 sanitize(max_q4)', B)
rep('C = B 删掉 11.2k+3.2', C)
rep('D = B 换成 10.4k+2.5', D)
