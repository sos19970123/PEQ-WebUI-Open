# -*- coding: utf-8 -*-
"""
fit_bench.py - 拟合算法基准对比（评估用，非生产代码）

对比：
  baseline : 现有 autofit.py（均匀布点 + lstsq + 贪心邻域 2 轮，纯 PK）
  v2       : 改进原型（残差峰值贪心布点 + 可选 LS/HS + lstsq + 坐标下降多轮精修）

数据：
  设备  peq-webui/curves/devices/dt900prox.json            (oratory1990)
  目标A peq-webui/curves/targets/sennheiser-hd-800-原始频响.json  (Headphone.com Legacy)
  目标B AutoEq results/oratory1990/over-ear/Sennheiser HD 800.csv raw 列（同 rig）

用法: py fit_bench.py
"""
import csv
import io
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # peq-webui/
from autofit import autofit, _log_grid, _interp, _rbj_mag_db, F_MIN, F_MAX, GRID_N  # noqa: E402

AUTOEQ_HD800_CSV = os.path.join(
    os.path.dirname(HERE), '..', 'AutoEq-4.1.2', 'AutoEq-4.1.2', 'results',
    'oratory1990', 'over-ear', 'Sennheiser HD 800', 'Sennheiser HD 800.csv',
)
SR = 48000.0


# ---------------- 数据加载 ----------------
def load_json_points(path):
    with open(path, 'rb') as f:
        data = json.loads(f.read().decode('utf-8-sig'))
    return [[float(p[0]), float(p[1])] for p in data['points']]


def load_csv_raw(path):
    with open(path, 'rb') as f:
        text = f.read().decode('utf-8-sig', errors='replace')
    pts = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            pts.append([float(row['frequency']), float(row['raw'])])
        except (KeyError, TypeError, ValueError):
            continue
    return pts


# ---------------- RBJ 幅频（dB），增益精确 ----------------
def rbj_mag_db(freqs, ftype, fc, gain_db, q, sr=SR):
    # 统一使用 autofit 的 RBJ 实现，避免基准与生产代码漂移。
    return _rbj_mag_db(freqs, ftype, fc, gain_db, q, sr)


def unit_shape(freqs, ftype, fc, q):
    """1dB 增益的 shape（lstsq 基函数）"""
    return rbj_mag_db(freqs, ftype, fc, 1.0, q)


def exact_sum(freqs, types, fcs, gains, qs):
    out = np.zeros(len(freqs))
    for t, fc, g, q in zip(types, fcs, gains, qs):
        out += rbj_mag_db(freqs, t, fc, g, q)
    return out


# ---------------- v2：改进原型 ----------------
def solve_gains(freqs, need, types, fcs, qs, max_gain):
    shape = np.column_stack([unit_shape(freqs, t, fc, q) for t, fc, q in zip(types, fcs, qs)])
    try:
        gains, *_ = np.linalg.lstsq(shape, need, rcond=None)
    except np.linalg.LinAlgError:
        gains = np.zeros(len(fcs))
    return np.clip(gains, -max_gain, max_gain)


def rms_of(freqs, need, types, fcs, gains, qs, hi_avg=10000.0):
    """RMS；hi_avg 以上的误差用逐点偏差但目标与预测都减去各自均值能量（AutoEq 风格）"""
    pred = exact_sum(freqs, types, fcs, gains, qs)
    err = pred - need
    hi = freqs >= hi_avg
    if np.any(hi):
        err_hi = (pred[hi] - np.mean(pred[hi])) - (need[hi] - np.mean(need[hi]))
        err = np.concatenate([err[~hi], err_hi])
    return float(np.sqrt(np.mean(err ** 2)))


