# -*- coding: utf-8 -*-
"""实证 bug B:新建临时预设 -> 首次写多行 notes -> 检查行序 -> 删除临时预设"""
import json, os, urllib.request, urllib.parse

BASE = 'http://127.0.0.1:9100'
PRE = r'F:\MIMO-Space\PEQ-WebUI\apo-presets'

def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))

def put(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='PUT')
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))

r = post('/api/preset/add', {'name': 'ZZ临时测试预设', 'device_id': ''})
pid = (r.get('preset') or {}).get('id')
print('临时预设 id =', pid)

notes = "第1行:甲\n第2行:乙\n第3行:丙\n第4行:丁"
put('/api/preset/notes', {'id': pid, 'notes': notes})

path = os.path.join(PRE, pid + '.txt')
got = [l[len('# note:'):].strip() for l in open(path, encoding='utf-8').read().splitlines() if l.startswith('# note:')]
print('写入顺序 :', notes.split('\n'))
print('文件顺序 :', got)
print('结论:', '✅ 顺序正确(bug B 已修)' if got == notes.split('\n') else '❌ 行序被倒置(bug B 仍存在)')

post('/api/preset/del', {'id': pid})
print('已删除临时预设,存在?', os.path.exists(path))
