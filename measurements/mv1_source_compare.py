# -*- coding: utf-8 -*-
"""MV1 三源对比:oratory / Super Review / Rtings(peq-webui 现有目标)之间的差异"""
import csv, json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

AE = r'F:\MIMO-Space\AutoEq-4.1.2\AutoEq-4.1.2\results'
TGT = r'F:\MIMO-Space\PEQ-WebUI\curves\targets'

def csv_pts(path, col='smoothed'):
    pts = []
    with open(path, 'rb') as f:
        t = f.read().decode('utf-8-sig', errors='replace')
    for row in csv.DictReader(t.splitlines()):
        try: pts.append((float(row['frequency']), float(row[col])))
        except Exception: pass
    pts.sort(); return pts

def json_pts(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

def aligned(pts, lo=500.0, hi=2000.0):
    a = np.array(pts, dtype=float); m = (a[:,0]>=lo)&(a[:,0]<=hi)
    return a[:,0], a[:,1]-a[m,1].mean()

grid = af._log_grid()
seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
lab = ['20-100','100-300','300-1k','1-3k','3-6k','6-9k','9-14k']
def brms(g): return [float(np.sqrt(np.mean(g[(grid>=lo)&(grid<hi)]**2))) for lo,hi in seg]

srcs = {}
fx, fy = aligned(json_pts(os.path.join(TGT, 'sony-mdr-mv1-原始频响.json')))
srcs['Rtings(现有目标)'] = af._interp([(float(f), float(d)) for f,d in zip(fx,fy)], grid)
for key, path in [('oratory', os.path.join(r'F:\MIMO-Space\PEQ-WebUI\measurements\oratory-Sony MDR-MV1\Sony MDR-MV1.csv')),
                  ('Super Review', os.path.join(AE, 'Super Review', 'over-ear', 'Sony MDR-MV1', 'Sony MDR-MV1.csv'))]:
    fx, fy = aligned(csv_pts(path))
    srcs[key] = af._interp([(float(f), float(d)) for f,d in zip(fx,fy)], grid)

print('MV1 三源逐段对比 rms(同一副耳机,差值=纯 rig 差):')
print(f'{"对比":<34} ' + ' '.join(f'{l:>8}' for l in lab))
pairs = [('oratory vs Rtings(现有目标)','oratory','Rtings(现有目标)'),
         ('oratory vs Super Review','oratory','Super Review'),
         ('Rtings vs Super Review','Rtings(现有目标)','Super Review')]
for name, a, b in pairs:
    d = srcs[a]-srcs[b]
    print(f'{name:<34} ' + ' '.join(f'{v:>8.2f}' for v in brms(d)))

print()
print('逐点(oratory vs Rtings):')
d = srcs['oratory'] - srcs['Rtings(现有目标)']
for f in [100,500,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000,11000,12000]:
    k = int(np.argmin(np.abs(grid-f)))
    print(f'  {f:>6}Hz {d[k]:+6.2f}')
