# -*- coding: utf-8 -*-
"""用落盘的精确参数复核 A/B 两版残差(验证 note 里的数字)"""
import json, re, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

dev = af._interp(jp(os.path.join(BASE, 'curves/devices/dt900prox.json')), grid)
tgt = af._interp(jp(os.path.join(BASE, 'curves/targets/sony-mdr-mv1-oratory-原始频响.json')), grid)

def parse(p):
    txt = open(os.path.join(BASE, 'apo-presets', p), encoding='utf-8-sig').read()
    bands, pre = [], 0.0
    for line in txt.splitlines():
        m = re.match(r'Preamp:\s*([-\d.]+)', line)
        if m: pre = float(m.group(1))
        m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz Gain ([-+\d.]+) dB Q ([\d.]+)', line)
        if m and m.group(1) == 'ON':
            bands.append((m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5))))
    return bands, pre

def rep(label, fname):
    bands, pre = parse(fname)
    eq = np.zeros_like(grid)
    for t, fc, g, q in bands:
        eq += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    res = dev + eq - tgt          # 形状口径(preamp 只是整体电平,听感上由音量补偿)
    def rr(lo, hi):
        s = res[(grid >= lo) & (grid < hi)]
        return float(np.sqrt(np.mean(s ** 2)))
    print(f'{label}  ({len(bands)}段, preamp {pre})')
    print(f'   形状残差: 100-1k {rr(100,1000):.2f} | 1-3k {rr(1000,3000):.2f} | 3-6k {rr(3000,6000):.2f} | '
          f'6-9k {rr(6000,9000):.2f} | 9-11k {rr(9000,11000):.2f} | 11-14k {rr(11000,14000):.2f} | 全段 {rr(20,20000):.3f}')
    print(f'   关键点残差: 4kHz {res[int(np.argmin(np.abs(grid-4000)))]:+.2f} | '
          f'8kHz {res[int(np.argmin(np.abs(grid-8000)))]:+.2f} | 9.5kHz {res[int(np.argmin(np.abs(grid-9500)))]:+.2f}')

rep('A 版 (sanitize ON, max_q3)', 'dt900-pro-x-mv1拟合.txt')
rep('B 版 (sanitize OFF, max_q4)', 'dt900-pro-x-mv1拟合-b.txt')
