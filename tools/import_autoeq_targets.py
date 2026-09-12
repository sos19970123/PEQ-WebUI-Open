# -*- coding: utf-8 -*-
"""
import_autoeq_targets.py - 从 AutoEq 源码导入目标曲线到 WebUI 曲线库

用法:
  py tools/import_autoeq_targets.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autoeq_store import AutoEqStore

CURVES_TARGETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'curves', 'targets')


def main():
    os.makedirs(CURVES_TARGETS, exist_ok=True)
    store = AutoEqStore()
    targets = store.read_targets()
    imported = []
    for t in targets:
        path = os.path.join(CURVES_TARGETS, t['id'] + '.json')
        if os.path.exists(path):
            continue
        with open(path, 'wb') as f:
            f.write(json.dumps(t, ensure_ascii=False, indent=2).encode('utf-8'))
        imported.append(t['id'])
    print('imported:', imported or 'nothing to do')


if __name__ == '__main__':
    main()