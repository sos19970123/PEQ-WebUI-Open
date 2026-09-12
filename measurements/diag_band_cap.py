# -*- coding: utf-8 -*-
"""诊断: 20 段 apply 到底被谁截断"""
import json, urllib.request

bands = [
    {"type":"PK","freq":101.6,"gain_db":0.59,"q":2.569,"enabled":True},
    {"type":"PK","freq":177.77,"gain_db":-0.34,"q":2.088,"enabled":True},
    {"type":"PK","freq":301.19,"gain_db":0.29,"q":2.428,"enabled":True},
    {"type":"PK","freq":695.35,"gain_db":-0.62,"q":4,"enabled":True},
    {"type":"PK","freq":856,"gain_db":1.7,"q":0.8,"enabled":True},
    {"type":"PK","freq":1484.63,"gain_db":-1.16,"q":2.696,"enabled":True},
    {"type":"PK","freq":1843.89,"gain_db":-3.38,"q":1.896,"enabled":False},
    {"type":"PK","freq":2352.98,"gain_db":-1.07,"q":3.357,"enabled":True},
    {"type":"PK","freq":2922.37,"gain_db":0.74,"q":4,"enabled":True},
    {"type":"PK","freq":3629.56,"gain_db":-1.84,"q":4,"enabled":True},
]
print('先只发前10段(安全,不改动超限部分)... 跳过')
# 只测试: 发 20 段, 看 applied 长度
allb = bands + [
    {"type":"PK","freq":4328.16,"gain_db":4.23,"q":3.251,"enabled":True},
    {"type":"PK","freq":4694.51,"gain_db":0.86,"q":3.466,"enabled":True},
    {"type":"PK","freq":5662.92,"gain_db":0.28,"q":4,"enabled":True},
    {"type":"PK","freq":6072.72,"gain_db":1.88,"q":4,"enabled":True},
    {"type":"PK","freq":6497.81,"gain_db":2.89,"q":0.672,"enabled":True},
    {"type":"PK","freq":7340.67,"gain_db":-2.26,"q":4,"enabled":True},
    {"type":"PK","freq":8593.91,"gain_db":1.25,"q":0.774,"enabled":True},
    {"type":"PK","freq":9231.54,"gain_db":1.25,"q":0.664,"enabled":True},
    {"type":"PK","freq":10298.3,"gain_db":0.39,"q":3.871,"enabled":True},
    {"type":"LS","freq":35,"gain_db":4.8,"q":0.75,"enabled":True},
]
body = {"preset": "1-2", "preamp_db": -8.7697, "activate": False,
        "ui_state": {"auto_fit_enabled": True, "legend": {"device": True, "target": True, "eq": True, "equalized": True, "applied": False, "draft": False, "preview": False}},
        "bands": allb}
req = urllib.request.Request('http://127.0.0.1:9100/api/eq/apply',
                             data=json.dumps(body).encode('utf-8'),
                             headers={'Content-Type': 'application/json'}, method='POST')
r = json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
print('ok =', r.get('ok'))
print('sent bands =', len(allb))
print('applied len =', len(r.get('applied') or []))
ct = r.get('config_text') or ''
fl = [l for l in ct.splitlines() if l.startswith('Filter')]
print('config_text Filter 行数 =', len(fl))
print('--- 末尾3行 ---')
for l in fl[-3:]: print(' ', l)
