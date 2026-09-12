# -*- coding: utf-8 -*-
"""Generate README illustration: raw vs target vs EQ vs equalized (SVG)."""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = os.path.join(ROOT, 'curves', 'devices', 'dt900prox.json')
TGT = os.path.join(ROOT, 'curves', 'targets', 'harman_overear_2018.json')
OUT = os.path.join(ROOT, 'docs', 'autofit-preview.svg')


def load_points(path):
    with open(path, 'rb') as f:
        data = json.loads(f.read().decode('utf-8-sig'))
    pts = [(float(p[0]), float(p[1])) for p in data.get('points', [])]
    pts = [(f, d) for f, d in pts if 20 <= f <= 20000]
    pts.sort(key=lambda x: x[0])
    return pts, data.get('name', os.path.basename(path))


def interp(pts, freq):
    if not pts:
        return 0.0
    if freq <= pts[0][0]:
        return pts[0][1]
    if freq >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        f0, y0 = pts[i - 1]
        f1, y1 = pts[i]
        if f0 <= freq <= f1:
            if f1 == f0:
                return y1
            t = (freq - f0) / (f1 - f0)
            return y0 + t * (y1 - y0)
    return pts[-1][1]


def log_grid(fmin=20, fmax=20000, n=240):
    lo, hi = math.log10(fmin), math.log10(fmax)
    return [10 ** (lo + (hi - lo) * i / (n - 1)) for i in range(n)]


def peaking_mag_db(f, f0, gain_db, q):
    """RBJ peaking magnitude in dB."""
    w0 = 2 * math.pi * f0 / 48000.0
    A = 10 ** (gain_db / 40.0)
    alpha = math.sin(w0) / (2 * q)
    b0 = 1 + alpha * A
    b1 = -2 * math.cos(w0)
    b2 = 1 - alpha * A
    a0 = 1 + alpha / A
    a1 = -2 * math.cos(w0)
    a2 = 1 - alpha / A
    # evaluate H(e^{jw}) at continuous f (approximate with digital omega)
    w = 2 * math.pi * f / 48000.0
    # use analog-style biquad for smoother plot (RBJ bilinear at 48k is fine for demo)
    def mag(bb0, bb1, bb2, aa0, aa1, aa2):
        c1 = math.cos(w)
        c2 = math.cos(2 * w)
        s1 = math.sin(w)
        s2 = math.sin(2 * w)
        num_re = bb0 + bb1 * c1 + bb2 * c2
        num_im = -(bb1 * s1 + bb2 * s2)
        den_re = aa0 + aa1 * c1 + aa2 * c2
        den_im = -(aa1 * s1 + aa2 * s2)
        num = num_re * num_re + num_im * num_im
        den = den_re * den_re + den_im * den_im
        return math.sqrt(max(num, 1e-30) / max(den, 1e-30))
    m = mag(b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0)
    return 20 * math.log10(max(m, 1e-12))


# demo EQ: a few PK bands chosen to flatten typical over-ear vs Harman
BANDS = [
    (60, 4.5, 0.8),
    (150, -2.5, 1.2),
    (400, -1.5, 1.5),
    (2500, 3.0, 1.8),
    (5500, -3.5, 2.5),
    (9000, 2.0, 2.0),
]


def eq_db(f):
    return sum(peaking_mag_db(f, f0, g, q) for f0, g, q in BANDS)


