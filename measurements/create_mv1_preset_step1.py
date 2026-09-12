# -*- coding: utf-8 -*-
"""① 建预设 ② 跑 DT900 Pro X -> oratory-MV1 同 rig 拟合,输出建议频段(先不落盘)"""
import json, urllib.request

BASE = 'http://127.0.0.1:9100'

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=30).read().decode('utf-8'))

# 1. 建预设
r = post('/api/preset/add', {'name': 'DT900 Pro X · MV1拟合', 'device_id': 'dt900prox'})
print('add ok =', r.get('ok'))
p = r.get('preset') or {}
pid = p.get('id')
print('preset id =', pid, '| name =', p.get('name'), '| device =', p.get('device_id'))

# 2. 拟合(webui 默认温和档: max_gain 6 / max_q 3,quick 引擎)
f = post('/api/eq/autofit', {
    'preset': pid,
    'target': 'sony-mdr-mv1-oratory-原始频响',
    'filters': 10, 'fmin': 100, 'fmax': 12000,
    'max_gain_db': 6, 'max_q': 3,
    'engine': 'quick', 'auto_shelf': False,
})
print()
print('autofit ok =', f.get('ok'), '| rms =', round(f.get('rms_db', -1), 3),
      '| preamp =', round(f.get('preamp_db', 0), 3), '| engine =', f.get('engine'))
print('warnings =', f.get('warnings'))
print('alignment =', f.get('alignment'))
print()
print('band            freq      gain     Q')
for b in f.get('bands', []):
    print(f'  {b["type"]:>3}  {b["freq"]:>9.2f}  {b["gain_db"]:>+6.2f}  {b["q"]:.3f}')

with open(r'F:\MIMO-Space\PEQ-WebUI\measurements\_mv1_fit.json', 'w', encoding='utf-8') as fh:
    json.dump({'preset_id': pid, 'fit': f}, fh, ensure_ascii=False, indent=1)
print('\n(saved _mv1_fit.json)')