def peak_init(freqs, need, n, max_gain, seed_types=None, seed_fcs=None, seed_qs=None,
              low_anchor=0.0, f_lo_limit=800.0):
    """残差峰值贪心布点：每次取 |残差| 最大处放 PK，宽度估 Q，lstsq 重解增益。
    low_anchor: 比例 0~1，先在 fmin~f_lo_limit 区间对数均布若干宽 Q 段保底低频。"""
    types = list(seed_types or [])
    fcs = list(seed_fcs or [])
    qs = list(seed_qs or [])
    resid = need - exact_sum(freqs, types, fcs, solve_gains(freqs, need, types, fcs, qs, max_gain), qs) if types else need.copy()
    n_anchor = int(round(n * low_anchor))
    if n_anchor > 0:
        lo_f, hi_f = freqs[0], min(f_lo_limit, freqs[-1])
        anchor_fs = [lo_f * (hi_f / lo_f) ** (i / max(1, n_anchor - 1)) if n_anchor > 1 else np.sqrt(lo_f * hi_f)
                     for i in range(n_anchor)]
        for fc in anchor_fs:
            types.append('PK')
            fcs.append(float(fc))
            qs.append(1.0)
            gains = solve_gains(freqs, need, types, fcs, qs, max_gain)
            resid = need - exact_sum(freqs, types, fcs, gains, qs)
    for _ in range(n - n_anchor):
        i = int(np.argmax(np.abs(resid)))
        fc = float(freqs[i])
        g0 = float(resid[i])
        # 估峰宽：向两侧走到 |resid| 降到一半或过零
        half = abs(g0) / 2.0
        lo = i
        while lo > 0 and abs(resid[lo]) > half and np.sign(resid[lo]) == np.sign(g0):
            lo -= 1
        hi = i
        while hi < len(freqs) - 1 and abs(resid[hi]) > half and np.sign(resid[hi]) == np.sign(g0):
            hi += 1
        bw = max(np.log2(freqs[hi] / freqs[lo]), 0.15)  # 至少 ~0.15 oct
        q = float(np.clip(np.sqrt(2 ** bw) / (2 ** bw - 1), 0.3, 12.0))
        types.append('PK')
        fcs.append(fc)
        qs.append(q)
        gains = solve_gains(freqs, need, types, fcs, qs, max_gain)
        resid = need - exact_sum(freqs, types, fcs, gains, qs)
    return types, fcs, list(gains), qs


def shelf_init(freqs, need, ftype, f_lo, f_hi, max_gain):
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
    gains = solve_gains(freqs, need, [ftype], [best_fc], [0.7], max_gain)
    return best_fc, float(gains[0]), 0.7


def coord_descent(freqs, need, types, fcs, gains, qs, max_gain, max_q,
                  fc_steps=(0.7, 0.85, 0.93, 1.0, 1.07, 1.18, 1.4),
                  q_steps=(0.6, 0.8, 0.9, 1.0, 1.12, 1.25, 1.6),
                  max_rounds=12, tol=1e-4):
    fcs = list(fcs)
    qs = list(qs)
    gains = solve_gains(freqs, need, types, fcs, qs, max_gain)
    best_rms = rms_of(freqs, need, types, fcs, gains, qs)
    for _ in range(max_rounds):
        improved = False
        for i in range(len(fcs)):
            for fr in fc_steps:
                fc_c = float(np.clip(fcs[i] * fr, freqs[0], freqs[-1]))
                for qr in q_steps:
                    q_c = float(np.clip(qs[i] * qr, 0.3, max_q))
                    if fc_c == fcs[i] and q_c == qs[i]:
                        continue
                    cfcs, cqs = list(fcs), list(qs)
                    cfcs[i], cqs[i] = fc_c, q_c
                    cg = solve_gains(freqs, need, types, cfcs, cqs, max_gain)
                    r = rms_of(freqs, need, types, cfcs, cg, cqs)
                    if r < best_rms - tol:
                        best_rms = r
                        fcs, qs, gains = cfcs, cqs, cg
                        improved = True
        if not improved:
            break
    return fcs, gains, qs, best_rms


