# -*- coding: utf-8 -*-
"""把 A/B 试听结论写入 B 版笔记,并把 11 段补回(规避 notes 截断 bug)
顺序:PUT notes(会把文件截成10段) -> POST apply 完整11段(apply 保留笔记)"""
import json, urllib.request

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
PREAMP = -5.5518

notes = """2026-09-11 新建(A/B 对照的 B 版):DT900 Pro X(oratory GRAS 45BC-10)→ Sony MDR-MV1(oratory1990,同 rig)
与 A 版(DT900 Pro X · MV1拟合)唯一差别:关闭 sanitize 后处理,max_q 3→4;LS 60Hz +3.0 Q0.707 两版相同
- 原因:A 版被 sanitize 的高频正增益上限卡住(>8k 钳 4dB、>10k 钳 2.5dB),而本拟合是同 rig,rig 差异在差值里抵消,该上限过于保守
- 放开后:6-9k 残差 2.79→0.38,9-11k 2.22→0.49,全段 2.52→1.91(未平滑逐点口径)
- 主要变化:8181Hz +2.5→+4.23(填 MV1 的 8k 尖峰)、新增 11186Hz +3.16 Q0.90(宽 Q 补 9-12k)
- 4k 谷不再强行填(4045Hz +6.0Q3 → +4.85Q4):4 个 rig 实测谷底位置均为 4045Hz 但深度 -2.26~-6.27(差 2.8 倍),属腔体/耦合抵消型凹陷,加能量会被再抵消且深度不确定——实测放开 Q 到 8 只多填 0.5dB
- 代价:preamp -4.24 → -5.55(形状峰值 +5.35 @8.2k);4k 区群延迟 0.17→0.19ms(可忽略)
- 残差:3-6k 1.43 | 6-9k 0.38 | 9-11k 0.49 | 11-14k 6.78(>10k 不可验证,不再追)
★ 2026-09-11 A/B 试听判定(用户,音量对齐后):**B 版胜出** —— "空气感更好,延展性调高了";A 版"能量集中在中频"。与模型预测一致(A 在 8-11k 欠补 2.2-4.0dB → 相对中频集中)。
结论:同 rig 拟合下关闭 sanitize 高频正增益上限是有效的,B 的设置保留。
状态:未激活(试听时手动切)"""

def put(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='PUT')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8'))

# ① 写笔记(第二遍修行序)
for i in (1, 2):
    r = put('/api/preset/notes', {'id': PID, 'notes': notes})
    print(f'notes #{i} ok =', r.get('ok'))
# ② 补回 11 段(apply 保留笔记)
a = post('/api/eq/apply', {'preset': PID, 'bands': bands, 'preamp_db': PREAMP,
                           'target_id': TID, 'activate': False})
print('apply ok =', a.get('ok'), '| bands =', len(a.get('applied') or []), '| active =', a.get('active_preset_id'))

# ③ 回读
lines = open(r'F:\MIMO-Space\PEQ-WebUI\apo-presets\dt900-pro-x-mv1拟合-b.txt',
             encoding='utf-8').read().splitlines()
print('notes 行数 =', sum(1 for l in lines if l.startswith('# note:')))
print('Filter 行数 =', sum(1 for l in lines if l.startswith('Filter')))
print('末 3 行:')
for l in lines[-3:]:
    print(' ', l)
