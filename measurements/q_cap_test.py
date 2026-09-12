# -*- coding: utf-8 -*-
"""(1) DT900 4k 谷在 4 个 rig 上是否一致(判断是"耳机固有"还是"位置/个体相关")
   (2) 放开 Q 上限的收益 vs 振铃代价"""
import json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
DEV = os.path.join(BASE, 'curves', 'devices')
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

print('===== (1) 4k 谷的多 rig 一致性 =====')
print(f'{"测量":<26} {"谷底freq":>9} {"谷底dB":>8} {"左峰(3.3k)":>10} {"右峰(5k)":>9} {"落差":>7}')
for name, did in [('oratory GRAS 45BC-10', 'dt900prox'),
                  ('Super Review KB006x+711', 'dt900prox-superreview'),
                  ('Rtings HMS II.3', 'dt900prox-rtings'),
                  ('Kuulokenurkka KB501x+711', 'dt900prox-kuulokenurkka')]:
    try:
        d = af._interp(jp(os.path.join(DEV, did + '.json')), grid)
    except Exception as e:
        print(f'{name}: 缺失 {e}'); continue
    m = (grid >= 3300) & (grid <= 5200)
    g, dd = grid[m], d[m]
    i = int(np.argmin(dd))
    left = float(np.max(d[(grid >= 3200) & (grid <= 3800)]))
    right = float(np.max(d[(grid >= 4600) & (grid <= 5500)]))
    print(f'{name:<26} {g[i]:>9.0f} {dd[i]:>+8.2f} {left:>+10.2f} {right:>+9.2f} {min(right,left)-dd[i]:>7.2f}')

print()
print('===== (2) Q 上限放开:收益 vs 振铃 =====')

def gd_peak_ms(fc, gain, q, sr=48000):
    A = 10.0 ** (gain / 40.0)
    w0 = 2 * np.pi * fc / sr
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2 * q)
    b0, b1, b2 = 1 + alpha * A, -2 * cw, 1 - alpha * A
    a0, a1, a2 = 1 + alpha / A, -2 * cw, 1 - alpha / A
    w = np.logspace(np.log10(100), np.log10(16000), 6000)
    z = np.exp(-1j * 2 * np.pi * w / sr)
    h = (b0 + b1 * z + b2 * z ** 2) / (a0 + a1 * z + a2 * z ** 2)
    ph = np.unwrap(np.angle(h))
    gd = -np.gradient(ph, 2 * np.pi * w / sr) / sr * 1000.0
    return float(gd.max())

dev = af._interp(jp(os.path.join(DEV, 'dt900prox.json')), grid)
tgt = af._interp(jp(os.path.join(BASE, 'curves', 'targets', 'sony-mdr-mv1-oratory-原始频响.json')), grid)

def run(max_q, sanitize, max_gain=6.0):
    r = af.autofit(jp(os.path.join(DEV, 'dt900prox.json')),
                   jp(os.path.join(BASE, 'curves', 'targets', 'sony-mdr-mv1-oratory-原始频响.json')),
                   filters=10, fmin=100.0, fmax=12000.0, max_gain_db=max_gain, max_q=max_q,
                   auto_shelf=False, sanitize=sanitize, smooth_oct=1/12)
    return r

def report(label, r):
    bands = r['bands']
    eq = np.zeros_like(grid)
    for b in bands:
        eq += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
    res = dev + eq - tgt
    def rr(lo, hi):
        s = res[(grid >= lo) & (grid < hi)]
        return float(np.sqrt(np.mean(s ** 2)))
    i4 = int(np.argmin(np.abs(grid - 4000)))
    maxq = max(b['q'] for b in bands)
    band4k = [b for b in bands if 3500 <= b['freq'] <= 5200]
    gd = max((gd_peak_ms(b['freq'], b['gain_db'], b['q']) for b in band4k), default=0.0)
    print(f'{label}')
    print(f'   rms {r["rms_db"]:.3f} | 3-6k {rr(3000,6000):.2f} | 6-9k {rr(6000,9000):.2f} | 4kHz残差 {res[i4]:+.2f}')
    print(f'   最大Q {maxq:.2f} | 4k区段峰值群延迟 {gd:.2f} ms')
    print('   4k 区滤波器: ' + ', '.join(f'{b["freq"]:.0f}Hz{b["gain_db"]:+.1f}Q{b["q"]:.2f}' for b in band4k))

report('现状: max_q=3, sanitize=ON(实际 Q 被钳到 4)', run(3.0, True))
print()
for q in (4.0, 5.0, 6.0, 8.0):
    report(f'max_q={q}, sanitize=OFF', run(q, False))
    print()
