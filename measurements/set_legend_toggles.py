# -*- coding: utf-8 -*-
"""把 legend 显示开关(原始频响/目标频响/均衡后曲线/均衡线曲线)补进我建的预设。
按文件直读 bands(绕开 get_preset 的 10 段截断),apply 不截断且保留 notes。"""
import json, re, os, urllib.request

BASE = 'http://127.0.0.1:9100'
PRE = r'F:\MIMO-Space\PEQ-WebUI\apo-presets'

TARGETS = [
    'dt900-pro-x-mv1拟合-b',        # 本轮新建(B,11 段)
    'dt900-pro-x-mv1拟合',          # 本轮新建(A)
    'dt900-pro-x-哈曼校准',          # 本轮改过(扩散场校准,10 段)
    'dt900-pro-x-sonymv1拟合',      # 本轮改过(哈曼拟合,8 段)
]

LEGEND = {'device': True, 'target': True, 'eq': True, 'equalized': True,
          'applied': False, 'draft': False, 'preview': False}

def parse(path):
    txt = open(path, encoding='utf-8-sig').read()
    dev, tgt, pre, auto = 'Fiio', '', 0.0, False
    bands = []
    for line in txt.splitlines():
        lm = line.strip()
        if lm.startswith('Device:'):
            dev = lm.split(':', 1)[1].strip()
        elif lm.startswith('Preamp:'):
            pre = float(re.search(r'([-\d.]+)', lm).group(1))
        elif lm.startswith('# target:'):
            tgt = lm.split(':', 1)[1].strip()
        elif lm.startswith('# ui_state:'):
            try:
                auto = bool(json.loads(lm.split(':', 1)[1].strip()).get('auto_fit_enabled', False))
            except Exception:
                pass
        else:
            m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS|LP|HP) Fc ([\d.]+) Hz(?: Gain ([-+\d.]+) dB)? Q ([\d.]+)', lm)
            if m:
                b = {'type': m.group(2), 'freq': float(m.group(3)),
                     'gain_db': float(m.group(4)) if m.group(4) is not None else 0.0,
                     'q': float(m.group(5)), 'enabled': m.group(1) == 'ON'}
                bands.append(b)
    return dev, tgt, pre, auto, bands

for pid in TARGETS:
    path = os.path.join(PRE, pid + '.txt')
    if not os.path.exists(path):
        print(f'{pid}: 文件不存在,跳过'); continue
    dev, tgt, pre, auto, bands = parse(path)
    body = {'preset': pid, 'bands': bands, 'preamp_db': pre,
            'target_id': tgt, 'activate': False,
            'ui_state': {'auto_fit_enabled': auto, 'legend': LEGEND}}
    req = urllib.request.Request(BASE + '/api/eq/apply',
                                 data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    r = json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))
    print(f'{pid:32s} 段数 {len(bands):>2}  已写入 legend  |  active={r.get("active_preset_id")}')

print()
print('--- 回读校验 ---')
for pid in TARGETS:
    path = os.path.join(PRE, pid + '.txt')
    if not os.path.exists(path):
        continue
    for line in open(path, encoding='utf-8').read().splitlines():
        if line.startswith('# ui_state:'):
            u = json.loads(line.split(':', 1)[1].strip())
            print(f'{pid:32s} legend={u.get("legend")}')
            break
    n = sum(1 for l in open(path, encoding='utf-8') if l.startswith('Filter'))
    nt = sum(1 for l in open(path, encoding='utf-8') if l.startswith('# note:'))
    print(f'{"":32s} Filter {n} 段 | notes {nt} 行')
