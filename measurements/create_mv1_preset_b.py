# -*- coding: utf-8 -*-
"""建 A/B 对照:B 版 = DT900->MV1(同 rig),max_q=4 + sanitize OFF"""
import json, urllib.request, urllib.parse

BASE = 'http://127.0.0.1:9100'
NAME = 'DT900 Pro X · MV1拟合 B'
TID = 'sony-mdr-mv1-oratory-原始频响'

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=120).read().decode('utf-8'))

def put(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='PUT')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

# 1) 建预设
r = post('/api/preset/add', {'name': NAME, 'device_id': 'dt900prox'})
pid = (r.get('preset') or {}).get('id')
print('preset id =', pid)

# 2) 拟合:max_q=4,sanitize 关,其余与 A 版一致
f = post('/api/eq/autofit', {
    'preset': pid, 'target': TID,
    'filters': 10, 'fmin': 100, 'fmax': 12000,
    'max_gain_db': 6, 'max_q': 4,
    'sanitize_bands': False,
    'min_mean_error': False,
    'sharpness_penalty': True,
    'smooth': True,
    'engine': 'quick', 'auto_shelf': False,
})
print('fit ok =', f.get('ok'), '| rms =', f.get('rms_db'), '| preamp =', f.get('preamp_db'), '| engine =', f.get('engine'))
print('alignment =', f.get('alignment'))
bands = [{'type': b['type'], 'freq': b['freq'], 'gain_db': b['gain_db'], 'q': b['q'], 'enabled': True}
         for b in f['bands']]
for b in bands:
    print(f"  {b['freq']:>9.2f}Hz {b['gain_db']:>+6.2f}dB Q{b['q']:.3f}")

# 3) 落盘
a = post('/api/eq/apply', {'preset': pid, 'bands': bands, 'preamp_db': f['preamp_db'],
                           'target_id': TID, 'activate': False})
print('apply ok =', a.get('ok'), '| bands =', len(a.get('applied') or []), '| active =', a.get('active_preset_id'))

# 4) 笔记(写两遍:第一遍会因后端 bug 倒序,第二遍修正)
notes = """2026-09-11 新建(A/B 对照的 B 版):DT900 Pro X(oratory GRAS 45BC-10)→ Sony MDR-MV1(oratory1990,同 rig)
与 A 版(DT900 Pro X · MV1拟合)唯一差别:关闭 sanitize 后处理,max_q 3→4
- 原因:A 版被 sanitize 的高频正增益上限卡住(>8k 钳 4dB、>10k 钳 2.5dB),而本拟合是同 rig,rig 差异在差值里抵消,该上限过于保守
- 放开后:6-9k 残差 2.79→0.38,9-11k 2.19→0.49,整体形状 rms 2.73→2.20(均为未平滑逐点口径)
- 主要变化:8181Hz +2.5→+4.2(填 MV1 的 8k 尖峰)、新增 11186Hz +3.2 Q0.90(宽 Q 补 9-12k)
- 4k 谷不再强行填(4045Hz +6.0Q3 → +4.8Q4):4 个 rig 实测谷底位置均为 4045Hz 但深度 -2.26~-6.27(差 2.8 倍),属腔体/耦合抵消型凹陷,加能量会被再抵消,且深度不确定——实测放开 Q 到 8 只能多填 0.5dB
- 代价:preamp -3.30 → -5.54(形状峰值 +5.34 @8.2k);4k 区群延迟 0.17→0.19ms(可忽略)
- A/B 提示:两版 preamp 差 2.3dB,试听请做音量对齐
- 残差现状:3-6k 1.44 | 6-9k 0.38 | 9-11k 0.49 | 11-14k 6.8(>10k 不可验证,不再追)
状态:未激活"""

for attempt in (1, 2):
    n = put('/api/preset/notes', {'id': pid, 'notes': notes})
    print(f'notes write #{attempt} ok =', n.get('ok'))

# 5) 回读
p = json.loads(urllib.request.urlopen(BASE + '/api/preset/config?id=' + urllib.parse.quote(pid), timeout=30).read().decode('utf-8'))
lines = p.get('config_text', '').splitlines()
print('--- 文件回读 ---')
for l in lines:
    print(l)
