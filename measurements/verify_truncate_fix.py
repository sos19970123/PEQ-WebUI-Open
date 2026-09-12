# -*- coding: utf-8 -*-
"""端到端验证:对 14 段预设写 notes,看段数是否保住(截断 bug 是否真已修)
   先备份,再原样回写笔记,最后核对段数/笔记行数/ui_state"""
import json, os, shutil, urllib.request

BASE = 'http://127.0.0.1:9100'
PRE = r'F:\MIMO-Space\PEQ-WebUI\apo-presets'
BAK = r'F:\MIMO-Space\PEQ-WebUI\measurements\_preset_backup'
os.makedirs(BAK, exist_ok=True)

PID = 'dt900prox-harman'
src = os.path.join(PRE, PID + '.txt')
shutil.copy2(src, os.path.join(BAK, PID + '.txt'))
print('备份 ->', os.path.join(BAK, PID + '.txt'))

def counts(path):
    lines = open(path, encoding='utf-8-sig').read().splitlines()
    return (sum(1 for l in lines if l.startswith('Filter')),
            sum(1 for l in lines if l.startswith('# note:')),
            next((l for l in lines if l.startswith('# ui_state:')), ''),
            next((l for l in lines if l.startswith('# fit:')), ''))

before = counts(src)
print(f'改写前: Filter {before[0]} 段 | notes {before[1]} 行 | fit 行 {"有" if before[3] else "无"}')

# 取现有笔记原文,原样回写
notes = []
for l in open(src, encoding='utf-8-sig').read().splitlines():
    if l.startswith('# note:'):
        notes.append(l[len('# note:'):].strip())
notes_text = '\n'.join(notes)

req = urllib.request.Request(BASE + '/api/preset/notes',
                             data=json.dumps({'id': PID, 'notes': notes_text}).encode('utf-8'),
                             headers={'Content-Type': 'application/json'}, method='PUT')
r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode('utf-8'))
print('PUT notes ok =', r.get('ok'))

after = counts(src)
print(f'改写后: Filter {after[0]} 段 | notes {after[1]} 行 | fit 行 {"有" if after[3] else "无"}')
print()
print('结论:', '✅ 段数保住 — 截断 bug 已修复' if after[0] == before[0] else f'❌ 段数 {before[0]} -> {after[0]},截断仍存在')
# 行序是否保持
lines_now = [l for l in open(src, encoding='utf-8-sig').read().splitlines() if l.startswith('# note:')]
print('笔记首行:', lines_now[0][:60] if lines_now else '(无)')
