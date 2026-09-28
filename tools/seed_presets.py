# -*- coding: utf-8 -*-
"""
seed_presets.py - 首跑播种（幂等，已存在则跳过）

为有曲线数据的设备生成初始 APO 预设；无曲线数据建空预设占位。
用法:
  py tools/seed_presets.py
环境变量 APO_PRESET_DIR / APO_CONFIG_DIR 可覆盖。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apo_backend import ApoBackend, render_preset
from autofit import autofit
from curve_store import CurveStore

# 通用示例种子（非个人设备）。按本机曲线库自动拟合；无曲线则空预设。
# 迁移/新机请按实际耳机改写 SEEDS，勿提交个人型号到公开仓。
SEEDS = [
    ('example-harman-oe', '示例 · 头戴 Harman', 'sample-over-ear', 'harman_overear_2018'),
    ('example-harman-ie', '示例 · 入耳 Harman', 'fd02', 'harman_in-ear_2019'),
    ('example-flat', '示例 · 平直', None, 'flat'),
]


def main():
    apo = ApoBackend()
    curves = CurveStore()
    created = []
    for preset_id, display_name, device_id, target_id in SEEDS:
        if apo.get_preset(preset_id) is not None:
            continue
        device = curves.get_device(device_id) or {} if device_id else {}
        target = curves.get_target(target_id) or {}
        src = device.get('points') or []
        tgt = target.get('points') or []
        bands = []
        preamp = 0
        if len(src) >= 2 and len(tgt) >= 2:
            try:
                res = autofit(src, tgt, filters=10)
                bands = res['bands']
                preamp = res['preamp_db']
            except Exception:
                bands = []
        text = render_preset(
            bands,
            preamp,
            name=display_name,
            device_id=device_id or '',
            device_scope='all',
            generated_by='seed_presets',
        )
        path = os.path.join(apo.preset_dir, preset_id + '.txt')
        os.makedirs(apo.preset_dir, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(text.encode('utf-8'))
        created.append(preset_id)
        print(f'created {preset_id}')
    apo.list_presets()
    print('done:', created or 'nothing to create')


if __name__ == '__main__':
    main()