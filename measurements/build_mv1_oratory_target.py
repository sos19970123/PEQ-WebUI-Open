# -*- coding: utf-8 -*-
"""生成 oratory 版 Sony MDR-MV1 目标曲线(供 peq-webui 同 rig 拟合)
schema 完全对齐现有 imported 目标: points = CSV raw + 500-2k 归零偏移"""
import csv, json, numpy as np, os

SRC = r'F:\MIMO-Space\PEQ-WebUI\measurements\oratory-Sony MDR-MV1\Sony MDR-MV1.csv'
OUT = r'F:\MIMO-Space\PEQ-WebUI\curves\targets\sony-mdr-mv1-oratory-原始频响.json'

pts = []
with open(SRC, 'rb') as f:
    t = f.read().decode('utf-8-sig', errors='replace')
for row in csv.DictReader(t.splitlines()):
    try:
        fq = float(row['frequency']); raw = float(row['raw'])
    except Exception:
        continue
    if 20.0 <= fq <= 20000.0:
        pts.append((fq, raw))
pts.sort()

a = np.array(pts, dtype=float)
m = (a[:, 0] >= 500.0) & (a[:, 0] <= 2000.0)
ref = float(a[m, 1].mean())
offset = round(-ref, 4)
aligned = [[round(float(f), 4), round(float(d) + offset, 4)] for f, d in pts]
chk = np.array(aligned)
print(f'points={len(aligned)}  raw 500-2k mean={ref:+.4f}  offset_db={offset}  归一后 mean={chk[(chk[:,0]>=500)&(chk[:,0]<=2000),1].mean():+.4f}')

obj = {
    'id': 'sony-mdr-mv1-oratory-原始频响',
    'name': 'Sony MDR-MV1 (原始频响·oratory1990)',
    'kind': 'target',
    'source': 'oratory1990',
    'points': aligned,
    'category': 'headphone',
    'alignment': {'enabled': True, 'method': 'mean', 'ref_low': 500.0, 'ref_high': 2000.0, 'offset_db': offset},
    'measured_device': 'Sony MDR-MV1',
    'measurement_source': 'oratory1990',
    'variant': 'oratory1990',
    'rig': 'GRAS 45BC-10',
    'rig_family': 'KEMAR HATS',
    'rig_standard': 'GRAS 45BC-10 KEMAR 型头身模拟器（Head-and-Torso Simulator）',
    'rig_note': '与 DT900 Pro X / R70X / R70xa 设备曲线同一 rig（oratory1990/AutoEq 基准），同源可比，无跨 rig 污染。',
    'measurement_rig': 'GRAS 45BC-10',
    'url': 'https://www.reddit.com/r/oratory1990/wiki/index/list_of_presets/',
    'measurement_url': 'https://www.reddit.com/r/oratory1990/wiki/index/list_of_presets/',
}
with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
    json.dump(obj, f, ensure_ascii=False, indent=2)
print('written:', OUT)
