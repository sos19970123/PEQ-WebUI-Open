# -*- coding: utf-8 -*-
"""
autofit.py - 纯 numpy 自动拟合引擎（确定性，无 scipy）

算法（《拟合算法优化方案评估.md》方案 A / v3）:
1. 源曲线 S(f) 与目标曲线 T(f) 重采样到同一对数网格。
2. 需求 E(f) = T(f) - S(f)。
3. 低频保底锚点：约 20% 段数在 fmin~800Hz 对数均布（宽 Q），避免段数全被高频抢走。
4. 峰值贪心布点：迭代取 |残差| 最大处放 PK，fc=峰位，按半高宽估 Q，
   每放一段 lstsq 重解全部 gain 并更新残差。
5. 坐标下降精修到收敛：fc × (0.7~1.4)、Q × (0.6~1.6) 邻域，每步 lstsq 重解 gain，
   无改进即停（上限 ~12 轮）。
6. 10kHz 以上按均值能量计误差（AutoEq 同款）。

可选 auto_shelf=False（默认关）。开启时按评估文档加 LS/HS，并在输出前做
近似/重复 fc 段合并防退化（阈值 1/50 oct，不误伤高频窄峰）。
"""
import math
import numpy as np

F_MIN = 20.0
F_MAX = 20000.0
GRID_N = 256
DEFAULT_SAMPLE_RATE = 48000
HI_AVG = 10000.0
PREAMP_HEADROOM = 0.2
SANITIZE_MAX_Q = 4.0
SANITIZE_HI_POS_CAP_DB = 4.0
SANITIZE_VHI_POS_CAP_DB = 2.5
SANITIZE_MIN_OCT = 1.0 / 6.0

WEIGHT_PRESETS = {
    'none': None,
    'mild': 'mild',
    'mid_centric': 'mid_centric',
    'hf_conservative': 'hf_conservative',
}


def _make_weights(freqs, profile='none'):
    """根据权重预设生成频段权重数组；'none'/None 返回 None 表示等权。"""
    if not profile or profile == 'none':
        return None
    f = np.asarray(freqs, dtype=float)
    w = np.ones_like(f)
    if profile == 'mild':
        w[(f >= 200) & (f <= 8000)] *= 1.5
        w[f >= 10000] *= 0.6
    elif profile == 'mid_centric':
        w[(f >= 500) & (f <= 4000)] *= 2.0
        w[(f >= 200) & (f < 500)] *= 1.3
        w[(f > 4000) & (f <= 8000)] *= 1.5
        w[f >= 12000] *= 0.3
    elif profile == 'hf_conservative':
        w[(f >= 8000) & (f < 10000)] *= 0.8
        w[f >= 10000] *= 0.4
        w[f < 80] *= 0.8
    return w


def _log_grid(fmin=F_MIN, fmax=F_MAX, n=GRID_N):
    return np.exp(np.linspace(np.log(fmin), np.log(fmax), n))


def _interp(points, grid):
    """points: [[freq, db], ...] -> db on grid. 空数据返回 0dB。"""
    if not points or len(points) < 2:
        return np.zeros_like(grid)
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    # x 轴按对数插值更贴合听感
    logxs = np.log(np.clip(xs, F_MIN, F_MAX))
    loggrid = np.log(np.clip(grid, F_MIN, F_MAX))
    return np.interp(loggrid, logxs, ys)


def _rbj_peaking_mag_db(freqs, fc, gain_db, q, sr=DEFAULT_SAMPLE_RATE):
    """兼容旧函数名：返回 1dB 增益下的 PK shape（也可传 gain_db）。

    实际新代码中使用 _unit_shape / _rbj_mag_db。
    """
    return _rbj_mag_db(freqs, 'PK', fc, gain_db, q, sr)


