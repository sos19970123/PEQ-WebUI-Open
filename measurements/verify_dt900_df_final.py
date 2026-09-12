# -*- coding: utf-8 -*-
"""验证最终方案:温和 10 段拟合 + 低频松版(101.6 -3.78 -> -2.2),算残差"""
import json, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

def load(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

dev = load(r'F:\MIMO-Space\PEQ-WebUI\curves\devices\dt900prox.json')
tgt = load(r'F:\MIMO-Space\PEQ-WebUI\curves\targets\diffuse_field_gras_kemar.json')

bands = [
    ('PK', 101.6, -3.78, 0.30),   # 低频: 忠实扩散场(目标低频本就低),保持拟合原样
    ('PK', 334.6, -1.01, 0.82),
    ('PK', 1315.1, +0.26, 0.54),
    ('PK', 2574.5, +4.15, 0.96),
    ('PK', 3438.1, -1.49, 3.00),
    ('PK', 4044.9, +6.00, 3.00),  # 4k 谷温和填(6dB 封顶)
    ('PK', 6239.5, -6.00, 1.96),  # 5-7k 铜管亮主刀
    ('PK', 8636.2, +2.50, 3.00),  # 9-11k 空气感渐次补
    ('PK', 9624.6, +2.50, 3.00),
    ('PK', 10439.4, +2.08, 3.00),
]
PREAMP = -6.55

grid = af._log_grid()
dev_g, tgt_g = af._interp(dev, grid), af._interp(tgt, grid)
shape = np.zeros_like(grid)
for t, fc, g, q in bands:
    shape += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
res = dev_g + shape + PREAMP - tgt_g

print('最终方案残差(含 preamp;均匀偏移由音量补偿):')
for f in [30, 60, 100, 150, 200, 300, 500, 800, 1000, 1500, 2000, 2500, 3000, 3500,
          4000, 4500, 5000, 5500, 6000, 6500, 7000, 8000, 9000, 9500, 10000, 11000, 12000]:
    i = np.argmin(np.abs(grid - f))
    flag = ' ' if abs(res[i]) < 2 else ('~' if abs(res[i]) < 3.5 else '!')
    print(f'{f:>6}Hz {res[i]:+6.2f} {flag}')
seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
print()
print('段 RMS(去 preamp 的纯形状更好看):')
shape_res = dev_g + shape - tgt_g
for lo, hi in seg:
    sel = shape_res[(grid>=lo)&(grid<hi)]
    print(f'{lo:>5}-{hi:<5}Hz rms {np.sqrt(np.mean(sel**2)):.2f} mean {np.mean(sel):+.2f}')
print(f'\n最大形状正增益 {np.max(shape):+.2f} dB, preamp {PREAMP}')
