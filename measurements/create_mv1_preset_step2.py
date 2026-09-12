# -*- coding: utf-8 -*-
"""落盘:DT900 Pro X · MV1拟合 —— 写 bands + target + notes(顺序:apply -> notes)"""
import json, urllib.request

BASE = 'http://127.0.0.1:9100'
PID = 'dt900-pro-x-mv1拟合'
TID = 'sony-mdr-mv1-oratory-原始频响'

fit = json.load(open(r'F:\MIMO-Space\PEQ-WebUI\measurements\_mv1_fit.json', encoding='utf-8'))['fit']
bands = [{'type': b['type'], 'freq': b['freq'], 'gain_db': b['gain_db'], 'q': b['q'], 'enabled': True}
         for b in fit['bands']]

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

def put(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='PUT')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

# ① 写参数 + 目标曲线(不激活)
r = post('/api/eq/apply', {'preset': PID, 'bands': bands, 'preamp_db': -3.3,
                           'target_id': TID, 'activate': False})
print('apply ok =', r.get('ok'), '| bands =', len(r.get('applied') or []),
      '| target =', r.get('target_id'), '| active =', r.get('active_preset_id'))

# ② 笔记
notes = """2026-09-11 新建:DT900 Pro X(oratory GRAS 45BC-10)→ Sony MDR-MV1(oratory1990,同 rig,无跨 rig)
目标曲线=新导入 sony-mdr-mv1-oratory-原始频响(oratory 版)。原库内 MV1 目标是 Rtings 版,与 DT900 跨 rig:两家 MV1 测量在 6-9k 差 5.4dB rms(8k 处 6.4dB、9k 处 8.1dB),故弃用换 oratory 同源版。
拟合参数:quick 引擎 / 10 段 / fmin 100 / fmax 12000 / max_gain 6 / max_q 3 / sanitize 开 / smooth 1/12
引擎口径 rms 0.86dB,preamp -3.30dB(余量充裕)
关键段:
- 4045Hz +6.0(顶格)= 填 DT900 的 4k 深谷(MV1 该处无谷)。若听出 4k 失真/刺,降到 +4~+5
- 4759Hz -5.86 = 压 DT900 的 5k 峰;101.6Hz +2.62 宽 Q = 补中低频暖度(MV1 100-300Hz 比哈曼高 3.4dB)
- 5910/8180/9755Hz +2.5~2.6 = 复现 MV1 的 6-9k 亮度
已知局限:
- MV1 实测 8k 有 +7.5dB 尖峰,受 sanitize 高频正增益上限限制只补到 +2.5 → 8-10k 亮度可能不及真机
- 3k/6k 处的窄峰(+8/+11)无法用 10 段完全复现
- fmin=100:20-100Hz 仅由 101.6Hz 宽 Q 段部分覆盖,下潜匹配不完整(要更深可加 LS 40Hz +2~3)
状态:未激活"""

n = put('/api/preset/notes', {'id': PID, 'notes': notes})
print('notes ok =', n.get('ok'))