def autofit_v2(source_points, target_points, filters=10, fmin=100.0, fmax=12000.0,
               max_gain_db=12.0, max_q=6.0, use_shelf=True, low_anchor=0.0):
    full_grid = _log_grid(F_MIN, F_MAX, GRID_N)
    source = _interp(source_points, full_grid)
    target = _interp(target_points, full_grid)
    mask = (full_grid >= fmin) & (full_grid <= fmax)
    freqs = full_grid[mask]
    need = target[mask] - source[mask]

    n = int(filters)
    types, fcs, qs = [], [], []
    if use_shelf and n >= 4:
        fc_ls, _, q_ls = shelf_init(freqs, need, 'LS', max(40.0, fmin), min(600.0, fmax), max_gain_db)
        fc_hs, _, q_hs = shelf_init(freqs, need, 'HS', max(2000.0, fmin), min(10000.0, fmax), max_gain_db)
        types += ['LS', 'HS']
        fcs += [fc_ls, fc_hs]
        qs += [q_ls, q_hs]
        n -= 2
    types, fcs, gains, qs = peak_init(freqs, need, n, max_gain_db,
                                      seed_types=types, seed_fcs=fcs, seed_qs=qs,
                                      low_anchor=low_anchor)

    fcs, gains, qs, rms = coord_descent(freqs, need, types, fcs, gains, qs,
                                        max_gain_db, max_q)
    # 排序输出
    order = sorted(range(len(fcs)), key=lambda i: fcs[i])
    bands = [{'type': types[i], 'freq': round(fcs[i], 1), 'gain_db': round(gains[i], 2),
              'q': round(qs[i], 2)} for i in order]
    return bands, rms


# ---------------- 报告 ----------------
def band_rms(freqs, err):
    rows = []
    f = 100.0
    while f < 12800:
        m = (freqs >= f) & (freqs < f * 2)
        if np.any(m):
            rows.append((f, f * 2, float(np.sqrt(np.mean(err[m] ** 2)))))
        f *= 2
    return rows


def eval_bands(bands, freqs, need, sr=SR):
    pred = np.zeros(len(freqs))
    for b in bands:
        pred += rbj_mag_db(freqs, b['type'], b['freq'], b.get('gain_db', b.get('gain', 0.0)), b['q'], sr)
    err = pred - need
    return float(np.sqrt(np.mean(err ** 2))), band_rms(freqs, err)


def report(title, freqs, need, bands):
    rms, rows = eval_bands(bands, freqs, need)
    print(f'\n[{title}] 总体 RMS = {rms:.3f} dB')
    print('  分频段: ' + '  '.join(f'{int(a)}-{int(b)}:{r:.2f}' for a, b, r in rows))
    print('  bands: ' + ' | '.join(
        f"{b['type']} {b['freq']:.0f}Hz {b.get('gain_db', b.get('gain', 0)):+.1f}dB Q{b['q']:.2f}"
        for b in bands if abs(b.get('gain_db', b.get('gain', 0))) > 0.05))
    return rms


def main():
    dev = load_json_points(os.path.join(HERE, '..', 'curves', 'devices', 'dt900prox.json'))
    tgt_legacy = load_json_points(os.path.join(HERE, '..', 'curves', 'targets',
                                               'sennheiser-hd-800-原始频响.json'))
    tgt_oratory = load_csv_raw(AUTOEQ_HD800_CSV)

    P = dict(filters=10, fmin=100.0, fmax=12000.0, max_gain_db=12.0, max_q=6.0)

    for tgt_name, tgt in [('目标A: HD800 raw (Headphone.com Legacy, 跨rig)', tgt_legacy),
                          ('目标B: HD800 raw (oratory1990, 同rig)', tgt_oratory)]:
        print('=' * 78)
        print(tgt_name)
        full_grid = _log_grid(F_MIN, F_MAX, GRID_N)
        source = _interp(dev, full_grid)
        target = _interp(tgt, full_grid)
        mask = (full_grid >= P['fmin']) & (full_grid <= P['fmax'])
        freqs = full_grid[mask]
        need = target[mask] - source[mask]

        res = autofit(dev, tgt, **P)
        report('autofit v3 已落地 (10×PK)', freqs, need, res['bands'])

        bands2, _ = autofit_v2(dev, tgt, use_shelf=False, **P)
        report('v2 纯PK (峰值布点+坐标下降)', freqs, need, bands2)

        bands3, _ = autofit_v2(dev, tgt, use_shelf=True, **P)
        report('v2 含LS/HS (8×PK+LS+HS)', freqs, need, bands3)

        # v3: 低频保底锚点（20% 段数放 fmin~800Hz 对数均布，Q=1）
        bands5, _ = autofit_v2(dev, tgt, use_shelf=False, low_anchor=0.2, **P)
        report('v3 纯PK + 低频保底20%', freqs, need, bands5)

        bands6, _ = autofit_v2(dev, tgt, use_shelf=True, low_anchor=0.2, **P)
        report('v3 含LS/HS + 低频保底20%', freqs, need, bands6)


if __name__ == '__main__':
    main()