def _rbj_mag_db(freqs, ftype, fc, gain_db, q, sr=DEFAULT_SAMPLE_RATE):
    """RBJ biquad 幅频响应（dB），支持 PK / LS / HS。"""
    freqs = np.asarray(freqs, dtype=float)
    A = 10.0 ** (float(gain_db) / 40.0)
    w0 = 2 * np.pi * float(fc) / sr
    cw, sw = np.cos(w0), np.sin(w0)
    if ftype == 'PK':
        alpha = sw / (2 * float(q))
        b0, b1, b2 = 1 + alpha * A, -2 * cw, 1 - alpha * A
        a0, a1, a2 = 1 + alpha / A, -2 * cw, 1 - alpha / A
    elif ftype == 'LS':
        alpha = sw / (2 * float(q))
        sa = 2 * np.sqrt(A) * alpha
        b0 = A * ((A + 1) - (A - 1) * cw + sa)
        b1 = 2 * A * ((A - 1) - (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - sa)
        a0 = (A + 1) + (A - 1) * cw + sa
        a1 = -2 * ((A - 1) + (A + 1) * cw)
        a2 = (A + 1) + (A - 1) * cw - sa
    elif ftype == 'HS':
        alpha = sw / (2 * float(q))
        sa = 2 * np.sqrt(A) * alpha
        b0 = A * ((A + 1) + (A - 1) * cw + sa)
        b1 = -2 * A * ((A - 1) + (A + 1) * cw)
        b2 = A * ((A + 1) - (A - 1) * cw - sa)
        a0 = (A + 1) - (A - 1) * cw + sa
        a1 = 2 * ((A - 1) - (A + 1) * cw)
        a2 = (A + 1) - (A - 1) * cw - sa
    else:
        raise ValueError(ftype)
    w = 2 * np.pi * freqs / sr
    z1 = np.exp(-1j * w)
    z2 = np.exp(-2j * w)
    h = (b0 + b1 * z1 + b2 * z2) / (a0 + a1 * z1 + a2 * z2)
    return 20 * np.log10(np.maximum(np.abs(h), 1e-12))


def _unit_shape(freqs, ftype, fc, q, sr=DEFAULT_SAMPLE_RATE):
    """1dB 增益下的 shape（lstsq 基函数）。"""
    return _rbj_mag_db(freqs, ftype, fc, 1.0, q, sr)


def _solve_gains(freqs, need, types, fcs, qs, max_gain, sr=DEFAULT_SAMPLE_RATE):
    shape = np.column_stack([_unit_shape(freqs, t, fc, q, sr) for t, fc, q in zip(types, fcs, qs)])
    try:
        gains, *_ = np.linalg.lstsq(shape, need, rcond=None)
    except np.linalg.LinAlgError:
        gains = np.zeros(len(fcs))
    return np.clip(gains, -max_gain, max_gain)


def _exact_sum(freqs, types, fcs, gains, qs, sr=DEFAULT_SAMPLE_RATE):
    out = np.zeros(len(freqs))
    for t, fc, g, q in zip(types, fcs, gains, qs):
        out += _rbj_mag_db(freqs, t, fc, g, q, sr)
    return out


def calculate_preamp_db(bands, headroom=PREAMP_HEADROOM, sample_rate=DEFAULT_SAMPLE_RATE,
                        fmin=F_MIN, fmax=F_MAX, n=GRID_N):
    """根据启用频段的串联频响最大正向峰值计算 Preamp（dB）。

    用于手动微调后保存预设时自动刷新 Preamp，避免用户逐段手算。
    与 autofit() 使用相同的 RBJ 响应模型和 0.2 dB headroom。
    仅支持 PK/LS/HS（LP/HP 无增益，不参与求和）。
    """
    types = []
    fcs = []
    gains = []
    qs = []
    for band in bands or []:
        if not isinstance(band, dict):
            continue
        if band.get('enabled', True) is False:
            continue
        ftype = str(band.get('type') or 'PK').upper()
        if ftype not in ('PK', 'LS', 'HS'):
            continue
        try:
            fc = float(band.get('freq', band.get('frequency', band.get('fc', 1000))) or 1000)
            gain = float(band.get('gain_db', band.get('gain', band.get('db', 0))) or 0)
            q = float(band.get('q', band.get('Q', 1)) or 1)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(fc) and math.isfinite(gain) and math.isfinite(q)):
            continue
        if fc <= 0 or q <= 0:
            continue
        types.append(ftype)
        fcs.append(fc)
        gains.append(gain)
        qs.append(q)

    if not types:
        return 0.0
    try:
        grid = _log_grid(fmin, fmax, n)
        pred = _exact_sum(grid, types, fcs, gains, qs, sr=sample_rate)
        max_positive = float(np.max(pred)) if len(pred) else 0.0
    except Exception:
        return 0.0
    return round(-max(0.0, max_positive + float(headroom or 0.0)), 4)


