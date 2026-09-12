# -*- coding: utf-8 -*-
"""API 等价设置下的 Q/sanitize 对照 + 手工"半放开"候选"""
import json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

depp = jp(os.path.join(BASE, 'curves', 'devices', 'dt900prox.json'))
tgp = jp(os.path.join(BASE, 'curves', 'targets', 'sony-mdr-mv1-oratory-原始频响.json'))
dev = af._interp(depp, grid)
tgt = af._interp(tgp, grid)

# API 等价:min_mean_error=False(category=headphone), sharpness_penalty=True(默认), smooth 1/12
def run(max_q, sanitize, max_gain=6.0):
    return af.autofit(depp, tgp, filters=10, fmin=100.0, fmax=12000.0, max_gain_db=max_gain,
                      max_q=max_q, auto_shelf=False, sanitize=sanitize, smooth_oct=1/12,
                      min_mean_error=False, sharpness_penalty=True)

def gd_peak_ms(fc, gain, q, sr=48000):
    A = 10.0 ** (gain / 40.0); w0 = 2 * np.pi * fc / sr
    cw, sw = np.cos(w0), np.sin(w0); alpha = sw / (2 * q)
    b0, b1, b2 = 1 + alpha * A, -2 * cw, 1 - alpha * A
    a0, a1, a2 = 1 + alpha / A, -2 * cw, 1 - alpha / A
    w = np.logspace(np.log10(100), np.log10(16000), 6000)
    z = np.exp(-1j * 2 * np.pi * w / sr)
    h = (b0 + b1 * z + b2 * z ** 2) / (a0 + a1 * z + a2 * z ** 2)
    gd = -np.gradient(np.unwrap(np.angle(h)), 2 * np.pi * w / sr) / sr * 1000.0
    return float(gd.max())

def report(label, bands):
    eq = np.zeros_like(grid)
    for b in bands:
        eq += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
    res = dev + eq - tgt
    def rr(lo, hi):
        s = res[(grid >= lo) & (grid < hi)]
        return float(np.sqrt(np.mean(s ** 2)))
    b4 = [b for b in bands if 3500 <= b['freq'] <= 5200]
    gd = max((gd_peak_ms(b['freq'], b['gain_db'], b['q']) for b in b4), default=0.0)
    print(f'{label}')
    print(f'   rms {rr(20,20000):.3f} | 3-6k {rr(3000,6000):.2f} | 6-9k {rr(6000,9000):.2f} | 9-14k {rr(9000,14000):.2f} | 4k残差 {res[int(np.argmin(np.abs(grid-4000)))]:+.2f} | 8k残差 {res[int(np.argmin(np.abs(grid-8000)))]:+.2f}')
    print(f'   最大Q {max(b["q"] for b in bands):.2f} | 4k区群延迟 {gd:.2f} ms | 最大正增益 {max(b["gain_db"] for b in bands):+.1f}')
    print('   ', ', '.join(f'{b["freq"]:.0f}Hz{b["gain_db"]:+.1f}Q{b["q"]:.2f}' for b in bands))

print('== 基线(与实际预设同设置) ==')
b_api = run(3.0, True)
report('max_q=3 + sanitize=ON', b_api['bands'])
print()
print('== 放开测试 ==')
for q, san in [(4.0, False), (6.0, False)]:
    r = run(q, san)
    report(f'max_q={q} + sanitize=OFF', r['bands'])
    print()

# 半放开手工候选:取 max_q=4/sanitize OFF 的结果,把 >8k 正增益压到 <=6dB
r4 = run(4.0, False)
print('== 手工"半放开"候选:同 max_q=4 但 >8k 正增益钳到 6dB ==')
b_manual = []
for b in r4['bands']:
    nb = dict(b)
    if nb['freq'] > 8000 and nb['gain_db'] > 6.0:
        nb['gain_db'] = 6.0
    b_manual.append(nb)
report('max_q=4 + HF 正增益钳 6dB', b_manual)
