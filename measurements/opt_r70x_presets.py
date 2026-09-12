# -*- coding: utf-8 -*-
"""验证 R70X 三条预设的可优化点"""
import json, re, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

def load(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

grid = af._log_grid()
dev_g = af._interp(load(r'F:\MIMO-Space\PEQ-WebUI\curves\devices\r70x.json'), grid)
seg = [(1000,3000),(20,100),(6000,14000),(9000,14000)]

def parse(path):
    txt = open(path, encoding='utf-8-sig').read()
    bands = []
    for line in txt.splitlines():
        m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
        if m:
            bands.append([m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5)), m.group(1) == 'ON'])
    return bands

def shape_of(bands):
    s = np.zeros_like(grid)
    for t, fc, g, q, on in bands:
        if on:
            s += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    return s

def report(label, res):
    out = []
    for lo, hi in seg:
        sel = res[(grid>=lo)&(grid<hi)]
        out.append(f'{lo//1000 if lo>=1000 else lo}-{hi//1000 if hi>=1000 else hi}k rms {np.sqrt(np.mean(sel**2)):.2f}')
    print(f'{label}: ' + ' | '.join(out))

# --- HD490PRO ---
hp = parse(r'F:\MIMO-Space\PEQ-WebUI\apo-presets\1-2.txt')
tgt = af._interp(load(r'F:\MIMO-Space\PEQ-WebUI\curves\targets\sennheiser-hd-490-pro-原始频响.json'), grid)
print('== HD490PRO 拟合 ==')
base = shape_of(hp)
report('现状(Filter7 OFF)', dev_g + base - tgt)
# 试探: 打开 Filter 7
alt = [list(b) for b in hp]
for b in alt:
    if abs(b[1] - 1843.89) < 1: b[4] = True
report('若打开 Filter7(-3.38@1844Q1.9)', dev_g + shape_of(alt) - tgt)
# 试探: Filter 7 半开(-1.7)
alt2 = [list(b) for b in hp]
for b in alt2:
    if abs(b[1] - 1843.89) < 1: b[2] = -1.7; b[4] = True
report('若 Filter7 改 -1.7', dev_g + shape_of(alt2) - tgt)
print('  (Filter7 当前 OFF -> 1-3k 偏高 +1.77)')

# --- MSR7B ---
ms = parse(r'F:\MIMO-Space\PEQ-WebUI\apo-presets\1.txt')
tgt2 = af._interp(load(r'F:\MIMO-Space\PEQ-WebUI\curves\targets\audio-technica-ath-msr7b-原始频响.json'), grid)
print('\n== MSR7B 拟合 ==')
report('现状', dev_g + shape_of(ms) - tgt2)
# 低频: 加 LS 35Hz
altm = [list(b) for b in ms] + [['LS', 40.0, 3.0, 0.7, True]]
report('若加 LS 40Hz +3.0', dev_g + shape_of(altm) - tgt2)
# 高频: 弱化 9973 -10.91 与 10160 +7 对消
altm2 = [list(b) for b in ms]
for b in altm2:
    if abs(b[1]-9973.99) < 1: b[2] = -6.0
    if abs(b[1]-10160.4) < 1: b[2] = 5.0
report('若 9973:-10.91->-6, 10160:+7->+5', dev_g + shape_of(altm2) - tgt2)

# --- R70XA ---
rx = parse(r'F:\MIMO-Space\PEQ-WebUI\apo-presets\r70x-r70xa拟合.txt')
tgt3 = af._interp(load(r'F:\MIMO-Space\PEQ-WebUI\curves\targets\audio-technica-ath-r70xa-原始频响.json'), grid)
print('\n== R70XA 拟合 ==')
report('现状', dev_g + shape_of(rx) - tgt3)
# 原始 R70X vs R70xa 差距(不 EQ)
report('原厂不EQ(raw vs R70xa目标)', dev_g - tgt3)