def _rms_db(freqs, need, types, fcs, gains, qs, hi_avg=HI_AVG, sr=DEFAULT_SAMPLE_RATE, weights=None):
    """RMS；hi_avg 以上的误差用逐点偏差但目标/预测都减去各自均值能量。"""
    if len(freqs) == 0:
        return 0.0
    pred = _exact_sum(freqs, types, fcs, gains, qs, sr)
    err = pred - need
    hi = freqs >= hi_avg
    if np.any(hi):
        err_hi = (pred[hi] - np.mean(pred[hi])) - (need[hi] - np.mean(need[hi]))
        err = np.concatenate([err[~hi], err_hi])
    if weights is not None:
        err = err * np.asarray(weights, dtype=float)
    return float(np.sqrt(np.mean(err ** 2)))



def _smooth_with_sigma(values, sigma_grid):
    """用指定 sigma（网格索引单位）做高斯平滑。"""
    values = np.asarray(values, dtype=float)
    if sigma_grid <= 0.0 or len(values) < 3:
        return values
    radius = int(max(1, min(len(values) // 2, int(np.ceil(sigma_grid * 4)))))
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-0.5 * (x / sigma_grid) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(values, radius, mode='edge')
    return np.convolve(padded, kernel, mode='valid')


def _sharpness_penalty_for_bands(freqs, types, fcs, gains, qs, sr=DEFAULT_SAMPLE_RATE):
    """AutoEq 风格 sharpness 惩罚：对高增益/高 Q 的窄峰给予额外损失。"""
    if not types:
        return 0.0
    penalty = 0.0
    with np.errstate(divide='ignore', invalid='ignore'):
        for t, fc, g, q in zip(types, fcs, gains, qs):
            if t != 'PK' or abs(g) < 0.01:
                continue
            gain_limit = -0.09503189270199464 + 20.575128011847003 * (1.0 / max(q, 0.1))
            if abs(gain_limit) < 0.01:
                continue
            x = abs(g) / gain_limit - 1.0 if gain_limit > 0 else 0.0
            coeff = 1.0 / (1.0 + np.exp(-x * 100.0))
            if coeff > 0:
                r = _rbj_mag_db(freqs, t, fc, g, q, sr)
                penalty += float(np.mean(np.square(r * coeff)))
    return penalty


def _peak_init(freqs, need, n, max_gain, seed_types=None, seed_fcs=None, seed_qs=None,
               low_anchor=0.0, f_lo_limit=800.0, sr=DEFAULT_SAMPLE_RATE):
    """残差峰值贪心布点：每次取 |残差| 最大处放 PK，宽度估 Q，lstsq 重解增益。"""
    types = list(seed_types or [])
    fcs = list(seed_fcs or [])
    qs = list(seed_qs or [])
    if types:
        gains = _solve_gains(freqs, need, types, fcs, qs, max_gain, sr)
        resid = need - _exact_sum(freqs, types, fcs, gains, qs, sr)
    else:
        resid = need.copy()

    n_anchor = int(round(n * low_anchor))
    if n_anchor > 0:
        lo_f, hi_f = freqs[0], min(f_lo_limit, freqs[-1])
        if n_anchor > 1:
            anchor_fs = [lo_f * (hi_f / lo_f) ** (i / (n_anchor - 1)) for i in range(n_anchor)]
        else:
            anchor_fs = [np.sqrt(lo_f * hi_f)]
        for fc in anchor_fs:
            types.append('PK')
            fcs.append(float(fc))
            qs.append(1.0)
            gains = _solve_gains(freqs, need, types, fcs, qs, max_gain, sr)
            resid = need - _exact_sum(freqs, types, fcs, gains, qs, sr)

    for _ in range(n - n_anchor):
        i = int(np.argmax(np.abs(resid)))
        fc = float(freqs[i])
        g0 = float(resid[i])
        half = abs(g0) / 2.0
        lo = i
        while lo > 0 and abs(resid[lo]) > half and np.sign(resid[lo]) == np.sign(g0):
            lo -= 1
        hi = i
        while hi < len(freqs) - 1 and abs(resid[hi]) > half and np.sign(resid[hi]) == np.sign(g0):
            hi += 1
        bw = max(np.log2(freqs[hi] / freqs[lo]), 0.15)
        q = float(np.clip(np.sqrt(2 ** bw) / (2 ** bw - 1), 0.3, 12.0))
        types.append('PK')
        fcs.append(fc)
        qs.append(q)
        gains = _solve_gains(freqs, need, types, fcs, qs, max_gain, sr)
        resid = need - _exact_sum(freqs, types, fcs, gains, qs, sr)
    return types, fcs, list(gains), qs


def _shelf_init(freqs, need, ftype, f_lo, f_hi, max_gain, sr=DEFAULT_SAMPLE_RATE):
    """AutoEq 风格 shelf 初始化：找前/后半段均值绝对值最大的分界点，Q=0.7。"""
    best_fc, best_score = None, -1.0
    for i in range(1, len(freqs) - 1):
        f = freqs[i]
        if f < f_lo or f > f_hi:
            continue
        seg = need[:i + 1] if ftype == 'LS' else need[i:]
        score = abs(float(np.mean(seg)))
        if score > best_score:
            best_score, best_fc = score, float(f)
    if best_fc is None:
        best_fc = float(np.sqrt(f_lo * f_hi))
    gains = _solve_gains(freqs, need, [ftype], [best_fc], [0.7], max_gain, sr)
    return best_fc, float(gains[0]), 0.7


def _coord_descent(freqs, need, types, fcs, gains, qs, max_gain, max_q,
                 fc_steps=(0.7, 0.85, 0.93, 1.0, 1.07, 1.18, 1.4),
                 q_steps=(0.6, 0.8, 0.9, 1.0, 1.12, 1.25, 1.6),
                 max_rounds=12, tol=1e-4, sr=DEFAULT_SAMPLE_RATE,
                 sharpness_penalty=False, weights=None):
    fcs = list(fcs)
    qs = list(qs)
    # 初始 Q 也必须落在用户 max_q / shelf 区间内，避免峰值初始化产生越界残留
    for i, q in enumerate(qs):
        if types[i] in ('LS', 'HS'):
            qs[i] = float(np.clip(q, min(0.4, max_q), min(0.7, max_q)))
        else:
            qs[i] = float(np.clip(q, min(0.3, max_q), max_q))
    gains = _solve_gains(freqs, need, types, fcs, qs, max_gain, sr)
    best_rms = _rms_db(freqs, need, types, fcs, gains, qs, sr=sr, weights=weights)
    best_loss = best_rms
    if sharpness_penalty:
        best_loss = best_rms + _sharpness_penalty_for_bands(freqs, types, fcs, gains, qs, sr)
    for _ in range(max_rounds):
        improved = False
        for i in range(len(fcs)):
            for fr in fc_steps:
                if types[i] == 'LS':
                    fc_lo, fc_hi = max(freqs[0], 20.0), min(freqs[-1], 600.0)
                elif types[i] == 'HS':
                    fc_lo, fc_hi = max(freqs[0], 6000.0), freqs[-1]
                else:
                    fc_lo, fc_hi = freqs[0], freqs[-1]
                if fc_hi <= fc_lo:
                    fc_lo, fc_hi = freqs[0], freqs[-1]
                fc_c = float(np.clip(fcs[i] * fr, fc_lo, fc_hi))
                for qr in q_steps:
                    if types[i] in ('LS', 'HS'):
                        q_lo, q_hi = min(0.4, max_q), min(0.7, max_q)
                    else:
                        q_lo, q_hi = 0.3, max_q
                    q_c = float(np.clip(qs[i] * qr, q_lo, q_hi))
                    if fc_c == fcs[i] and q_c == qs[i]:
                        continue
                    cfcs, cqs = list(fcs), list(qs)
                    cfcs[i], cqs[i] = fc_c, q_c
                    cg = _solve_gains(freqs, need, types, cfcs, cqs, max_gain, sr)
                    r = _rms_db(freqs, need, types, cfcs, cg, cqs, sr=sr, weights=weights)
                    candidate_loss = r
                    if sharpness_penalty:
                        candidate_loss = r + _sharpness_penalty_for_bands(freqs, types, cfcs, cg, cqs, sr)
                    if candidate_loss < best_loss - tol:
                        best_loss = candidate_loss
                        best_rms = r
                        fcs, qs, gains = cfcs, cqs, cg
                        improved = True
        if not improved:
            break
    return fcs, gains, qs, best_rms


def _dedupe_bands(bands, min_oct=0.02, max_gain=None):
    """近似/完全相同 fc 段合并兜底，防止病态重复段写进 APO。

    阈值取约 1/50 oct，只合并真正重复/几乎重合的段，避免误伤 v3 高频窄峰优化。
    若提供 max_gain，合并后的增益会被重新夹紧。
    """
    active = [dict(b) for b in bands if b.get('enabled', True)]
    active.sort(key=lambda b: (b['freq'], b['q']))
    merged = []
    for b in active:
        if merged and b['type'] == merged[-1]['type']:
            prev = merged[-1]
            ratio = b['freq'] / prev['freq'] if prev['freq'] > 0 else 1.0
            q_ratio = max(prev['q'], b['q']) / min(prev['q'], b['q']) if min(prev['q'], b['q']) > 0 else 1.0
            if ratio > 0 and abs(math.log2(ratio)) < min_oct and q_ratio < 1.05:
                w1 = abs(prev['gain_db'])
                w2 = abs(b['gain_db'])
                if w1 + w2 > 1e-9:
                    fc = math.exp((w1 * math.log(prev['freq']) + w2 * math.log(b['freq'])) / (w1 + w2))
                else:
                    fc = math.sqrt(prev['freq'] * b['freq'])
                prev['freq'] = round(float(fc), 2)
                merged_gain = prev['gain_db'] + b['gain_db']
                if max_gain is not None:
                    merged_gain = max(-float(max_gain), min(float(max_gain), merged_gain))
                prev['gain_db'] = round(merged_gain, 2)
                prev['q'] = round(max(prev['q'], b['q']), 3)
                prev['enabled'] = abs(prev['gain_db']) > 0.01
                continue
        merged.append(b)
    return merged


def sanitize_bands(bands, max_gain=None, max_q=SANITIZE_MAX_Q,
                   min_oct=SANITIZE_MIN_OCT,
                   hi_cap_db=SANITIZE_HI_POS_CAP_DB,
                   very_hi_cap_db=SANITIZE_VHI_POS_CAP_DB):
    """听感安全后处理（可选）。

    - 限制 PK 的 Q，避免高 Q 振铃；
    - 限制 5kHz/8kHz 以上正增益，高频尽量保守；
    - 清理 1/6 oct 内正负对消的 PK 对；
    - 最后再做一次重复段合并。
    """
    active = [dict(b) for b in bands if b.get('enabled', True)]
    for b in active:
        if b.get('type') == 'PK':
            b['q'] = round(min(float(b.get('q', 1.0)), max_q), 3)
        gain = float(b.get('gain_db', 0.0))
        if gain > 0:
            f = float(b.get('freq', 0.0))
            if f >= 8000:
                gain = min(gain, very_hi_cap_db)
            elif f >= 5000:
                gain = min(gain, hi_cap_db)
        if max_gain is not None:
            gain = max(-float(max_gain), min(float(max_gain), gain))
        b['gain_db'] = round(gain, 2)
        b['enabled'] = abs(gain) > 0.01
    active = [b for b in active if b.get('enabled', True)]
    active.sort(key=lambda b: (b['freq'], b['q']))

    removed = set()
    result = []
    for i, b in enumerate(active):
        if i in removed:
            continue
        drop = False
        if b.get('type') == 'PK':
            for j in range(i + 1, len(active)):
                if j in removed:
                    continue
                c = active[j]
                if c.get('type') != 'PK':
                    continue
                ratio = c['freq'] / b['freq'] if b['freq'] > 0 else 1.0
                if ratio <= 1 or abs(math.log2(ratio)) >= min_oct:
                    continue
                if b['gain_db'] * c['gain_db'] < 0 and abs(b['gain_db']) > 0.5 and abs(c['gain_db']) > 0.5:
                    # 保留幅度更大的一段，移除较弱一段，减少正负对消
                    if abs(b['gain_db']) >= abs(c['gain_db']):
                        removed.add(j)
                    else:
                        removed.add(i)
                        drop = True
                    break
        if not drop:
            result.append(b)

    result = _dedupe_bands(result, max_gain=max_gain)
    result.sort(key=lambda b: b['freq'])
    return result


def _fit_quick(grid_fit, needs, n, fmin, fmax, max_gain, max_q,
                sample_rate=DEFAULT_SAMPLE_RATE, low_anchor=0.2, auto_shelf=False,
                 sharpness_penalty=False, weights=None):
    """单次快速拟合，返回 (bands, rms)。auto_shelf=True 时可能带 LS/HS 候选。"""
    types, fcs, qs = [], [], []
    remaining = n

    # 可选 shelf：只在对应半段平均残差幅度足够时启用（避免浪费段数）
    if auto_shelf and n >= 4:
        ls_lo = max(20.0, fmin)
        ls_hi = min(600.0, fmax)
        hs_lo = max(6000.0, fmin)
        hs_hi = min(12000.0, fmax)
        if ls_lo < ls_hi:
            ls_fc, _, ls_q = _shelf_init(grid_fit, needs, 'LS', ls_lo, ls_hi, max_gain, sample_rate)
            ls_mean = abs(float(np.mean(needs[grid_fit <= ls_fc]))) if np.any(grid_fit <= ls_fc) else 0.0
            if ls_mean > 1.5:
                types += ['LS']
                fcs += [ls_fc]
                qs += [ls_q]
                remaining -= 1
        if hs_lo < hs_hi:
            hs_fc, _, hs_q = _shelf_init(grid_fit, needs, 'HS', hs_lo, hs_hi, max_gain, sample_rate)
            hs_mean = abs(float(np.mean(needs[grid_fit >= hs_fc]))) if np.any(grid_fit >= hs_fc) else 0.0
            if hs_mean > 1.5:
                types += ['HS']
                fcs += [hs_fc]
                qs += [hs_q]
                remaining -= 1

    remaining = max(1, min(n, remaining))
    types, fcs, gains, qs = _peak_init(
        grid_fit, needs, remaining, max_gain,
        seed_types=types, seed_fcs=fcs, seed_qs=qs,
        low_anchor=low_anchor, sr=sample_rate)

    fcs, gains, qs, rms = _coord_descent(
        grid_fit, needs, types, fcs, gains, qs,
        max_gain, max_q, sr=sample_rate,
        sharpness_penalty=sharpness_penalty, weights=weights)

    bands = []
    for i in range(len(fcs)):
        bands.append({
            'type': types[i],
            'freq': round(float(fcs[i]), 2),
            'gain_db': round(float(gains[i]), 2),
            'q': round(float(qs[i]), 3),
            'enabled': abs(float(gains[i])) > 0.01,
        })
    bands = _dedupe_bands(bands, max_gain=max_gain)

    # 去重后重新计算真实残差
    if bands:
        btypes = [b['type'] for b in bands]
        bfcs = [b['freq'] for b in bands]
        bgains = [b['gain_db'] for b in bands]
        bqs = [b['q'] for b in bands]
        rms = _rms_db(grid_fit, needs, btypes, bfcs, bgains, bqs, sr=sample_rate)
    else:
        rms = float(np.sqrt(np.mean(needs ** 2)))

    bands.sort(key=lambda b: b['freq'])
    return bands, rms


def autofit(source_points, target_points,
            filters=10, fmin=100.0, fmax=12000.0,
            max_gain_db=12.0, max_q=6.0, sample_rate=DEFAULT_SAMPLE_RATE,
            low_anchor=0.2, auto_shelf=False,
             sharpness_penalty=False, smooth_oct=0.0,
             sanitize=False, align=True, align_ref_low=500.0, align_ref_high=2000.0,
             min_mean_error=True, min_mean_low=100.0, min_mean_high=10000.0,
             weight_profile='none'):
    """自动拟合。

    low_anchor: 低频保底段数比例（方案 A v3 默认 0.2）。
    auto_shelf: 是否启用 LS/HS（评估文档 P2 可选开关，默认关）。
                开启后会与纯 PK 结果做防退化比较，只有 shelf 确实降低残差才采用。
    align: 是否在拟合前做基准对齐。默认 True，对齐后不会出现一条曲线整体
           高于/低于另一条导致全频段 EQ 的情况。
    align_ref_low/align_ref_high: 当 min_mean_error=False 时使用的参考频段。
    min_mean_error: 是否使用 AutoEq 风格的 100Hz-10kHz 误差均值归零。
    sanitize: 是否启用听感安全后处理（限制 Q/高频正增益/清理正负对消）。
    """
    warnings = []
    if not source_points or len(source_points) < 2:
        warnings.append('设备原始频响数据为空，使用 0dB 平直作为源曲线')
        source_points = [[F_MIN, 0], [F_MAX, 0]]
    if not target_points or len(target_points) < 2:
        warnings.append('目标曲线数据为空，使用 0dB 平直作为目标曲线')
        target_points = [[F_MIN, 0], [F_MAX, 0]]
    if fmin >= fmax:
        fmin, fmax = min(fmin, fmax), max(fmin, fmax)
    fmin = float(max(F_MIN, min(fmin, F_MAX)))
    fmax = float(max(F_MIN, min(fmax, F_MAX)))
    if fmin >= fmax:
        fmin, fmax = F_MIN, F_MAX

    full_grid = _log_grid(F_MIN, F_MAX, GRID_N)
    source = _interp(source_points, full_grid)
    target = _interp(target_points, full_grid)

    mask = (full_grid >= fmin) & (full_grid <= fmax)
    grid_fit = full_grid[mask]
    needs = target[mask] - source[mask]

    alignment_info = {}
    if align:
        # 基准对齐（参考 AutoEq center + min_mean_error）
        # 1) min_mean_error=True：将 100Hz-10kHz 内需求曲线均值归零，
        #    避免曲线整体偏高/偏低导致绝大多数频段都要 EQ。
        # 2) min_mean_error=False：退回参考频段（默认 500Hz-2kHz）平均对齐。
        if min_mean_error:
            mm_mask = (grid_fit >= min_mean_low) & (grid_fit <= min_mean_high)
            if np.any(mm_mask):
                mean_off = float(np.mean(needs[mm_mask]))
                needs = needs - mean_off
                alignment_info['method'] = 'min_mean_error'
                alignment_info['min_mean_low'] = float(min_mean_low)
                alignment_info['min_mean_high'] = float(min_mean_high)
                alignment_info['offset_db'] = round(mean_off, 4)
                alignment_info['min_mean_offset_db'] = round(mean_off, 4)
        else:
            ref_mask = (grid_fit >= align_ref_low) & (grid_fit <= align_ref_high)
            if np.any(ref_mask):
                ref_off = float(np.mean(needs[ref_mask]))
                needs = needs - ref_off
                alignment_info['method'] = 'ref_band_mean'
                alignment_info['ref_low'] = float(align_ref_low)
                alignment_info['ref_high'] = float(align_ref_high)
                alignment_info['offset_db'] = round(ref_off, 4)

    # 拟合前平滑：smooth_oct > 0 时对 log 频域做高斯平滑，减少测量毛刺
    if smooth_oct and smooth_oct > 0:
        if len(grid_fit) > 2:
            f_step = grid_fit[1] / grid_fit[0]
            indices_per_oct = 1.0 / np.log2(f_step)
            sigma_grid = float(smooth_oct) * indices_per_oct
            needs = _smooth_with_sigma(needs, sigma_grid)

    n = int(max(1, min(20, filters or 10)))
    max_gain = float(max_gain_db)
    max_q = float(max_q)
    weights = _make_weights(grid_fit, weight_profile)

    if auto_shelf and n >= 4:
        shelf_bands, shelf_rms = _fit_quick(
            grid_fit, needs, n, fmin, fmax, max_gain, max_q, sample_rate,
            low_anchor=low_anchor, auto_shelf=True,
             sharpness_penalty=sharpness_penalty, weights=weights)
        pk_bands, pk_rms = _fit_quick(
            grid_fit, needs, n, fmin, fmax, max_gain, max_q, sample_rate,
            low_anchor=low_anchor, auto_shelf=False,
             sharpness_penalty=sharpness_penalty, weights=weights)
        # 防退化：shelf 组合常产生同频堆叠/正负对消。必须显著优于纯 PK 才采用。
        if shelf_rms < pk_rms - 0.02:
            bands, rms = shelf_bands, shelf_rms
        else:
            bands, rms = pk_bands, pk_rms
            warnings.append(
                '高低架候选未改善拟合（shelf RMS %.3f vs 纯PK RMS %.3f，且易出现低频堆叠），'
                '已自动关闭高低架' % (shelf_rms, pk_rms))
    else:
        bands, rms = _fit_quick(
            grid_fit, needs, n, fmin, fmax, max_gain, max_q, sample_rate,
            low_anchor=low_anchor, auto_shelf=auto_shelf,
            sharpness_penalty=sharpness_penalty, weights=weights)

    if sanitize:
        bands = sanitize_bands(bands, max_gain=max_gain)
        if bands:
            btypes = [b['type'] for b in bands if b.get('enabled', True)]
            bfcs = [b['freq'] for b in bands if b.get('enabled', True)]
            bgains = [b['gain_db'] for b in bands if b.get('enabled', True)]
            bqs = [b['q'] for b in bands if b.get('enabled', True)]
            rms = _rms_db(grid_fit, needs, btypes, bfcs, bgains, bqs, sr=sample_rate)
        else:
            rms = float(np.sqrt(np.mean(needs ** 2)))

    # Preamp：按级联后频率响应的最大正向峰值计算，而不是单段最大增益；
    # 并保留 0.2dB headroom，避免多段正增益叠加后削波。
    btypes = [b['type'] for b in bands if b.get('enabled', True)]
    bfcs = [b['freq'] for b in bands if b.get('enabled', True)]
    bgains = [b['gain_db'] for b in bands if b.get('enabled', True)]
    bqs = [b['q'] for b in bands if b.get('enabled', True)]
    if btypes:
        pred = _exact_sum(grid_fit, btypes, bfcs, bgains, bqs, sr=sample_rate)
        max_positive = float(np.max(pred))
    else:
        max_positive = 0.0
    preamp_db = -max(0.0, max_positive + PREAMP_HEADROOM)
    weighted_rms = rms
    if weights is not None:
        weighted_rms = _rms_db(grid_fit, needs, btypes, bfcs, bgains, bqs, sr=sample_rate, weights=weights)
    return {
        'bands': bands,
        'rms_db': round(rms, 4),
        'weighted_rms_db': round(weighted_rms, 4),
        'weight_profile': weight_profile or 'none',
        'preamp_db': round(preamp_db, 4),
        'warnings': warnings,
        'engine': 'quick',
        'alignment': alignment_info,
    }


if __name__ == '__main__':
    src = [[20, 2], [100, 1], [1000, -2], [5000, 1], [20000, -1]]
    tgt = [[20, 0], [100, 0], [1000, 0], [5000, 0], [20000, 0]]
    res = autofit(src, tgt, filters=4)
    print(res)


