# -*- coding: utf-8 -*-
"""
curve_align.py - 频响曲线基准对齐工具

参考算法：
- AutoEq FrequencyResponse.center():
  * 默认将 1 kHz 点平移到 0 dB；
  * 也支持给一个频率区间，用区间内平均增益作为 0 dB 基准。
- AutoEq batch_processing.process(min_mean_error=True):
  * 在 100 Hz - 10 kHz 上把误差曲线的平均值归零，
    避免 1 kHz 单点正好落在窄峰/深谷时产生整体偏移。
- Room EQ Wizard (REW) 等工具也普遍提供以 1 kHz 或参考频段平均
  SPL 对齐目标/测量的功能。

本模块提供两类操作：
1. align_points_to_reference: 单条曲线整体平移，使参考频段平均（或参考点）为 0 dB。
2. align_error_mean: 直接对需求曲线（目标-源）在指定频段做均值归零，等价于 AutoEq min_mean_error。
"""
import numpy as np

DEFAULT_REF_LOW = 500.0
DEFAULT_REF_HIGH = 2000.0
DEFAULT_MIN_MEAN_LOW = 100.0
DEFAULT_MIN_MEAN_HIGH = 10000.0


def _interp_on_freq(points, freqs):
    """把离散 [freq, db] 点按对数频率线性插值到 freqs。"""
    if not points or len(points) < 2:
        return np.zeros_like(freqs, dtype=float)
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    logxs = np.log(np.clip(xs, 1e-6, None))
    logf = np.log(np.clip(freqs, 1e-6, None))
    return np.interp(logf, logxs, ys)


def _ref_db(points, ref_low=DEFAULT_REF_LOW, ref_high=DEFAULT_REF_HIGH, method='mean', samples=32):
    """计算曲线在参考频段的基准值。

    method:
      'mean'  - 在 [ref_low, ref_high] 内对数均匀取 samples 个点，取平均 dB。
      'point' - 取参考频段几何中心点的插值，用于兼容 AutoEq 的单点 center。
    """
    if method == 'point':
        center = float(np.sqrt(ref_low * ref_high))
        return float(_interp_on_freq(points, np.array([center]))[0])
    if ref_low >= ref_high:
        ref_low, ref_high = min(ref_low, ref_high), max(ref_low, ref_high)
    if ref_low <= 0 or ref_high <= 0:
        ref_low, ref_high = DEFAULT_REF_LOW, DEFAULT_REF_HIGH
    freqs = np.exp(np.linspace(np.log(ref_low), np.log(ref_high), int(samples)))
    vals = _interp_on_freq(points, freqs)
    return float(np.mean(vals))


def align_points_to_reference(points, ref_low=DEFAULT_REF_LOW, ref_high=DEFAULT_REF_HIGH,
                              method='mean', samples=32):
    """将单条曲线整体平移，使参考频段平均/参考点为 0 dB。

    返回 (aligned_points, offset_db)。offset_db 为从原曲线减去的基准值。
    """
    if not points or len(points) < 2:
        return list(points), 0.0
    offset = _ref_db(points, ref_low, ref_high, method, samples)
    aligned = [[float(f), float(db) - offset] for f, db in points]
    return aligned, offset


def align_error_mean(needs, freqs,
                     low=DEFAULT_MIN_MEAN_LOW, high=DEFAULT_MIN_MEAN_HIGH):
    """将需求曲线（target-source）在 [low, high] 频段内的平均值归零。

    返回 (aligned_needs, offset_db)。offset_db 为从 needs 减去的均值。
    """
    needs = np.asarray(needs, dtype=float)
    mask = (freqs >= low) & (freqs <= high)
    if not np.any(mask):
        return needs.copy(), 0.0
    offset = float(np.mean(needs[mask]))
    return needs - offset, offset


def align_curve_pair(source_points, target_points,
                     ref_low=DEFAULT_REF_LOW, ref_high=DEFAULT_REF_HIGH,
                     method='mean', min_mean_error=True,
                     min_mean_low=DEFAULT_MIN_MEAN_LOW, min_mean_high=DEFAULT_MIN_MEAN_HIGH,
                     samples=32):
    """对源/目标曲线做拟合前基准对齐。

    步骤：
    1. 若 min_mean_error=True，直接在 100Hz-10kHz 上把 target-source 的均值归零。
       这等价于 AutoEq 的 min_mean_error，可避免整体偏高/偏低导致全频段 EQ。
    2. 若 min_mean_error=False，则退回到参考频段平均对齐（AutoEq center 的区间版）。

    返回 (source_points, target_points, alignment_info)。
    为保持需求曲线不变，只平移 target_points。
    """
    # 为了计算 100Hz-10kHz 的均值，需要插值到统一对数网格。
    all_freqs = np.unique(np.concatenate([
        np.array([p[0] for p in source_points], dtype=float),
        np.array([p[0] for p in target_points], dtype=float),
    ]))
    if len(all_freqs) < 2:
        return list(source_points), list(target_points), {'offset_db': 0.0, 'min_mean_offset_db': 0.0}

    grid = np.exp(np.linspace(np.log(np.max([all_freqs.min(), 20.0])),
                              np.log(np.min([all_freqs.max(), 20000.0])), 256))
    src = _interp_on_freq(source_points, grid)
    tgt = _interp_on_freq(target_points, grid)
    needs = tgt - src

    if min_mean_error:
        needs, mean_off = align_error_mean(needs, grid, min_mean_low, min_mean_high)
        shift = mean_off
        info = {
            'method': 'min_mean_error',
            'min_mean_low': min_mean_low,
            'min_mean_high': min_mean_high,
            'offset_db': round(shift, 4),
            'min_mean_offset_db': round(shift, 4),
        }
    else:
        mask = (grid >= ref_low) & (grid <= ref_high)
        ref_off = float(np.mean(needs[mask])) if np.any(mask) else 0.0
        shift = ref_off
        info = {
            'method': method,
            'ref_low': ref_low,
            'ref_high': ref_high,
            'offset_db': round(shift, 4),
            'min_mean_offset_db': 0.0,
        }

    # 平移只作用于目标曲线，保持源曲线原始数据不变。
    aligned_target = [[float(f), float(db) - shift] for f, db in target_points]
    return list(source_points), aligned_target, info


if __name__ == '__main__':
    src = [[20, 5], [100, 4], [1000, 2], [5000, 3], [20000, 1]]
    tgt = [[20, 0], [100, 0], [1000, 0], [5000, 0], [20000, 0]]
    print('align points:', align_points_to_reference(src))
    print('align pair:', align_curve_pair(src, tgt))
