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

SEEDS = [
    ('dt900prox-harman', 'DT900 Pro X · Harman 校准', 'dt900prox', 'harman_overear_2018'),
    ('r70x-harman', 'R70X · Harman 校准', 'r70x', 'harman_overear_2018'),
    ('fd02-harman', 'FD02 · Harman 入耳校准', 'fd02', 'harman_in-ear_2019'),
    ('e40-harman', 'E40 · Harman 入耳校准', 'e40', 'harman_in-ear_2019'),
    ('xlm-harman', '小蓝帽 · Harman 入耳校准', 'xlm', 'harman_in-ear_2019'),
    ('t100-flat', '创新 T100 · 平直', 't100', 'flat'),
]


def main():
    apo = ApoBackend()
    curves = CurveStore()
    created = []
    for preset_id, display_name, device_id, target_id in SEEDS:
        if apo.get_preset(preset_id) is not None:
            continue
        device = curves.get_device(device_id) or {}
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
            device_id=device_id,
            device_scope='Fiio',
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