# -*- coding: utf-8 -*-
"""rig_guard.py - 拟合的跨 rig 防护（需求 R2/R3）

目标曲线与设备频响来自不同测量 rig 时，9kHz 以上差异可能属于测量系统
而非耳机本身。本模块只做“判定 + 文案 + 默认上限”，不依赖 Web 层，便于单测。
"""

CROSS_RIG_FMAX = 7000.0
CROSS_RIG_HZ = 9000.0

# family key 用于判断“是否同一类测量系统”。
# 注意顺序：显式 rig 关键字优先，Harman 仅在没有其它关键字时作为 oratory 目标兜底。
_FAMILY_PATTERNS = (
    ('oratory', ('45bc', '43ag', '43ac', 'oratory1990', 'kearm')),
    ('5128', ('5128',)),
    ('hms', ('hms', 'ii.3')),
    ('711', ('711', '60318')),
    ('ears', ('ears',)),
    ('diffuse', ('diffuse',)),
)


def rig_family_key(*values):
    """从任意包含 rig/来源/名称的字段推导测量系统类别。"""
    parts = [str(v) for v in values if v not in (None, '')]
    if not parts:
        return ''
    low = ' '.join(parts).lower()
    for key, patterns in _FAMILY_PATTERNS:
        if any(p in low for p in patterns):
            return key
    # 目标曲线经常只写“Harman 2018”而没有 rig 字段：Harman 曲线基准与
    # oratory/GRAS 同源，按 oratory 处理，避免把同基准拟合误报为跨 rig。
    if 'harman' in low:
        return 'oratory'
    return ''


def curve_rig_info(curve):
    """返回曲线 JSON 的 rig 摘要（family 统一归一化为 canonical key）。"""
    curve = curve or {}
    rig = str(curve.get('rig') or curve.get('measurement_rig') or '').strip()
    family = rig_family_key(
        rig,
        curve.get('rig_family'),
        curve.get('rig_standard'),
        curve.get('source'),
        curve.get('variant'),
        curve.get('measurement_source'),
        curve.get('name'),
        curve.get('id'),
    )
    source = str(
        curve.get('measurement_source')
        or curve.get('variant')
        or curve.get('source')
        or ''
    ).strip()
    return {
        'rig': rig,
        'family': family,
        'source': source,
        'name': str(curve.get('name') or curve.get('id') or '').strip(),
    }


def source_label(info):
    return info.get('source') or info.get('name') or '未知来源'


def check_cross_rig(device, target):
    """比较设备与目标曲线的 rig。

    返回 dict:
      cross     : 两侧 rig 已知且不同类
      unknown   : 至少一侧 rig 缺失，无法判断可比性
      warnings  : 可直接追加到 autofit 响应的中文提示
    """
    d = curve_rig_info(device)
    t = curve_rig_info(target)
    result = {
        'cross': False,
        'unknown': False,
        'device_rig': d['rig'],
        'target_rig': t['rig'],
        'device_family': d['family'],
        'target_family': t['family'],
        'device_source': source_label(d),
        'target_source': source_label(t),
        'warnings': [],
    }

    if not d['rig'] and not t['rig']:
        result['unknown'] = True
        result['warnings'].append('未知 rig，无法判断可比性：设备与目标曲线都没有 rig 元数据，9kHz 以上结果不可验证。')
        return result
    if not d['rig']:
        result['unknown'] = True
        result['warnings'].append(
            f'无法判断可比性：设备 rig 未知；目标来自 {source_label(t)}（{t["rig"]}）。9kHz 以上结果不可验证。'
        )
        return result
    if not t['rig']:
        result['unknown'] = True
        result['warnings'].append(
            f'无法判断可比性：目标 rig 未知；设备来自 {source_label(d)}（{d["rig"]}）。9kHz 以上结果不可验证。'
        )
        return result

    if d['family'] and t['family'] and d['family'] != t['family']:
        result['cross'] = True
        result['warnings'].append(
            f'跨 rig 拟合：目标来自 {source_label(t)}（{t["rig"]}），'
            f'设备来自 {source_label(d)}（{d["rig"]}）。'
            f'9kHz 以上差异可能属测量系统而非耳机，建议 fmax ≤ {int(CROSS_RIG_FMAX)}Hz'
        )
    elif not (d['family'] and t['family']):
        # 两侧都有 rig 字符串，但有一侧无法归类：无法确认可比性，给出降级提示
        # （不强制收敛 fmax，避免误伤普通目标曲线）。
        norm = lambda s: str(s or '').strip().lower()
        if norm(d['rig']) != norm(t['rig']):
            result['unknown'] = True
            result['warnings'].append(
                f'无法判断可比性：设备 rig “{d["rig"]}” 与目标 rig “{t["rig"]}” 不同且无法归类，'
                f'9kHz 以上结果不可验证；建议 fmax ≤ {int(CROSS_RIG_FMAX)}Hz。'
            )
    return result
