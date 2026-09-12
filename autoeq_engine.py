# -*- coding: utf-8 -*-
"""
autoeq_engine.py - 精确模式（方案 B1：本地 AutoEq 4.1.2 优化器适配）

仅当 scipy 可用时启用；scipy/matplotlib/tabulate 缺失时不启用（详见 PRECISE_AVAILABLE）。
默认 AutoEq 根目录与 autoeq_store.py 一致，可用环境变量 AUTOEQ_ROOT 覆盖。

输出 schema 与 autofit.autofit() 完全一致：{bands, rms_db, preamp_db, warnings, engine}
"""
import os
import sys
import types

import numpy as np

from autofit import (
    F_MIN, F_MAX, GRID_N, DEFAULT_SAMPLE_RATE,
    _log_grid, _interp, _rms_db, _dedupe_bands,
    _smooth_with_sigma, sanitize_bands, _make_weights,
)

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AUTOEQ_ROOT = os.path.normpath(
    os.path.join(_PROJECT_ROOT, '..', 'AutoEq-4.1.2', 'AutoEq-4.1.2')
)
PRECISE_GRID_N = 1024  # 比快速模式 256 点更密，供 SLSQP 精确寻优
PRECISE_AVAILABLE = False
PRECISE_IMPORT_ERROR = ''
_PEQ_CLASS = None


def _install_optional_stubs():
    """AutoEq peq.py 顶部 import matplotlib/tabulate，但 optimize() 并不需要它们。

    如果 scipy 已安装而这两个绘图/表格库缺失，用最小 stub 让优化器可导入。
    """
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        mpl = types.ModuleType('matplotlib')
        pyplot = types.ModuleType('matplotlib.pyplot')
        ticker = types.ModuleType('matplotlib.ticker')
        def _unsupported(*args, **kwargs):
            raise RuntimeError('matplotlib is not available; plotting is unsupported')
        pyplot.subplots = _unsupported
        pyplot.plot = _unsupported
        pyplot.semilogx = _unsupported
        pyplot.fill_between = _unsupported
        pyplot.legend = _unsupported
        pyplot.grid = _unsupported
        pyplot.xaxis = None
        mpl.pyplot = pyplot
        mpl.ticker = ticker
        sys.modules.setdefault('matplotlib', mpl)
        sys.modules.setdefault('matplotlib.pyplot', pyplot)
        sys.modules.setdefault('matplotlib.ticker', ticker)
    try:
        import tabulate  # noqa: F401
    except ImportError:
        tab = types.ModuleType('tabulate')
        tab.tabulate = lambda *args, **kwargs: ''
        sys.modules.setdefault('tabulate', tab)


def _load_precise():
    global PRECISE_AVAILABLE, PRECISE_IMPORT_ERROR, _PEQ_CLASS
    try:
        import scipy  # noqa: F401
    except Exception as exc:
        PRECISE_IMPORT_ERROR = f'scipy 不可用: {exc}'
        return
    _install_optional_stubs()
    root = os.environ.get('AUTOEQ_ROOT', DEFAULT_AUTOEQ_ROOT)
    if os.path.isdir(root) and root not in sys.path:
        sys.path.insert(0, root)
    try:
        from autoeq.peq import PEQ
        _PEQ_CLASS = PEQ
        PRECISE_AVAILABLE = True
    except Exception as exc:
        PRECISE_IMPORT_ERROR = f'AutoEq peq.py 导入失败: {exc}'


_load_precise()

_TYPE_MAP = {'Peaking': 'PK', 'LowShelf': 'LS', 'HighShelf': 'HS'}




if _PEQ_CLASS is not None:
    class _PointwisePEQ(_PEQ_CLASS):
        """精确引擎的高保真变体：不做 10kHz 以上均值化，保留逐点高频拟合。"""

        def _optimizer_loss(self, params, parse=True):
            if parse:
                self._parse_optimizer_params(params)
            fr = self.fr.copy()
            target = self.target.copy()
            # 高保真模式：不做 10kHz 均值化，也不加 sharpness 惩罚；
            # 让 SLSQP 可以像快速引擎一样去追 10kHz 后峰形和更低的纯 RMS。
            loss_val = np.mean(np.square(target[self._min_f_ix:self._max_f_ix] - fr[self._min_f_ix:self._max_f_ix]))
            return np.sqrt(loss_val)

    class _WeightedPEQ(_PEQ_CLASS):
        """精确引擎的感知加权变体：在 AutoEq 默认损失基础上加入频段权重。"""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._weights = None
            self._pointwise_hi = False

        def _optimizer_loss(self, params, parse=True):
            if parse:
                self._parse_optimizer_params(params)
            fr = self.fr.copy()
            target = self.target.copy()
            if not self._pointwise_hi:
                # 保持 AutoEq 默认：10kHz 以上只看总能量
                target[self._10k_ix:] = np.mean(target[self._10k_ix:])
                fr[self._10k_ix:] = np.mean(fr[self._10k_ix:])
            err = target[self._min_f_ix:self._max_f_ix] - fr[self._min_f_ix:self._max_f_ix]
            if self._weights is not None:
                w = self._weights[self._min_f_ix:self._max_f_ix]
                loss_val = np.mean(np.square(err * w))
            else:
                loss_val = np.mean(np.square(err))
            for filt in self.filters:
                loss_val += filt.sharpness_penalty
            return np.sqrt(loss_val)
