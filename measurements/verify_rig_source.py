# -*- coding: utf-8 -*-
"""坐实:导入的 HD490 Pro / Para II 目标曲线,到底来自哪个 rig(与本地 AutoEq 各候选比对)"""
import csv, json, glob, os
import numpy as np

AE = r'F:\MIMO-Space\AutoEq-4.1.2\AutoEq-4.1.2\results'
PEQ = r'F:\MIMO-Space\PEQ-WebUI\curves\targets'

def load_json_points(p):
    o = json.load(open(p, encoding='utf-8-sig'))
    return [(x[0], x[1]) for x in o['points']]

def load_csv_raw(path):
    pts = []
    with open(path, 'rb') as f:
        t = f.read().decode('utf-8-sig', errors='replace')
    for row in csv.DictReader(t.splitlines()):
        try:
            pts.append((float(row['frequency']), float(row['raw'])))
        except Exception:
            pass
    pts.sort()
    return pts

def align(pts, lo=500.0, hi=2000.0):
    a = np.array(pts, dtype=float)
    m = (a[:, 0] >= lo) & (a[:, 0] <= hi)
    return a[:, 0], a[:, 1] - a[m, 1].mean()

def rms_vs(target_pts, cand_pts):
    tx, ty = align(target_pts)
    cx, cy = align(cand_pts)
    cyi = np.interp(np.log(np.clip(tx, 20, 20000)), np.log(np.clip(cx, 20, 20000)), cy)
    d = ty - cyi
    return float(np.sqrt(np.mean(d ** 2)))

print('===== HD490 Pro: 导入目标 vs 本地各候选 =====')
tgt = load_json_points(os.path.join(PEQ, 'sennheiser-hd-490-pro-原始频响.json'))
cands = []
for pat in ['Rtings/over-ear/*490*/**/*.csv', 'Super Review/over-ear/*490*/**/*.csv']:
    cands += glob.glob(os.path.join(AE, pat), recursive=True)
# 也扫一层
for root, dirs, files in os.walk(os.path.join(AE, 'Rtings')):
    for f in files:
        if '490' in f and f.endswith('.csv'): cands.append(os.path.join(root, f))
for root, dirs, files in os.walk(os.path.join(AE, 'Super Review')):
    for f in files:
        if '490' in f and f.endswith('.csv'): cands.append(os.path.join(root, f))
for c in sorted(set(cands)):
    try:
        print(f'  rms {rms_vs(tgt, load_csv_raw(c)):6.2f}  <- {c.replace(AE, "")}')
    except Exception as e:
        print(f'  ERR {e} {c}')

print()
print('===== Moondrop Para II: 本地是否有 + 候选 =====')
hits = []
for root, dirs, files in os.walk(AE):
    if 'Para' in root or any('Para' in f for f in files if f.endswith('.csv')):
        for f in files:
            if f.endswith('.csv'): hits.append(os.path.join(root, f))
tgt2 = load_json_points(os.path.join(PEQ, 'moondrop-para-ii-原始频响.json'))
for c in sorted(set(hits)):
    if 'Para' not in c: continue
    try:
        print(f'  rms {rms_vs(tgt2, load_csv_raw(c)):6.2f}  <- {c.replace(AE, "")}')
    except Exception as e:
        print(f'  ERR {e} {c}')
if not hits:
    print('  本地 AutoEq 无 Para 相关目录(需查 GitHub)')
