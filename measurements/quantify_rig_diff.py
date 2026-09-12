# -*- coding: utf-8 -*-
"""量化跨 rig 差异:同一副耳机在不同 rig 上的测量差(= 纯 rig 差异,耳机不变)
用途:判断各拟合预设的残差里,多少是"真实耳机差",多少是"rig 假差异" """
import json, numpy as np, sys, os
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

DEV = r'F:\MIMO-Space\PEQ-WebUI\curves\devices'

def load(i):
    o = json.load(open(os.path.join(DEV, i + '.json'), encoding='utf-8-sig'))
    return o.get('source', '?'), o.get('rig', o.get('measurement_rig', '?')), [(x[0], x[1]) for x in o['points']]

grid = af._log_grid()
seg = [(20,100),(100,300),(300,1000),(1000,3000),(3000,6000),(6000,9000),(9000,14000)]

def diff_report(label, a, b):
    (sa, ra, pa), (sb, rb, pb) = load(a), load(b)
    ga, gb = af._interp(pa, grid), af._interp(pb, grid)
    d = ga - gb
    print(f'-- {label}')
    print(f'   {sa}/{ra}  vs  {sb}/{rb}')
    for lo, hi in seg:
        sel = d[(grid>=lo)&(grid<hi)]
        print(f'   {lo:>5}-{hi:<5}Hz  rms {np.sqrt(np.mean(sel**2)):5.2f}  mean {np.mean(sel):+5.2f}  max {np.max(np.abs(sel)):5.2f}')

print('===== DT900 Pro X: 多 rig 差异(用于判断"乐园2拟合")=====')
diff_report('oratory GRAS 45BC-10  vs  Super Review KB006x+711', 'dt900prox', 'dt900prox-superreview')
diff_report('oratory GRAS 45BC-10  vs  Rtings B&K 5128', 'dt900prox', 'dt900prox-rtings')
diff_report('oratory GRAS 45BC-10  vs  Kuulokenurkka', 'dt900prox', 'dt900prox-kuulokenurkka')

print()
print('===== R70X: 多 rig 差异(用于判断"HD490PRO 拟合")=====')
diff_report('oratory GRAS 45BC-10  vs  Rtings B&K 5128', 'r70x', 'r70x-rtings')
diff_report('oratory GRAS 45BC-10  vs  Kuulokenurkka', 'r70x', 'r70x-kuulokenurkka')
diff_report('oratory GRAS 45BC-10  vs  Innerfidelity', 'r70x', 'r70x-innerfidelity')
