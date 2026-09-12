# -*- coding: utf-8 -*-
"""扫描所有预设的 legend 开关状态(只读,不写)"""
import json, os

PRE = r'F:\MIMO-Space\PEQ-WebUI\apo-presets'
NEED = ('device', 'target', 'eq', 'equalized')

rows = []
for fn in sorted(os.listdir(PRE)):
    if not fn.endswith('.txt') or fn in ('hl-active.txt', 'config.txt'):
        continue
    path = os.path.join(PRE, fn)
    legend = None
    name = ''
    for line in open(path, encoding='utf-8-sig', errors='replace').read().splitlines():
        if line.startswith('# name:'):
            name = line.split(':', 1)[1].strip()
        if line.startswith('# ui_state:'):
            try:
                legend = json.loads(line.split(':', 1)[1].strip()).get('legend') or {}
            except Exception:
                legend = {}
            break
    if legend is None:
        legend = {}
    ok = all(legend.get(k) for k in NEED)
    rows.append((fn, name, ok, sum(1 for k in NEED if legend.get(k)), legend))

print(f'{"文件":<34} {"名称":<26} {"四项全开":<8}')
print('-' * 78)
for fn, name, ok, cnt, lg in rows:
    print(f'{fn:<34} {name[:24]:<26} {("✅" if ok else f"❌ {cnt}/4"):<8}')
bad = [fn for fn, _, ok, _, _ in rows if not ok]
print()
print('缺显示开关的预设:', bad if bad else '(无)')
