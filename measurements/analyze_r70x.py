# -*- coding: utf-8 -*-
"""R70X 三视角:原厂 vs 哈曼/扩散场取向;三条预设(HD490PRO/MSR7B/R70XA拟合)形状残差"""
import json, re, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

def load(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

dev = load(r'F:\MIMO-Space\PEQ-WebUI\curves\devices\r70x.json')
grid = af._log_grid()
dev_g = af._interp(dev, grid)

print('======== R70X 原厂取向(500-2k 已归零,同基准可比)========')
for tname, tp in [('harman_overear_2018', r'F:\MIMO-Space\PEQ-WebUI\curves\targets\harman_overear_2018.json'),
                  ('diffuse_field_gras_kemar', r'F:\MIMO-Space\PEQ-WebUI\curves\targets\diffuse_field_gras_kemar.json')]:
    tgt_g = af._interp(load(tp), grid)
    diff = dev_g - tgt_g
    print(f'\n-- 相对 {tname}(正=原厂比目标高)--')
    for f in [30, 60, 100, 150, 200, 300, 500, 800, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 12000]:
        i = np.argmin(np.abs(grid - f))
        print(f'{f:>6}Hz {diff[i]:+6.2f} dB')
    seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
    print('分段 mean:', end=' ')
    for lo, hi in seg:
        sel = diff[(grid>=lo)&(grid<hi)]
        print(f'{lo//1000 if lo>=1000 else lo}-{hi//1000 if hi>=1000 else hi} {np.mean(sel):+5.2f}', end=' | ')
    print()

print('\n======== 三条预设形状残差(去 preamp;正=最终比目标高)========')
presets = [
    ('HD490PRO拟合(调整后)', r'F:\MIMO-Space\PEQ-WebUI\apo-presets\1-2.txt',
     r'F:\MIMO-Space\PEQ-WebUI\curves\targets\sennheiser-hd-490-pro-原始频响.json'),
    ('MSR7B拟合(调整后)', r'F:\MIMO-Space\PEQ-WebUI\apo-presets\1.txt',
     r'F:\MIMO-Space\PEQ-WebUI\curves\targets\audio-technica-ath-msr7b-原始频响.json'),
    ('R70XA拟合', r'F:\MIMO-Space\PEQ-WebUI\apo-presets\r70x-r70xa拟合.txt',
     r'F:\MIMO-Space\PEQ-WebUI\curves\targets\audio-technica-ath-r70xa-原始频响.json'),
]
for name, pp, tp in presets:
    try:
        tgt_g = af._interp(load(tp), grid)
    except Exception as e:
        print(f'{name}: 目标加载失败 {e}'); continue
    txt = open(pp, encoding='utf-8-sig').read()
    bands = []
    for line in txt.splitlines():
        m = re.match(r'Filter \d+: ON (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
        if m:
            bands.append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))))
    shape = np.zeros_like(grid)
    for t, fc, g, q in bands:
        shape += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    res = dev_g + shape - tgt_g
    print(f'\n-- {name} (bands={len(bands)}) --')
    seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
    for lo, hi in seg:
        sel = res[(grid>=lo)&(grid<hi)]
        print(f'{lo:>5}-{hi:<5}Hz  rms {np.sqrt(np.mean(sel**2)):5.2f}  mean {np.mean(sel):+5.2f}')
