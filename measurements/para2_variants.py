# -*- coding: utf-8 -*-
"""乐园2 追加段:三组理性候选对比(避免相邻 boost/cut 大对消)"""
import json, re, os, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
PRE = os.path.join(BASE, 'apo-presets')
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

txt = open(os.path.join(PRE, 'dt900prox-harman.txt'), encoding='utf-8-sig').read()
cur = []
for lm in [l.strip() for l in txt.splitlines()]:
    m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz(?: Gain ([-+\d.]+) dB)? Q ([\d.]+)', lm)
    if m and m.group(1) == 'ON':
        cur.append((m.group(2), float(m.group(3)), float(m.group(4)) if m.group(4) else 0.0, float(m.group(5))))

d = af._interp(jp(os.path.join(BASE, 'curves/devices/dt900prox.json')), grid)
t = af._interp(jp(os.path.join(BASE, 'curves/targets/moondrop-para-ii-原始频响.json')), grid)

def shape(bs):
    s = np.zeros_like(grid)
    for tp, fc, g, q in bs:
        s += af._rbj_mag_db(grid, tp, fc, g, q, sr=48000)
    return s

SEG = [(20,100),(100,400),(400,2000),(2000,6000),(6000,9000),(9000,14000)]
LAB = ['20-100','100-400','400-2k','2-6k','6-9k','9-14k']
def show(label, res, bs):
    r = [float(np.sqrt(np.mean(res[(grid >= lo) & (grid < hi)] ** 2))) for lo, hi in SEG]
    s = shape(bs); i = int(np.argmax(s))
    print(f'{label:<34} ' + ' '.join(f'{l} {v:5.2f}' for l, v in zip(LAB, r)))
    print(f'{"":34} 峰值 {s.max():+.2f}dB@{grid[i]:.0f}Hz -> preamp {-(s.max()+0.2):.2f}')

show('现状(10段, preamp -2.06)', d + shape(cur) - t, cur)

V1 = cur + [('PK',3500.0,-3.0,2.5), ('PK',4050.0,3.0,3.5), ('PK',5300.0,-5.0,1.5), ('PK',6200.0,-5.0,1.6)]
V2 = cur + [('PK',3500.0,-3.0,2.5), ('PK',4050.0,3.0,3.5), ('PK',5600.0,-7.0,1.1), ('PK',6800.0,-3.0,2.5)]
V3 = cur + [('PK',3500.0,-3.0,2.5), ('PK',4050.0,2.5,3.5), ('PK',5400.0,-6.0,1.3), ('PK',6300.0,-6.0,1.5), ('PK',7000.0,-3.0,2.5)]
for nm, bs in [('V1(双削 5300/6200)', V1), ('V2(宽削 5600+尾 6800)', V2), ('V3(双削+4k轻填)', V3)]:
    print()
    show(nm, d + shape(bs) - t, bs)
    print('   追加段: ' + ', '.join(f'{fc:.0f}Hz{g:+.1f}Q{q}' for tp, fc, g, q in bs[len(cur):]))
