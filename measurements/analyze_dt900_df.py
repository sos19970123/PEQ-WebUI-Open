# -*- coding: utf-8 -*-
"""分析 dt900-pro-x-哈曼校准(扩散场校准)预设:EQ后残余误差 vs diffuse_field 目标"""
import json, re, sys, os
import numpy as np
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'

def load_points(path):
    with open(path, 'rb') as f:
        obj = json.load(f)
    return [(p[0], p[1]) for p in obj['points']]

# 1. 设备原始频响(oratory1990, 500-2k 归零)
dev = load_points(os.path.join(BASE, 'curves', 'devices', 'dt900prox.json'))
# 2. 扩散场目标
tgt = load_points(os.path.join(BASE, 'curves', 'targets', 'diffuse_field_gras_kemar.json'))

# 3. 预设 EQ
preset_path = os.path.join(BASE, 'apo-presets', 'dt900-pro-x-哈曼校准.txt')
with open(preset_path, 'rb') as f:
    txt = f.read().decode('utf-8-sig', errors='replace')
bands = []
preamp = 0.0
for line in txt.splitlines():
    m = re.match(r'Preamp:\s*([-\d.]+)', line)
    if m: preamp = float(m.group(1)); continue
    m = re.match(r'Filter \d+: ON (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
    if m:
        bands.append({'type': m.group(1), 'fc': float(m.group(2)),
                      'gain': float(m.group(3)), 'q': float(m.group(4))})

grid = af._log_grid()
dev_g = af._interp(dev, grid)
tgt_g = af._interp(tgt, grid)
eq_g = np.zeros_like(grid)
for b in bands:
    eq_g += af._rbj_mag_db(grid, b['type'], b['fc'], b['gain'], b['q'])
eq_g += preamp
final_g = dev_g + eq_g
resid = final_g - tgt_g  # EQ 后 vs 目标(正=偏高)

def at(freq):
    i = int(np.argmin(np.abs(grid - freq)))
    return i

print(f'bands={len(bands)} preamp={preamp}')
print(f'{"freq":>7} {"raw":>6} {"EQ":>6} {"final":>6} {"target":>6} {"resid":>6}')
for f in [30,60,100,150,200,250,300,400,500,700,1000,1500,2000,2500,2832,3000,3500,4000,5000,6000,7000,8000,9000,10000,12000]:
    i = at(f)
    print(f'{f:>7} {dev_g[i]:+6.2f} {eq_g[i]:+6.2f} {final_g[i]:+6.2f} {tgt_g[i]:+6.2f} {resid[i]:+6.2f}')

# 分段 RMS 残余(找最没拉平/削过头的区段)
print()
print('segment resid RMS / mean / max / min (EQ后-目标)')
seg = [(20,60),(60,100),(100,200),(200,400),(400,1000),(1000,2000),(2000,3500),(3500,6000),(6000,9000),(9000,14000)]
for lo, hi in seg:
    sel = resid[(grid>=lo)&(grid<hi)]
    print(f'{lo:>5}-{hi:<5}Hz  rms {np.sqrt(np.mean(sel**2)):5.2f}  mean {np.mean(sel):+5.2f}  max {np.max(sel):+5.2f}  min {np.min(sel):+5.2f}')

# 原始 raw 相对 target 需要补多少(不 EQ 前的差距)
print()
print('raw-target 分段 mean (原始频响离扩散场目标多远)')
for lo, hi in seg:
    sel = (dev_g-tgt_g)[(grid>=lo)&(grid<hi)]
    print(f'{lo:>5}-{hi:<5}Hz  mean {np.mean(sel):+5.2f}')