def path_from_xy(xs, ys, xmap, ymap):
    parts = []
    for i, (x, y) in enumerate(zip(xs, ys)):
        cmd = 'M' if i == 0 else 'L'
        parts.append(f'{cmd}{xmap(x):.2f},{ymap(y):.2f}')
    return ' '.join(parts)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    dev, dev_name = load_points(DEV)
    tgt, tgt_name = load_points(TGT)
    grid = log_grid()
    raw = [interp(dev, f) for f in grid]
    tgt = [interp(tgt, f) for f in grid]
    # align both to 0 dB mean in 500-2000 like AutoEq center
    def center_ys(ys):
        sel = [y for f, y in zip(grid, ys) if 500 <= f <= 2000]
        c = sum(sel) / max(len(sel), 1)
        return [y - c for y in ys]
    raw = center_ys(raw)
    tgt = center_ys(tgt)
    # simple residual-driven EQ toward target
    eq = []
    eqd = []
    for f, r, t in zip(grid, raw, tgt):
        # gentle gain toward difference, capped
        need = max(-12.0, min(12.0, t - r))
        # blend analytic demo bands + residual for illustration
        e = 0.55 * eq_db(f) + 0.45 * need
        e = max(-12.0, min(12.0, e))
        eq.append(e)
        eqd.append(r + e)

    # SVG layout
    W, H = 960, 520
    L, R, T, B = 64, 24, 36, 52
    pw, ph = W - L - R, H - T - B

    def xmap(f):
        return L + (math.log10(f) - math.log10(20)) / (math.log10(20000) - math.log10(20)) * pw

    ymin, ymax = -18, 18

    def ymap(d):
        return T + (ymax - d) / (ymax - ymin) * ph

    colors = {
        'raw': '#9ca3af',
        'tgt': '#38bdf8',
        'eq': '#f59e0b',
        'eqd': '#2563eb',
    }

    # grid lines
    yticks = list(range(-15, 16, 5))
    xticks = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    xlabels = {20: '20', 50: '50', 100: '100', 200: '200', 500: '500',
               1000: '1k', 2000: '2k', 5000: '5k', 10000: '10k', 20000: '20k'}

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="PEQ auto-fit illustration">')
    svg.append(f'<rect width="{W}" height="{H}" fill="#0b1220"/>')
    svg.append(f'<text x="{W/2}" y="22" text-anchor="middle" fill="#e5e7eb" font-family="Segoe UI, PingFang SC, Microsoft YaHei, sans-serif" font-size="14" font-weight="600">Auto-fit preview · Raw → Target via parametric EQ</text>')
    # plot frame
    svg.append(f'<rect x="{L}" y="{T}" width="{pw}" height="{ph}" fill="#111827" stroke="#1f2937"/>')
    for y in yticks:
        yy = ymap(y)
        svg.append(f'<line x1="{L}" y1="{yy:.1f}" x2="{L+pw}" y2="{yy:.1f}" stroke="#1f2937" stroke-width="1"/>')
        svg.append(f'<text x="{L-8}" y="{yy+4:.1f}" text-anchor="end" fill="#6b7280" font-size="11" font-family="Segoe UI, sans-serif">{y}</text>')
    for f in xticks:
        xx = xmap(f)
        svg.append(f'<line x1="{xx:.1f}" y1="{T}" x2="{xx:.1f}" y2="{T+ph}" stroke="#1f2937" stroke-width="1"/>')
        svg.append(f'<text x="{xx:.1f}" y="{T+ph+18}" text-anchor="middle" fill="#6b7280" font-size="11" font-family="Segoe UI, sans-serif">{xlabels[f]}</text>')
    svg.append(f'<text x="{L+pw/2:.0f}" y="{H-12}" text-anchor="middle" fill="#9ca3af" font-size="12" font-family="Segoe UI, sans-serif">Frequency (Hz)</text>')
    svg.append(f'<text x="16" y="{T+ph/2:.0f}" text-anchor="middle" fill="#9ca3af" font-size="12" font-family="Segoe UI, sans-serif" transform="rotate(-90 16 {T+ph/2:.0f})">Level (dB)</text>')

    # curves
    svg.append(f'<path d="{path_from_xy(grid, raw, xmap, ymap)}" fill="none" stroke="{colors["raw"]}" stroke-width="1.8" opacity="0.95"/>')
    svg.append(f'<path d="{path_from_xy(grid, tgt, xmap, ymap)}" fill="none" stroke="{colors["tgt"]}" stroke-width="1.8" stroke-dasharray="6 4" opacity="0.95"/>')
    # EQ offset around 0
    svg.append(f'<path d="{path_from_xy(grid, eq, xmap, ymap)}" fill="none" stroke="{colors["eq"]}" stroke-width="1.6" opacity="0.9"/>')
    svg.append(f'<path d="{path_from_xy(grid, eqd, xmap, ymap)}" fill="none" stroke="{colors["eqd"]}" stroke-width="2.4" opacity="0.95"/>')

    # legend
    lx, ly = L + 16, T + 18
    items = [
        (colors['raw'], 'Raw (device)', False),
        (colors['tgt'], 'Target', True),
        (colors['eq'], 'EQ filter response', False),
        (colors['eqd'], 'Equalized', False),
    ]
    svg.append(f'<rect x="{lx-8}" y="{ly-14}" width="220" height="96" rx="8" fill="#0f172a" stroke="#334155" opacity="0.92"/>')
    for i, (c, label, dashed) in enumerate(items):
        yy = ly + i * 20
        dash = ' stroke-dasharray="6 4"' if dashed else ''
        svg.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+28}" y2="{yy}" stroke="{c}" stroke-width="2.5"{dash}/>')
        svg.append(f'<text x="{lx+36}" y="{yy+4}" fill="#e5e7eb" font-size="12" font-family="Segoe UI, PingFang SC, sans-serif">{label}</text>')

    # footer note
    svg.append(f'<text x="{L}" y="{H-12}" fill="#64748b" font-size="11" font-family="Segoe UI, sans-serif">Illustrative curve generated from public sample data (not a live fit).</text>')
    svg.append('</svg>')

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(svg))
    print('wrote', OUT, 'bytes', os.path.getsize(OUT))
    print('device', dev_name, 'target', tgt_name, 'points', len(grid))


if __name__ == '__main__':
    main()
