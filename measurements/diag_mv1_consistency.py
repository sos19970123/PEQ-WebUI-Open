# -*- coding: utf-8 -*-
"""诊断:目标文件/设备文件/CSV 原值 在关键频点上是否一致"""
import json, csv, numpy as np

def jp(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return np.array(o['points'])

BASE = r'F:\MIMO-Space\PEQ-WebUI'
tgt = jp(BASE + r'\curves\targets\sony-mdr-mv1-oratory-原始频响.json')
dev = jp(BASE + r'\curves\devices\dt900prox.json')

rows = {}
t = open(r'F:\MIMO-Space\PEQ-WebUI\measurements\oratory-Sony MDR-MV1\Sony MDR-MV1.csv',
         'rb').read().decode('utf-8-sig', errors='replace')
for col in ('raw', 'smoothed'):
    pts = []
    for r in csv.DictReader(t.splitlines()):
        try:
            pts.append((float(r['frequency']), float(r[col])))
        except Exception:
            pass
    rows[col] = np.array(sorted(pts))

def at(a, f):
    i = int(np.argmin(np.abs(a[:, 0] - f)))
    return a[i, 1]

print('freq     tgt文件    CSVraw    CSVsmoothed   dev文件')
for f in [100, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 12000]:
    print(f'{f:>6} {at(tgt,f):+9.2f} {at(rows["raw"],f):+9.2f} {at(rows["smoothed"],f):+12.2f} {at(dev,f):+9.2f}')

print()
print('tgt   500-2k mean', round(float(tgt[(tgt[:,0]>=500)&(tgt[:,0]<=2000),1].mean()), 3))
print('dev   500-2k mean', round(float(dev[(dev[:,0]>=500)&(dev[:,0]<=2000),1].mean()), 3))
r0 = rows['raw']
print('CSVraw 500-2k mean', round(float(r0[(r0[:,0]>=500)&(r0[:,0]<=2000),1].mean()), 3))
print('点数 tgt/dev/csvraw:', len(tgt), len(dev), len(r0))
