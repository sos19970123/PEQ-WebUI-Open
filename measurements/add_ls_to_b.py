# -*- coding: utf-8 -*-
"""给 B 版补上同一条 LS 60Hz +3.0 Q0.707(与 A 对齐,只留 sanitize/Q 这一个变量),并重算 preamp"""
import json, urllib.request, numpy as np, sys
sys.path.insert(0, r'F:\MIMO-Space\PEQ-WebUI')
import autofit as af

BASE = 'http://127.0.0.1:9100'
PID = 'dt900-pro-x-mv1拟合-b'
TID = 'sony-mdr-mv1-oratory-原始频响'

bands = [
    {'type': 'PK', 'freq': 101.6, 'gain_db': 2.70, 'q': 0.432, 'enabled': True},
    {'type': 'PK', 'freq': 1376.16, 'gain_db': 1.10, 'q': 2.613, 'enabled': True},
    {'type': 'PK', 'freq': 2082.81, 'gain_db': -2.34, 'q': 1.527, 'enabled': True},
    {'type': 'PK', 'freq': 2792.44, 'gain_db': 2.15, 'q': 3.226, 'enabled': True},
    {'type': 'PK', 'freq': 4044.94, 'gain_db': 4.85, 'q': 4.0, 'enabled': True},
    {'type': 'PK', 'freq': 4758.83, 'gain_db': -5.14, 'q': 3.6, 'enabled': True},
    {'type': 'PK', 'freq': 5910.42, 'gain_db': 1.47, 'q': 4.0, 'enabled': True},
    {'type': 'PK', 'freq': 8180.78, 'gain_db': 4.23, 'q': 2.289, 'enabled': True},
    {'type': 'PK', 'freq': 11186.33, 'gain_db': 3.16, 'q': 0.896, 'enabled': True},
    {'type': 'PK', 'freq': 11634.18, 'gain_db': -6.00, 'q': 2.58, 'enabled': True},
    {'type': 'LS', 'freq': 60.0, 'gain_db': 3.0, 'q': 0.707, 'enabled': True},
]

# preamp:按级联形状最大正峰值 + 0.2 headroom
grid = af._log_grid()
s = np.zeros_like(grid)
for b in bands:
    s += af._rbj_mag_db(grid, b['type'], b['freq'], b['gain_db'], b['q'], sr=48000)
i = int(np.argmax(s))
preamp = round(-(float(s.max()) + 0.2), 4)
print(f'B+LS 形状峰值 {s.max():+.2f}dB @{grid[i]:.0f}Hz -> preamp {preamp}')
for f in (30, 60, 100, 200):
    print(f'   {f}Hz 总增益 {s[int(np.argmin(np.abs(grid-f)))]:+.2f}')

req = urllib.request.Request(BASE + '/api/eq/apply',
                             data=json.dumps({'preset': PID, 'bands': bands, 'preamp_db': preamp,
                                              'target_id': TID, 'activate': False}).encode('utf-8'),
                             headers={'Content-Type': 'application/json'}, method='POST')
r = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))
print('apply ok =', r.get('ok'), '| bands =', len(r.get('applied') or []), '| active =', r.get('active_preset_id'))
