# -*- coding: utf-8 -*-
"""11 条预设的"忠实度矩阵":逐段形状残差 + rig 关系
   残差小 = 忠实复现了目标;残差大 = 保留了本机特色/未能复现"""
import json, re, os, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
PRE = os.path.join(BASE, 'apo-presets')
grid = af._log_grid()
DEV, TGT = os.path.join(BASE, 'curves/devices'), os.path.join(BASE, 'curves/targets')

SEG = [(20,100),(100,400),(400,2000),(2000,6000),(6000,9000),(9000,14000)]
LAB = ['20-100','100-400','400-2k','2-6k','6-9k','9-14k']

def load_points(path):
    o = json.load(open(path, encoding='utf-8-sig'))
    return o, [(p[0], p[1]) for p in o['points']]

def parse_preset(pid):
    txt = open(os.path.join(PRE, pid + '.txt'), encoding='utf-8-sig').read()
    dev = tgt = ''
    bands = []
    for line in txt.splitlines():
        lm = line.strip()
        if lm.startswith('# device:'): dev = lm.split(':', 1)[1].strip()
        elif lm.startswith('# target:'): tgt = lm.split(':', 1)[1].strip()
        else:
            m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz(?: Gain ([-+\d.]+) dB)? Q ([\d.]+)', lm)
            if m and m.group(1) == 'ON':
                bands.append((m.group(2), float(m.group(3)),
                              float(m.group(4)) if m.group(4) else 0.0, float(m.group(5))))
    return dev, tgt, bands

PRESETS = [
    ('R70X', 'r70x-r70xa拟合', 'R70X ·R70XA拟合'),
    ('R70X', '1-2', 'R70X ·HD490PRO拟合'),
    ('R70X', '1', 'R70X ·MSR7B拟合'),
    ('DT900', 'dt900-pro-x-sonymv1拟合', 'DT900 ·哈曼拟合'),
    ('DT900', 'dt900-pro-x-哈曼校准', 'DT900 ·扩散场校准'),
    ('DT900', 'dt900prox-harman', 'DT900 ·乐园2拟合'),
    ('DT900', 'dt900-pro-x-mv1拟合-b', 'DT900 ·MV1拟合'),
    ('E40', 'e40', 'E40 ·fw01拟合'),
    ('FD02', 'fd02-哈曼校准', 'FD02 ·fw1800校准'),
    ('FD02', 'fd02-vdsf校准', 'FD02 ·VDSF校准'),
    ('FD02', 'fd02-fw10000拟合', 'FD02 ·FW10000拟合'),
]

print('=== 各预设目标来源(rig 可比性)===\n')
info = {}
for _, pid, name in PRESETS:
    dev_id, tgt_id, bands = parse_preset(pid)
    dpath = os.path.join(DEV, dev_id + '.json')
    tpath = os.path.join(TGT, tgt_id + '.json')
    if not (os.path.exists(dpath) and os.path.exists(tpath)):
        print(f'{name}: 曲线缺失 dev={dev_id!r} tgt={tgt_id!r}')
        continue
    dobj, dpts = load_points(dpath)
    tobj, tpts = load_points(tpath)
    drig = dobj.get('rig') or dobj.get('measurement_rig') or dobj.get('source', '?')
    trig = tobj.get('rig') or tobj.get('measurement_rig') or tobj.get('source', '?')
    d = af._interp(dpts, grid); t = af._interp(tpts, grid)
    eq = np.zeros_like(grid)
    for tp, fc, g, q in bands:
        eq += af._rbj_mag_db(grid, tp, fc, g, q, sr=48000)
    res = d + eq - t
    rr = [float(np.sqrt(np.mean(res[(grid >= lo) & (grid < hi)] ** 2))) for lo, hi in SEG]
    info[name] = (dobj, tobj, drig, trig, rr, len(bands))

for name, (dobj, tobj, drig, trig, rr, nb) in info.items():
    same = '同 rig' if str(drig).strip() and str(drig).strip() == str(trig).strip() else '跨 rig'
    print(f'{name:<22} [{nb:>2}段]  设备 {drig:<22} | 目标 {trig:<24} -> {same}')

print()
print('=== 忠实度矩阵(形状残差 rms,dB;越小越忠实)===\n')
print(f'{"预设":<22} ' + ' '.join(f'{l:>7}' for l in LAB))
print('-' * 100)
for name, (dobj, tobj, drig, trig, rr, nb) in info.items():
    cells = []
    for v in rr:
        mark = '  ' if v < 1.0 else (' ~' if v < 2.0 else ' !')
        cells.append(f'{v:5.2f}{mark}')
    print(f'{name:<22} ' + ' '.join(cells))
print()
print('图例: 无标记=忠实(<1.0dB) | ~ =部分(1.0-2.0) | ! =保留本体/未复现(>2.0)')
