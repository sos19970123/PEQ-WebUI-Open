# -*- coding: utf-8 -*-
"""索尼 MV1 体验方案选型:三副候选(DT900ProX / R70X / R70xa)拟合 oratory-MV1 的代价对比"""
import csv, json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

AE = r'F:\MIMO-Space\AutoEq-4.1.2\AutoEq-4.1.2\results'
DEV = r'F:\MIMO-Space\PEQ-WebUI\curves\devices'
TGT = r'F:\MIMO-Space\PEQ-WebUI\curves\targets'
MV1 = r'F:\MIMO-Space\PEQ-WebUI\measurements\oratory-Sony MDR-MV1\Sony MDR-MV1.csv'

def csv_pts(path, col='smoothed'):
    pts = []
    with open(path, 'rb') as f:
        t = f.read().decode('utf-8-sig', errors='replace')
    for row in csv.DictReader(t.splitlines()):
        try:
            pts.append((float(row['frequency']), float(row[col])))
        except Exception:
            pass
    pts.sort()
    return pts

def json_pts(p):
    return [(x[0], x[1]) for x in json.load(open(p, encoding='utf-8-sig'))['points']]

def aligned(pts, lo=500.0, hi=2000.0):
    a = np.array(pts, dtype=float)
    m = (a[:, 0] >= lo) & (a[:, 0] <= hi)
    return [(float(f), float(d)) for f, d in zip(a[:, 0], a[:, 1] - a[m, 1].mean())]

grid = af._log_grid()
seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]
lab = ['20-100','100-300','300-1k','1-3k','3-6k','6-9k','9-14k']
def brms(g):
    return [float(np.sqrt(np.mean(g[(grid >= lo) & (grid < hi)] ** 2))) for lo, hi in seg]

mv1_pts = aligned(csv_pts(MV1))
mv1 = af._interp(mv1_pts, grid)
tgt_h = af._interp(json_pts(os.path.join(TGT, 'harman_overear_2018.json')), grid)

print('===== MV1(oratory)自身特性: 相对哈曼(正=比哈曼高) =====')
print(f'{"band":>8} {"mean":>8}')
for i, l in enumerate(lab):
    sel = (mv1 - tgt_h)[(grid >= seg[i][0]) & (grid < seg[i][1])]
    print(f'{l:>8} {np.mean(sel):>+8.2f}')
print('关键点:')
for f in [30,60,100,200,500,1000,2000,3000,4000,5000,6000,7000,8000,9000,10000,12000]:
    k = int(np.argmin(np.abs(grid - f)))
    print(f'  {f:>6}Hz  MV1 {mv1[k]:+6.2f} | Harman {tgt_h[k]:+6.2f} | 差 {mv1[k]-tgt_h[k]:+6.2f}')

print()
print('===== R70xa 曲线来源验证 =====')
rxa = af._interp(json_pts(os.path.join(DEV, 'audio-technica-ath-r70xa.json')), grid)
orat_rxa = af._interp(aligned(csv_pts(os.path.join(AE, 'oratory1990', 'over-ear',
                                                  'Audio-Technica ATH-R70xa',
                                                  'Audio-Technica ATH-R70xa.csv'))), grid)
print(f'  peq-webui R70xa vs oratory1990 R70xa: rms {np.sqrt(np.mean((rxa-orat_rxa)**2)):.2f}  (≈0 即同源)')

print()
print('===== 三副候选拟合 oratory-MV1(oratory rig, 无跨 rig)=====')
cands = [('DT900 Pro X', 'dt900prox'),
         ('R70X', 'r70x'),
         ('R70xa', 'audio-technica-ath-r70xa')]
summary = []
for name, did in cands:
    dpts = json_pts(os.path.join(DEV, did + '.json'))
    dev = af._interp(dpts, grid)
    gap = dev - mv1
    r = af.autofit(dpts, mv1_pts, filters=10, fmin=100.0, fmax=12000.0,
                   max_gain_db=6.0, max_q=3.0, auto_shelf=False,
                   sanitize=True, smooth_oct=1/12)
    gains = [b['gain_db'] for b in r['bands']]
    pos = sum(g for g in gains if g > 0)
    print(f'\n-- {name}  (oratory GRAS 45BC-10)')
    print('   原始差距 rms: ' + ' | '.join(f'{l} {v:.2f}' for l, v in zip(lab, brms(gap))))
    print(f'   拟合后 rms {r["rms_db"]:.2f} dB | preamp {r["preamp_db"]:.2f} dB | 最大增益 {max(gains):+.1f} | 正增益合计 {pos:+.1f}')
    print('   ' + ', '.join(f'{b["freq"]:.0f}Hz {b["gain_db"]:+.1f}' for b in r['bands']))
    summary.append((name, r['rms_db'], r['preamp_db'], max(gains), pos,
                    brms(gap)[0], brms(gap)[-1]))

print()
print('===== 汇总 =====')
print(f'{"候选":<14} {"拟合rms":>8} {"preamp":>8} {"最大增益":>9} {"正增益和":>9} {"低频差":>8} {"9-14k差":>8}')
for n, rms, pre, mg, pos, lo, hi in summary:
    print(f'{n:<14} {rms:>8.2f} {pre:>8.2f} {mg:>+9.1f} {pos:>+9.1f} {lo:>8.2f} {hi:>8.2f}')
