# -*- coding: utf-8 -*-
"""落盘两条修改:先 PUT notes(会截到10段),再 apply 完整段数(apply 保留笔记)
   并按用户要求带上 ui_state.legend 四项全开"""
import json, re, os, urllib.request

BASE = 'http://127.0.0.1:9100'
PRE = r'F:\MIMO-Space\PEQ-WebUI\apo-presets'
LEGEND = {'device': True, 'target': True, 'eq': True, 'equalized': True,
          'applied': False, 'draft': False, 'preview': False}

def parse(pid):
    txt = open(os.path.join(PRE, pid + '.txt'), encoding='utf-8-sig').read()
    dev = tgt = ''; pre = 0.0; auto = False; bands = []
    for lm in [l.strip() for l in txt.splitlines()]:
        if lm.startswith('# device:'): dev = lm.split(':', 1)[1].strip()
        elif lm.startswith('# target:'): tgt = lm.split(':', 1)[1].strip()
        elif lm.startswith('Preamp:'): pre = float(re.search(r'([-\d.]+)', lm).group(1))
        elif lm.startswith('# ui_state:'):
            try: auto = bool(json.loads(lm.split(':', 1)[1].strip()).get('auto_fit_enabled', False))
            except Exception: pass
        else:
            m = re.match(r'Filter \d+: (ON|OFF) (PK|LS|HS) Fc ([\d.]+) Hz(?: Gain ([-+\d.]+) dB)? Q ([\d.]+)', lm)
            if m:
                bands.append({'type': m.group(2), 'freq': float(m.group(3)),
                              'gain_db': float(m.group(4)) if m.group(4) else 0.0,
                              'q': float(m.group(5)), 'enabled': m.group(1) == 'ON'})
    return dev, tgt, pre, auto, bands

def put(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='PUT')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

JOBS = [
    ('dt900prox-harman', 'DT900 Pro X · 乐园2拟合',
     [{'type': 'PK', 'freq': 3500.0, 'gain_db': -3.0, 'q': 2.5, 'enabled': True},
      {'type': 'PK', 'freq': 4050.0, 'gain_db': 3.0, 'q': 3.5, 'enabled': True},
      {'type': 'PK', 'freq': 5300.0, 'gain_db': -5.0, 'q': 1.5, 'enabled': True},
      {'type': 'PK', 'freq': 6200.0, 'gain_db': -5.0, 'q': 1.6, 'enabled': True}],
     """2026-09-11 补完 2k 以上(原 10 段滤波器全部 ≤3.1kHz = 半成品,2k 以上完全没拟合):
- 追加 3500Hz -3.0Q2.5 / 4050Hz +3.0Q3.5 / 5300Hz -5.0Q1.5 / 6200Hz -5.0Q1.6
- 4050 是"轻填"DT900 的 4k 抵消谷(实测该谷 4 rig 位置一致但深度差 2.8 倍,填满无意义)+3 即可
- 5300/6200 双段削 DT900 的 5-6.5k 金属峰(原厂该处比自身 500-2k 高 +7~9dB,是"人声抢戏/齿音刺"的来源)
- 效果:2-6k 残差 3.98→2.75,6-9k 4.49→3.15(未平滑逐点口径)
- 保守处理:目标跨 rig(Super Review KB006x+711),故只做到 6.5k、削减只做需求的 ~60-70%,9k 以上不动
- preamp 保持 -2.06(新增段未抬高峰值,峰值 +1.51)"""),
    ('dt900-pro-x-哈曼校准', 'DT900 pro x · 扩散场校准',
     [{'type': 'LS', 'freq': 60.0, 'gain_db': -2.41, 'q': 0.707, 'enabled': True}],
     """2026-09-11 补低频(原 20-100Hz 比扩散场目标高 +1.56dB,即没砍到位):
- 追加 LS 60Hz -2.41dB Q0.707
- 效果:20-100Hz 残差 1.75→0.14,100-400Hz 0.62→0.57,2k 以上完全不变
- LS 的 Q 必须取 0.707:>0.707 会在 60-100Hz 挖坑,<0.707 会漏进 200Hz
- Fc 取 60 而非 40:缺口平坦延伸到 80Hz,40Hz 的架在 60Hz 只给一半
- preamp 保持 -6.55(段为负增益,峰值仍 +6.35)"""),
]

for pid, name, add, note in JOBS:
    dev, tgt, pre, auto, cur = parse(pid)
    bands = cur + add
    print(f'--- {name}({pid})---')
    print(f'   {len(cur)} 段 + {len(add)} 段 = {len(bands)} 段 | preamp {pre} | target {tgt}')

    old_notes = []
    for lm in [l for l in open(os.path.join(PRE, pid + '.txt'), encoding='utf-8-sig').read().splitlines() if l.startswith('# note:')]:
        old_notes.append(lm[len('# note:'):].strip())
    new_notes = '\n'.join(old_notes + note.split('\n'))

    for i in (1, 2):     # 两遍:规避首次写入倒序
        r = put('/api/preset/notes', {'id': pid, 'notes': new_notes})
        print(f'   notes #{i} ok={r.get("ok")}')
    a = post('/api/eq/apply', {'preset': pid, 'bands': bands, 'preamp_db': pre, 'target_id': tgt,
                               'activate': False,
                               'ui_state': {'auto_fit_enabled': auto, 'legend': LEGEND}})
    print(f'   apply ok={a.get("ok")} bands={len(a.get("applied") or [])} active={a.get("active_preset_id")}')
    print()

print('--- 回读校验 ---')
for pid, name, _, _ in JOBS:
    lines = open(os.path.join(PRE, pid + '.txt'), encoding='utf-8').read().splitlines()
    print(f'{pid}: Filter {sum(1 for l in lines if l.startswith("Filter"))} 段 | notes {sum(1 for l in lines if l.startswith("# note:"))} 行')
    for l in lines:
        if l.startswith('# ui_state:'):
            print('   legend =', json.loads(l.split(':', 1)[1].strip()).get('legend'))
