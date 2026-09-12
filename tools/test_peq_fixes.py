# -*- coding: utf-8 -*-
"""test_peq_fixes.py - 跨 rig 拟合防护 + 预设元数据不截断的回归自检。

运行:
  py tools/test_peq_fixes.py

不依赖 pytest；只用标准库 + 项目模块。断言失败会抛 AssertionError。
"""
import os
import shutil
import sys
import tempfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from apo_backend import ApoBackend  # noqa: E402
from curve_store import CurveStore  # noqa: E402
from eq_parser import parse_eq  # noqa: E402
from rig_guard import check_cross_rig  # noqa: E402

SAMPLE_PRESET = """# name: R70X · HD490PRO 拟合
# device: r70x
# target: sennheiser-hd-490-pro-原始频响
# fit: {"fmin":100,"fmax":12000}
# ui_state: {"auto_fit_enabled":true}
# note: 原笔记
# generated: 2020-01-01T00:00:00 by mixer_web

Device: Fiio
Preamp: -8.5 dB

__BANDS__
"""


def make_bands(n=20, off_index=7):
    lines = []
    for i in range(1, n + 1):
        state = 'OFF' if i == off_index else 'ON'
        lines.append(f'Filter {i}: {state} PK Fc {100 + i * 10} Hz Gain {1.0 if i % 2 else -1.0} dB Q 1.0')
    lines.append('Filter 21: ON LS Fc 35 Hz Gain 4.8 dB Q 0.75')  # 故意多一段，模拟 21 段
    return '\n'.join(lines)


def count_filters(text):
    return sum(1 for line in text.splitlines() if line.startswith('Filter '))


def test_parse_eq_no_truncation():
    text = make_bands(20)
    parsed = parse_eq(text, max_bands=None)
    assert len(parsed['bands']) == 21, len(parsed['bands'])
    parsed_capped = parse_eq(text, max_bands=20)
    assert len(parsed_capped['bands']) == 20
    print('[ok] parse_eq max_bands 可关闭截断')


