# -*- coding: utf-8 -*-
"""curve_adjust.py - 目标曲线快速整形工具。

在自动拟合前对目标曲线做参数化调整：
- amount: 0~1，原始设备曲线与目标曲线之间插值
- bass_db: 低频整体增益（低架形状，约 200Hz 以下）
- treble_db: 高频整体增益（高架形状，约 5kHz 以上）
- tilt_db: 每倍频程倾斜（以 1kHz 为参考，正值高频增加）
"""
import numpy as np

from autofit import F_MIN, F_MAX, _log_grid, _interp, _rbj_mag_db

ADJUST_GRID_N = 512
BASS_FC = 200.0
BASS_Q = 0.7
TREBLE_FC = 5000.0
TREBLE_Q = 0.7
TILT_REF = 1000.0


def _clamp(v, lo=0.0, hi=1.0):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


def apply_target_adjust(source_points, target_points, adjust=None):
    """返回调整后的目标曲线点列表 [[freq, db], ...]。"""
    if not adjust:
        return list(target_points or [])

    grid = _log_grid(F_MIN, F_MAX, ADJUST_GRID_N)
    src = _interp(source_points or [], grid)
    tgt = _interp(target_points or [], grid)

    amount = _clamp(adjust.get('amount', 1.0) if adjust.get('amount') is not None else 1.0)
    out = src + amount * (tgt - src)

    try:
        bass_db = float(adjust.get('bass_db') or 0.0)
    except (TypeError, ValueError):
        bass_db = 0.0
    if abs(bass_db) > 0.001:
        out += _rbj_mag_db(grid, 'LS', BASS_FC, bass_db, BASS_Q)

    try:
        treble_db = float(adjust.get('treble_db') or 0.0)
    except (TypeError, ValueError):
        treble_db = 0.0
    if abs(treble_db) > 0.001:
        out += _rbj_mag_db(grid, 'HS', TREBLE_FC, treble_db, TREBLE_Q)

    try:
        tilt_db = float(adjust.get('tilt_db') or 0.0)
    except (TypeError, ValueError):
        tilt_db = 0.0
    if abs(tilt_db) > 0.001:
        out += tilt_db * np.log2(np.clip(grid, F_MIN, F_MAX) / TILT_REF)

    out = np.clip(out, -60.0, 60.0)
    return [[float(f), float(db)] for f, db in zip(grid, out)]


if __name__ == '__main__':
    src = [[20, 0], [1000, 0], [20000, 0]]
    tgt = [[20, 0], [1000, 0], [20000, 0]]
    pts = apply_target_adjust(src, tgt, {'amount': 1.0, 'bass_db': 2.0, 'treble_db': -1.0, 'tilt_db': 0.5})
    print(len(pts), pts[0], pts[-1])
