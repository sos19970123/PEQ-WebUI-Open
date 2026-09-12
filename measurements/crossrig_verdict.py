# -*- coding: utf-8 -*-
"""决定性对比:每条跨rig预设,逐频段列出
   A. 原始差距(设备 vs 目标,不EQ)= 拟合要处理的总量
   B. rig 差异包络(同一副耳机在两 rig 上的实测差)= 其中不可信的"假差"
   若 |A| 与 B 同量级 -> 该频段的拟合是在追 rig 特征(陷阱)"""
import json, re, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

DEV = r'F:\MIMO-Space\PEQ-WebUI\curves\devices'
TGT = r'F:\MIMO-Space\PEQ-WebUI\curves\targets'
PRE = r'F:\MIMO-Space\PEQ-WebUI\apo-presets'

def dev_pts(i):
    return [(x[0], x[1]) for x in json.load(open(os.path.join(DEV, i+'.json'), encoding='utf-8-sig'))['points']]
def tgt_pts(f):
    return [(x[0], x[1]) for x in json.load(open(os.path.join(TGT, f + '.json'), encoding='utf-8-sig'))['points']]
def parse(p):
    txt = open(os.path.join(PRE, p), encoding='utf-8-sig').read()
    out = []
    for line in txt.splitlines():
        m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
        if m and m.group(1) == 'ON':
            out.append((m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5))))
    return out
def shape(bs, grid):
    s = np.zeros_like(grid)
    for t, fc, g, q in bs:
        s += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    return s

grid = af._log_grid()
seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
lab = ['20-100','100-300','300-1k','1-3k','3-6k','6-9k','9-14k']

def band_rms(g):
    return [float(np.sqrt(np.mean(g[(grid>=lo)&(grid<hi)]**2))) for lo, hi in seg]

# --- 乐园2: DT900(oratory GRAS) -> Para II(Super Review KB006x+711) ---
d = af._interp(dev_pts('dt900prox'), grid)
t = af._interp(tgt_pts('moondrop-para-ii-原始频响'), grid)
eq = shape(parse('dt900prox-harman.txt'), grid)
raw_gap = band_rms(d - t)
resid = band_rms(d + eq - t)
# rig 包络: DT900 oratory vs superreview 实测差
r = band_rms(d - af._interp(dev_pts('dt900prox-superreview'), grid))

print('===== 乐园2拟合: DT900(oratory) -> Para II(Super Review) =====')
print(f'{"band":>8} {"原始差距A":>10} {"EQ修正":>9} {"残差":>8} {"rig假差B":>10} {"判定":>10}')
for i, l in enumerate(lab):
    v = '⚠️追假差' if raw_gap[i] < r[i]*1.3 and abs(raw_gap[i]) > 1.5 else ('可信' if abs(raw_gap[i]) > r[i]*2 else '—')
    print(f'{l:>8} {raw_gap[i]:>10.2f} {band_rms(eq)[i]:>9.2f} {resid[i]:>8.2f} {r[i]:>10.2f} {v:>10}')

# --- HD490PRO: R70X(oratory GRAS) -> HD490 Pro(Rtings) ---
d2 = af._interp(dev_pts('r70x'), grid)
t2 = af._interp(tgt_pts('sennheiser-hd-490-pro-原始频响'), grid)
eq2 = shape(parse('1-2.txt'), grid)
raw2 = band_rms(d2 - t2)
res2 = band_rms(d2 + eq2 - t2)
rig2 = band_rms(d2 - af._interp(dev_pts('r70x-rtings'), grid))

print()
print('===== HD490PRO拟合: R70X(oratory) -> HD490 Pro(Rtings) =====')
print(f'{"band":>8} {"原始差距A":>10} {"EQ修正":>9} {"残差":>8} {"rig假差B":>10} {"判定":>10}')
for i, l in enumerate(lab):
    v = '⚠️追假差' if raw2[i] < rig2[i]*1.3 and abs(raw2[i]) > 1.5 else ('可信' if abs(raw2[i]) > rig2[i]*2 else '—')
    print(f'{l:>8} {raw2[i]:>10.2f} {band_rms(eq2)[i]:>9.2f} {res2[i]:>8.2f} {rig2[i]:>10.2f} {v:>10}')

# --- 参照: R70XA 同 rig ---
d3 = af._interp(dev_pts('r70x'), grid)
t3 = af._interp(tgt_pts('audio-technica-ath-r70xa-原始频响'), grid)
raw3 = band_rms(d3 - t3)
print()
print('===== 参照 R70XA拟合(同 rig oratory↔oratory)=====')
print(f'{"band":>8} {"原始差距A":>10} {"rig假差B":>10}   (B≈0 表示无跨rig问题)')
for i, l in enumerate(lab):
    print(f'{l:>8} {raw3[i]:>10.2f} {"~0(同rig)":>10}')
