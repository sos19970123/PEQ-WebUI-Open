# -*- coding: utf-8 -*-
"""HD490 预设 9k+ 三段去 rig 修正:
   tilt(f) = R70X_oratory - R70X_rtings  (同一副耳机的 rig 差)
   去 rig 目标 tgt' = tgt_rtings + tilt   (= HD490 若在 oratory rig 上测的样子)
   需要的 EQ = tgt' - dev ; 与现状对比得出三条应改多少"""
import json, re, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
def dp(i):
    return [(x[0], x[1]) for x in json.load(open(os.path.join(BASE, 'curves/devices', i+'.json'), encoding='utf-8-sig'))['points']]
def tp(f):
    return [(x[0], x[1]) for x in json.load(open(os.path.join(BASE, 'curves/targets', f+'.json'), encoding='utf-8-sig'))['points']]
def parse(p):
    txt = open(os.path.join(BASE, 'apo-presets', p), encoding='utf-8-sig').read()
    out = []
    for line in txt.splitlines():
        m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
        if m:
            out.append([m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5)), m.group(1)=='ON'])
    return out
def shape(bs, grid):
    s = np.zeros_like(grid)
    for t, fc, g, q, on in bs:
        if on: s += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    return s

grid = af._log_grid()
dev = af._interp(dp('r70x'), grid)
tgt = af._interp(tp('sennheiser-hd-490-pro-原始频响'), grid)
tilt = dev - af._interp(dp('r70x-rtings'), grid)   # oratory - rtings
tgt_derig = tgt + tilt

bands = parse('1-2.txt')
eq_cur = shape(bands, grid)
need_derig = tgt_derig - dev          # 去 rig 后真正需要的 EQ 形状
need_raw = tgt - dev                  # 未去 rig(原始目标)

print('freq   当前EQ   需要EQ(去rig)  需要EQ(原始)  tilt')
for f in [7000, 8000, 8600, 9200, 9800, 10300, 11000, 12000, 13000]:
    i = np.argmin(np.abs(grid-f))
    print(f'{f:>6} {eq_cur[i]:+7.2f} {need_derig[i]:+12.2f} {need_raw[i]:+12.2f} {tilt[i]:+7.2f}')

print()
seg = [(9000,14000),(6000,9000)]
def rms(g, lo, hi): return float(np.sqrt(np.mean(g[(grid>=lo)&(grid<hi)]**2)))

print('9-14k 区对比:')
print(f'  当前 EQ 幅度 rms        {rms(eq_cur,9000,14000):5.2f}   (rig假差 rms {rms(tilt,9000,14000):5.2f}, mean {np.mean(tilt[(grid>=9000)&(grid<14000)]):+.2f})')
print(f'  去 rig 后需要 EQ rms    {rms(need_derig,9000,14000):5.2f}')
print(f'  未去 rig 需要 EQ rms    {rms(need_raw,9000,14000):5.2f}')

# 三种候选: 现状 / 三段减半 / 三段清零 / 按 need_derig 定值
def variant(label, mods):
    b = [list(x) for x in bands]
    for fc_target, newg in mods.items():
        for x in b:
            if abs(x[1]-fc_target) < 1 and x[0] == 'PK':
                x[2] = newg
    e = shape(b, grid)
    print(f'  {label:34s} vs去rig rms {rms(dev+e-tgt_derig,9000,14000):5.2f} | vs原始目标 rms {rms(dev+e-tgt,9000,14000):5.2f}')
    return b

print()
print('候选方案(9-14k 残差):')
variant('现状 +2.5/+2.5/+0.78', {})
variant('减半 +1.25/+1.25/+0.4', {8593.91:1.25, 9231.54:1.25, 10298.3:0.4})
variant('清零 0/0/0', {8593.91:0.0, 9231.54:0.0, 10298.3:0.0})
variant('按去rig定值 见下表', {8593.91:0.5, 9231.54:0.5, 10298.3:0.5})
variant('-2.9(整段去tilt) 0/0/0 等效', {8593.91:0.0, 9231.54:0.0, 10298.3:0.0})
