# -*- coding: utf-8 -*-
"""DT900->MV1 在 2.5k-12k 的逐点账:需求 / 实际施加 / 残差"""
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

eq = np.zeros_like(grid)
for b in bands:
    eq += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
res = dev + eq - tgt

print(f'{"freq":>7} {"DT900":>7} {"MV1":>7} {"需求":>7} {"施加":>7} {"残差":>7}  {"":<4}')
for f in [2000, 2500, 3000, 3500, 4000, 4500, 5000, 5500, 6000, 6500, 7000, 7500, 8000,
          9000, 10000, 11000, 12000]:
    i = int(np.argmin(np.abs(grid - f)))
    need = tgt[i] - dev[i]
    mark = ''
    if abs(res[i]) > 3:
        mark = '  << 残差大'
    print(f'{f:>7} {dev[i]:>+7.2f} {tgt[i]:>+7.2f} {need:>+7.2f} {eq[i]:>+7.2f} {res[i]:>+7.2f}{mark}')

print()
print('DT900 谷/峰 位置(原厂自身,相对其 500-2k 平均):')
# 找 3-9k 内的极值
seg = (grid >= 3000) & (grid <= 9000)
g, d = grid[seg], dev[seg]
imin = int(np.argmin(d)); imax = int(np.argmax(d))
print(f'  谷底 {g[imin]:.0f}Hz = {d[imin]:+.2f} dB')
print(f'  峰顶 {g[imax]:.0f}Hz = {d[imax]:+.2f} dB')
print(f'  谷峰落差 = {d[imax]-d[imin]:.2f} dB')
print()
print('施加的滤波器(3k 以上):')
for b in bands:
    if b['freq'] >= 3000:
        print(f'  {b["freq"]:>8.1f}Hz {b["gain_db"]:>+6.2f}dB Q{b["q"]:.3f}')
