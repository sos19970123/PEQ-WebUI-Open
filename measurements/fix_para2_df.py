# -*- coding: utf-8 -*-
"""① 乐园2:保留现有 10 段,追加 2k-6.5k 修正(目标跨rig -> 只做到 6.5k)
   ② 扩散场:保留现有 10 段,追加一条 LS 修 20-100Hz 偏低"""
import json, re, os, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = r'F:\MIMO-Space\PEQ-WebUI'
PRE = os.path.join(BASE, 'apo-presets')
DEV, TGT = os.path.join(BASE, 'curves/devices'), os.path.join(BASE, 'curves/targets')
grid = af._log_grid()

def jp(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

def parse(pid):
    txt = open(os.path.join(PRE, pid + '.txt'), encoding='utf-8-sig').read()
    dev = tgt = ''; pre = 0.0; bands = []
    for line in txt.splitlines():
        lm = line.strip()
        if lm.startswith('# device:'): dev = lm.split(':', 1)[1].strip()
        elif lm.startswith('# target:'): tgt = lm.split(':', 1)[1].strip()
        elif lm.startswith('Preamp:'): pre = float(re.search(r'([-\d.]+)', lm).group(1))
        else:
            m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz(?: Gain ([-+\d.]+) dB)? Q ([\d.]+)', lm)
            if m and m.group(1) == 'ON':
                bands.append((m.group(2), float(m.group(3)), float(m.group(4)) if m.group(4) else 0.0, float(m.group(5))))
    return dev, tgt, pre, bands

def shape(bs, x=None):
    s = np.zeros_like(grid)
    for t, fc, g, q in bs:
        s += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    if x:
        t, fc, g, q = x
        s += af._rbj_mag_db(grid, t, fc, g, q, sr=48000)
    return s

SEG = [(20,100),(100,400),(400,2000),(2000,6000),(6000,9000),(9000,14000)]
LAB = ['20-100','100-400','400-2k','2-6k','6-9k','9-14k']
def rr(res):
    return [float(np.sqrt(np.mean(res[(grid >= lo) & (grid < hi)] ** 2))) for lo, hi in SEG]
def show(label, res):
    print(f'{label:<30} ' + ' '.join(f'{l} {v:5.2f}' for l, v in zip(LAB, rr(res))))

# ================= ① 乐园2 =================
print('========== ① DT900 · 乐园2拟合 ==========')
dev_id, tgt_id, pre, cur = parse('dt900prox-harman')
print(f'现有 {len(cur)} 段, preamp {pre} | 目标 {tgt_id}(跨 rig)')
d = af._interp(jp(os.path.join(DEV, dev_id + '.json')), grid)
t = af._interp(jp(os.path.join(TGT, tgt_id + '.json')), grid)
s_cur = shape(cur)
need = t - d - s_cur          # 还需要补的量
print('\n2k-7.5k 逐点需求(正=要抬,负=要削):')
for f in [2000,2500,3000,3500,4000,4500,5000,5500,6000,6500,7000,7500]:
    i = int(np.argmin(np.abs(grid - f)))
    print(f'  {f:>5}Hz {need[i]:+6.2f}')

cands = [('PK',3500.0,3.0), ('PK',4050.0,3.5), ('PK',5300.0,2.0), ('PK',6100.0,1.6), ('PK',6600.0,2.5)]
mask = (grid >= 2500) & (grid <= 6700)
S = np.column_stack([af._unit_shape(grid, c[0], c[1], c[2], sr=48000) for c in cands])
gains, *_ = np.linalg.lstsq(S[mask], need[mask], rcond=None)
print('\n解出的追加段(全量):')
for c, g in zip(cands, gains):
    print(f'  PK {c[1]:>7.1f}Hz {g:+6.2f}dB Q{c[2]}')
add = [('PK', c[1], float(round(g, 2)), c[2]) for c, g in zip(cands, gains)]
print()
show('现状', d + s_cur - t)
show('+追加段(全量)', d + shape(cur, None) + shape(add) - t)

# 阻尼版:5-6.5k 的削减只做 70%(跨 rig 保守)
add_d = []
for tp, fc, g, q in add:
    g2 = g * (1.0 if g > 0 else 0.7)
    add_d.append((tp, fc, round(g2, 2), q))
print('\n阻尼版(负增益只做 70%):')
for tp, fc, g, q in add_d:
    print(f'  PK {fc:>7.1f}Hz {g:+6.2f}dB Q{q}')
show('+追加段(阻尼)', d + shape(cur) + shape(add_d) - t)
s_new = shape(cur) + shape(add_d)
i = int(np.argmax(s_new))
print(f'\n阻尼版形状峰值 {s_new.max():+.2f}dB @{grid[i]:.0f}Hz -> preamp {-(s_new.max()+0.2):.2f}(原 {pre})')

# ================= ② 扩散场 =================
print('\n========== ② DT900 · 扩散场校准 ==========')
dev2, tgt2, pre2, cur2 = parse('dt900-pro-x-哈曼校准')
print(f'现有 {len(cur2)} 段, preamp {pre2} | 目标 {tgt2}')
d2 = af._interp(jp(os.path.join(DEV, dev2 + '.json')), grid)
t2 = af._interp(jp(os.path.join(TGT, tgt2 + '.json')), grid)
show('现状', d2 + shape(cur2) - t2)
print('\n20-200Hz 逐点残差(现状):')
for f in [20,30,40,50,60,80,100,150,200]:
    i = int(np.argmin(np.abs(grid - f)))
    print(f'  {f:>4}Hz {d2[i] + shape(cur2)[i] - t2[i]:+6.2f}')
# 解一条 LS 60Hz Q0.707 的增益,最小化 20-150Hz 残差
res_now = d2 + shape(cur2) - t2
m2 = (grid >= 20) & (grid <= 160)
ls_shape = af._unit_shape(grid, 'LS', 60.0, 0.707, sr=48000)[m2]
g_ls = float(-np.linalg.lstsq(ls_shape.reshape(-1, 1), res_now[m2], rcond=None)[0][0])
print(f'\n解出 LS 60Hz Q0.707 增益 = {g_ls:+.2f} dB')
for gg in [round(g_ls, 2), round(g_ls * 0.8, 2)]:
    add_ls = ('LS', 60.0, gg, 0.707)
    print(f'\n-- 加 LS 60Hz {gg:+.2f} Q0.707 --')
    show('  结果', d2 + shape(cur2, add_ls) - t2)
    s = shape(cur2, add_ls)
    i = int(np.argmax(s))
    print(f'  形状峰值 {s.max():+.2f}dB @{grid[i]:.0f}Hz -> preamp {-(s.max()+0.2):.2f}(原 {pre2})')
