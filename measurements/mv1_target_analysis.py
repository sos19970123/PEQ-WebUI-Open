# -*- coding: utf-8 -*-
"""MV1(oratory)相对 扩散场 DF / 哈曼 / DT900ProX 的取向,判断它的调音目标"""
import json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

mv1 = af._interp(jp(os.path.join(BASE, 'curves/targets/sony-mdr-mv1-oratory-原始频响.json')), grid)
df = af._interp(jp(os.path.join(BASE, 'curves/targets/diffuse_field_gras_kemar.json')), grid)
harman = af._interp(jp(os.path.join(BASE, 'curves/targets/harman_overear_2018.json')), grid)
dt900 = af._interp(jp(os.path.join(BASE, 'curves/devices/dt900prox.json')), grid)

seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
lab = ['20-100','100-300','300-1k','1-3k','3-6k','6-9k','9-14k']

def bandmean(a, b):
    d = a - b
    return [float(np.mean(d[(grid>=lo)&(grid<hi)])) for lo, hi in seg]

print('分段均值(dB):')
print(f'{"对比":<26} ' + ' '.join(f'{l:>8}' for l in lab))
for name, arr in [('MV1 − 扩散场DF', bandmean(mv1, df)),
                  ('MV1 − 哈曼2018', bandmean(mv1, harman)),
                  ('MV1 − DT900ProX', bandmean(mv1, dt900)),
                  ('DT900ProX − 扩散场DF', bandmean(dt900, df))]:
    print(f'{name:<26} ' + ' '.join(f'{v:>+8.2f}' for v in arr))

print()
print('关键频点 MV1 / DF / 哈曼:')
for f in [20,30,60,100,200,500,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000,12000]:
    i = int(np.argmin(np.abs(grid - f)))
    print(f'  {f:>6}Hz  MV1 {mv1[i]:+6.2f} | DF {df[i]:+6.2f} | 哈曼 {harman[i]:+6.2f}')

# 全段与 DF 的吻合度(MV1 是否更接近 DF 而非哈曼?)
def rms(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))
for lo, hi in [(100,1000),(1000,6000),(6000,12000)]:
    m = (grid>=lo)&(grid<hi)
    print(f'\n{lo}-{hi}Hz 形状吻合(越小越像):MV1↔DF {np.sqrt(np.mean((mv1[m]-df[m])**2)):.2f} dB | MV1↔哈曼 {np.sqrt(np.mean((mv1[m]-harman[m])**2)):.2f} | DT900↔DF {np.sqrt(np.mean((dt900[m]-df[m])**2)):.2f} | DT900↔哈曼 {np.sqrt(np.mean((dt900[m]-harman[m])**2)):.2f}')