def test_update_preset_meta_preserves_filters():
    tmp = tempfile.mkdtemp(prefix='peq_meta_test_')
    try:
        preset_dir = os.path.join(tmp, 'presets')
        config_dir = os.path.join(tmp, 'config')
        os.makedirs(preset_dir)
        os.makedirs(config_dir)
        path = os.path.join(preset_dir, '1-2.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_PRESET.replace('__BANDS__', make_bands(20)))
        be = ApoBackend(preset_dir=preset_dir, config_dir=config_dir)
        before = open(path, encoding='utf-8').read()
        updated = be.update_preset_meta('1-2', notes='新笔记 A\n新笔记 B')
        assert updated is not None
        assert len(updated['bands']) == 21, len(updated['bands'])
        after = open(path, encoding='utf-8').read()
        assert count_filters(after) == 21, count_filters(after)
        assert 'Filter 7: OFF' in after, 'Filter 7 的 OFF 状态被改坏'
        assert 'Preamp: -8.5 dB' in after, 'Preamp 被改坏'
        assert 'Device: Fiio' in after, 'Device 行被改坏'
        assert '新笔记 A' in after and '原笔记' not in after
        assert '# fit: {"fmin":100,"fmax":12000}' in after, '# fit 被丢失'
        assert '# ui_state: {"auto_fit_enabled":true}' in after, '# ui_state 被丢失'
        before_filter_lines = [l for l in before.splitlines() if l.startswith('Filter ')]
        after_filter_lines = [l for l in after.splitlines() if l.startswith('Filter ')]
        assert before_filter_lines == after_filter_lines, 'Filter 行发生变化'
        print('[ok] update_preset_meta 只改元数据，Filter/Preamp/Device 原样保留')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_note_order_and_clear():
    tmp = tempfile.mkdtemp(prefix='peq_note_order_test_')
    try:
        preset_dir = os.path.join(tmp, 'presets')
        config_dir = os.path.join(tmp, 'config')
        os.makedirs(preset_dir)
        os.makedirs(config_dir)
        be = ApoBackend(preset_dir=preset_dir, config_dir=config_dir)
        p = be.create_preset('Note Order Test')
        preset_id = p['id']
        bands = parse_eq(make_bands(20), max_bands=None)['bands']
        assert be.update_preset(preset_id, bands, preamp_db=-6.0, auto_preamp=False) is not None
        path = os.path.join(preset_dir, preset_id + '.txt')

        # 1) 首次写多行笔记，文件中的 # note: 行必须与输入同序
        updated = be.update_preset_meta(preset_id, notes='1\n2\n3\n4')
        assert updated is not None
        text = open(path, encoding='utf-8').read()
        note_lines = [line for line in text.splitlines() if line.startswith('# note:')]
        assert note_lines == ['# note: 1', '# note: 2', '# note: 3', '# note: 4'], note_lines

        # 2) 同样内容再写一遍仍稳定，不能重复或倒置
        updated = be.update_preset_meta(preset_id, notes='1\n2\n3\n4')
        assert updated is not None
        text = open(path, encoding='utf-8').read()
        note_lines = [line for line in text.splitlines() if line.startswith('# note:')]
        assert note_lines == ['# note: 1', '# note: 2', '# note: 3', '# note: 4'], note_lines

        # 3) 已有笔记时用新内容完全替换，旧行不能残留
        updated = be.update_preset_meta(preset_id, notes='A\nB')
        assert updated is not None
        text = open(path, encoding='utf-8').read()
        note_lines = [line for line in text.splitlines() if line.startswith('# note:')]
        assert note_lines == ['# note: A', '# note: B'], note_lines
        assert '# note: 1' not in text, text

        # 4) 清空 notes 只删 # note:，Filter/Preamp/Device 不变
        filter_lines_before = [line for line in text.splitlines() if line.startswith('Filter ')]
        updated = be.update_preset_meta(preset_id, notes='')
        assert updated is not None
        text = open(path, encoding='utf-8').read()
        assert not [line for line in text.splitlines() if line.startswith('# note:')], text
        filter_lines_after = [line for line in text.splitlines() if line.startswith('Filter ')]
        assert filter_lines_after == filter_lines_before, '清空笔记不应改动 Filter 行'
        assert len(updated['bands']) == 21, len(updated['bands'])
        print('[ok] 首次写笔记顺序正确；重写幂等；旧笔记完全替换；清空笔记不动 bands')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_metadata_interfaces_preserve_bands():
    tmp = tempfile.mkdtemp(prefix='peq_meta_iface_test_')
    try:
        preset_dir = os.path.join(tmp, 'presets')
        config_dir = os.path.join(tmp, 'config')
        os.makedirs(preset_dir)
        os.makedirs(config_dir)
        path = os.path.join(preset_dir, '1-2.txt')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(SAMPLE_PRESET.replace('__BANDS__', make_bands(20)))
        be = ApoBackend(preset_dir=preset_dir, config_dir=config_dir)
        before_filter_lines = [line for line in open(path, encoding='utf-8').read().splitlines()
                               if line.startswith('Filter ')]

        # 四个元数据接口路径均只改元数据；这里用同一后端方法覆盖 notes/device/target/rename
        cases = [
            ('notes', {'notes': '新笔记 A\n新笔记 B'}),
            ('device', {'device_id': 'new-device'}),
            ('target', {'target_id': 'new-target'}),
            ('rename', {'name': 'New Name'}),
        ]
        for label, kwargs in cases:
            updated = be.update_preset_meta('1-2', **kwargs)
            assert updated is not None, label
            assert len(updated['bands']) == 21, (label, len(updated['bands']))
            after_text = open(path, encoding='utf-8').read()
            after_filter_lines = [line for line in after_text.splitlines() if line.startswith('Filter ')]
            assert count_filters(after_text) == 21, (label, count_filters(after_text))
            assert after_filter_lines == before_filter_lines, f'{label} 改动了 Filter 行'
        print('[ok] notes/device/target/rename 四条元数据路径均保留 21 段 bands')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_auto_preamp_on_save():
    tmp = tempfile.mkdtemp(prefix='peq_preamp_test_')
    try:
        preset_dir = os.path.join(tmp, 'presets')
        config_dir = os.path.join(tmp, 'config')
        os.makedirs(preset_dir)
        os.makedirs(config_dir)
        be = ApoBackend(preset_dir=preset_dir, config_dir=config_dir)
        p = be.create_preset('Auto Preamp Test')
        bands = [{'type': 'PK', 'freq': 1000, 'gain': 6, 'q': 1, 'enabled': True}]
        updated = be.update_preset(p['id'], bands, preamp_db=0.0)
        assert updated is not None
        assert -6.25 < updated['preamp_db'] < -6.15, updated['preamp_db']
        # 撤销/回退路径必须能原样写回历史 Preamp，而不是再次自动计算
        restored = be.update_preset(p['id'], bands, preamp_db=-3.3, auto_preamp=False)
        assert restored is not None
        assert abs(restored['preamp_db'] - (-3.3)) < 1e-6, restored['preamp_db']
        print('[ok] 保存时自动计算 Preamp，回退时保留历史 Preamp')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_rig_guard():
    cs = CurveStore()
    dev = cs.get_device('r70x')
    cross_target = cs.get_target('sennheiser-hd-490-pro-原始频响')
    same_target = cs.get_target('audio-technica-ath-r70xa-target')
    r1 = check_cross_rig(dev, cross_target)
    assert r1['cross'] is True and r1['unknown'] is False, r1
    assert '9kHz' in r1['warnings'][0]
    r2 = check_cross_rig(dev, same_target)
    assert r2['cross'] is False and r2['unknown'] is False, r2
    print('[ok] check_cross_rig 跨 rig / 同 rig 判定正确')


def test_rig_diff():
    cs = CurveStore()
    diff = cs.rig_diff('r70x', rig_from='Rtings HMS II.3', rig_to='oratory1990 GRAS 45BC-10')
    assert diff is not None
    assert diff['from_id'] == 'r70x-rtings', diff['from_id']
    assert diff['to_id'] == 'r70x'
    assert len(diff['points']) >= 100
    hi = [p[1] for p in diff['points'] if 9000 <= p[0] <= 14000]
    assert hi and abs(sum(hi) / len(hi)) > 1.0, '9-14k 应有明显 rig 差'
    print('[ok] rig_diff 能算出同型号双 rig 实测差')


def main():
    test_parse_eq_no_truncation()
    test_update_preset_meta_preserves_filters()
    test_note_order_and_clear()
    test_metadata_interfaces_preserve_bands()
    test_auto_preamp_on_save()
    test_rig_guard()
    test_rig_diff()
    print('\n全部自检通过')


if __name__ == '__main__':
    main()