else:
    _PointwisePEQ = None
    _WeightedPEQ = None


def autofit_precise(source_points, target_points,
                    filters=10, fmin=100.0, fmax=12000.0,
                    max_gain_db=12.0, max_q=6.0, sample_rate=DEFAULT_SAMPLE_RATE,
                    auto_shelf=False, max_time=None, hi_fidelity=False,
                    smooth_oct=0.0, sanitize=False,
                    align=True, align_ref_low=500.0, align_ref_high=2000.0,
                    min_mean_error=True, min_mean_low=100.0, min_mean_high=10000.0,
                    weight_profile='none'):
    """AutoEq SLSQP 联合优化。scipy 缺失时抛 RuntimeError，由 mixer_web 回退快速模式。"""
    if not PRECISE_AVAILABLE or _PEQ_CLASS is None:
        raise RuntimeError(PRECISE_IMPORT_ERROR or '精确引擎不可用')
    use_weighted = weight_profile and weight_profile != 'none'
    if use_weighted and _WeightedPEQ is not None:
        PEQ = _WeightedPEQ
    else:
        PEQ = _PointwisePEQ if hi_fidelity else _PEQ_CLASS

    full_grid = _log_grid(F_MIN, F_MAX, PRECISE_GRID_N)
    source = _interp(source_points, full_grid)
    target = _interp(target_points, full_grid)
    need_full = target - source
    alignment_info = {}
    if align:
        # 与快速引擎保持一致：默认用 AutoEq min_mean_error 风格，
        # 在 100Hz-10kHz 内把需求曲线均值归零；也可退回参考频段平均对齐。
        if min_mean_error:
            mm_mask = (full_grid >= min_mean_low) & (full_grid <= min_mean_high)
            if np.any(mm_mask):
                mean_off = float(np.mean(need_full[mm_mask]))
                need_full = need_full - mean_off
                alignment_info['method'] = 'min_mean_error'
                alignment_info['min_mean_low'] = float(min_mean_low)
                alignment_info['min_mean_high'] = float(min_mean_high)
                alignment_info['offset_db'] = round(mean_off, 4)
                alignment_info['min_mean_offset_db'] = round(mean_off, 4)
        else:
            ref_mask = (full_grid >= align_ref_low) & (full_grid <= align_ref_high)
            if np.any(ref_mask):
                ref_off = float(np.mean(need_full[ref_mask]))
                need_full = need_full - ref_off
                alignment_info['method'] = 'ref_band_mean'
                alignment_info['ref_low'] = float(align_ref_low)
                alignment_info['ref_high'] = float(align_ref_high)
                alignment_info['offset_db'] = round(ref_off, 4)

    mask = (full_grid >= fmin) & (full_grid <= fmax)
    grid_fit = full_grid[mask]
    need_fit = need_full[mask]

    # 精确引擎也支持拟合前平滑：只平滑拟合区间，边缘外的目标保持原样。
    need_opt = need_full.copy()
    if smooth_oct and smooth_oct > 0:
        if len(grid_fit) > 2:
            f_step = grid_fit[1] / grid_fit[0]
            indices_per_oct = 1.0 / np.log2(f_step)
            sigma_grid = float(smooth_oct) * indices_per_oct
            need_opt[mask] = _smooth_with_sigma(need_fit, sigma_grid)

    n = int(max(1, min(20, filters or 10)))
    max_gain = float(max_gain_db)
    max_q = float(max_q)
    if max_time is None or max_time <= 0:
        max_time = 5.0 + n * 0.5
    max_time = float(max_time)
    fmin, fmax = float(fmin), float(fmax)
    if fmin >= fmax:
        fmin, fmax = fmax, fmin
    fmin = float(max(F_MIN, min(fmin, F_MAX)))
    fmax = float(max(F_MIN, min(fmax, F_MAX)))
    if fmin >= fmax:
        fmin, fmax = F_MIN, F_MAX

    filter_configs = []
    pk_min_fc = max(20.0, fmin)
    if hi_fidelity:
        # 高保真模式允许 PK 追到用户 fmax，用于拟合 10kHz 以后的明确峰形。
        pk_max_fc = min(fmax, F_MAX)
    else:
        pk_max_fc = min(10000.0, fmax)
    if pk_min_fc > pk_max_fc:
        # 用户只想拟合 10kHz 以上时，PK 固定在 AutoEq 默认上限 10kHz，交给均值能量处理。
        pk_min_fc = pk_max_fc = 10000.0
    for _ in range(n):
        filter_configs.append({
            'type': 'PEAKING',
            'min_fc': pk_min_fc,
            'max_fc': pk_max_fc,
            'min_q': min(0.18248, max_q),
            'max_q': max_q,
            'min_gain': -max_gain,
            'max_gain': max_gain,
        })

    if auto_shelf and n >= 4:
        ls_lo = max(20.0, fmin)
        ls_hi = min(600.0, fmax)
        hs_lo = max(6000.0, fmin)
        hs_hi = min(12000.0, fmax)
        shelf_configs = []
        if ls_lo < ls_hi:
            shelf_configs.append({
                'type': 'LOW_SHELF',
                'min_fc': ls_lo,
                'max_fc': ls_hi,
                'q': min(0.7, max_q),
                'min_gain': -max_gain,
                'max_gain': max_gain,
            })
        if hs_lo < hs_hi:
            shelf_configs.append({
                'type': 'HIGH_SHELF',
                'min_fc': hs_lo,
                'max_fc': hs_hi,
                'q': min(0.7, max_q),
                'min_gain': -max_gain,
                'max_gain': max_gain,
            })
        # 与评估文档 P2 一致：LS 限制在低频，HS 限制在高频，并固定 Q 防退化。
        filter_configs = shelf_configs + [dict(c) for c in filter_configs[:max(0, n - len(shelf_configs))]]

    config = {
        'optimizer': {
            'min_f': fmin,
            'max_f': fmax,
            'min_std': 0.002,
            'max_time': max_time,
        },
        'filters': filter_configs,
    }
    peq = PEQ.from_dict(config, full_grid, sample_rate, target=need_opt)
    if use_weighted and isinstance(peq, _WeightedPEQ):
        peq._weights = _make_weights(full_grid, weight_profile)
        peq._pointwise_hi = bool(hi_fidelity)
    peq.optimize()

    bands = []
    for filt in peq.filters:
        bands.append({
            'type': _TYPE_MAP[filt.__class__.__name__],
            'freq': round(float(filt.fc), 2),
            'gain_db': round(float(filt.gain), 2),
            'q': round(float(filt.q), 3),
            'enabled': abs(float(filt.gain)) > 0.01,
        })
    bands = _dedupe_bands(bands, max_gain=max_gain)

    if sanitize:
        bands = sanitize_bands(bands, max_gain=max_gain)

    if bands:
        btypes = [b['type'] for b in bands]
        bfcs = [b['freq'] for b in bands]
        bgains = [b['gain_db'] for b in bands]
        bqs = [b['q'] for b in bands]
        rms = _rms_db(grid_fit, need_fit, btypes, bfcs, bgains, bqs, sr=sample_rate)
    else:
        rms = float(np.sqrt(np.mean(need_fit ** 2)))

    bands.sort(key=lambda b: b['freq'])
    if bands:
        btypes = [b['type'] for b in bands]
        bfcs = [b['freq'] for b in bands]
        bgains = [b['gain_db'] for b in bands]
        bqs = [b['q'] for b in bands]
        from autofit import _exact_sum, PREAMP_HEADROOM
        pred = _exact_sum(grid_fit, btypes, bfcs, bgains, bqs, sr=sample_rate)
        max_positive = float(np.max(pred)) if len(pred) else 0.0
    else:
        max_positive = 0.0
    preamp_db = -max(0.0, max_positive + PREAMP_HEADROOM)
    weights = _make_weights(full_grid, weight_profile) if use_weighted else None
    weighted_rms = rms
    if weights is not None and bands:
        weighted_rms = _rms_db(grid_fit, need_fit, btypes, bfcs, bgains, bqs, sr=sample_rate, weights=weights[:len(grid_fit)])
    return {
        'bands': bands,
        'rms_db': round(rms, 4),
        'weighted_rms_db': round(weighted_rms, 4),
        'weight_profile': weight_profile or 'none',
        'preamp_db': round(preamp_db, 4),
        'warnings': [],
        'engine': 'precise',
        'alignment': alignment_info,
    }


