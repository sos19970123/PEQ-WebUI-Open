# -*- coding: utf-8 -*-
# Verify RAA E40 extracted curves + render SVG overlay (stdlib only)
import csv, math, os

DIR = r"F:\Hermes-Deepseek\headphone-lab\measurements\raa-e40"
C0 = "RAA_E40_c0_Frequency_response_SIEC_Summar_"
C3 = "RAA_E40_c3_Sensitivity_and_Frequency_resp_E40.csv"

def load(name):
    xs = []
    with open(os.path.join(DIR, name)) as f:
        for row in csv.DictReader(f):
            xs.append((float(row['freq']), float(row['dB'])))
    return xs

E40 = load(C0 + 'E40.csv')
HRAW = load(C0 + 'HarmanRaw.csv')
HSM = load(C0 + 'HarmanSmooth.csv')
SPL = load(C3)

# --- sanity checks ---
assert len(E40) == len(HRAW) == len(HSM) == 251, (len(E40), len(HRAW), len(HSM))
assert E40[0][0] > 19.5 and E40[0][0] < 20.5
assert 19000 < E40[-1][0] < 20100
ratios = [E40[i+1][0]/E40[i][0] for i in range(250)]
assert max(ratios) - min(ratios) < 0.005, "log spacing not uniform"

# cross-check: c0 relative curve must equal c3 absolute SPL minus a constant
spl1k = min(SPL, key=lambda p: abs(p[0]-1000))[1]
rel1k = min(E40, key=lambda p: abs(p[0]-1000))[1]
offs = spl1k - rel1k
dev = max(abs((s[1]-offs) - e[1]) for s, e in zip(SPL, E40))

def at(curve, f):
    return min(curve, key=lambda p: abs(p[0]-f))

anchors = {}
for f in (20, 100, 500, 1000, 3000, 5000, 8000, 10000, 15000, 19000):
    anchors[f] = round(at(E40, f)[1], 2)
peak = max(E40[15:200], key=lambda p: p[1])
dip = min([p for p in E40 if 100 < at(E40, p[0])[0] and 5000 < p[0] < 9000], key=lambda p: p[1])
h1k = at(HSM, 1000)[1]

print(f"points: {len(E40)}  span: {E40[0][0]:.1f}-{E40[-1][0]:.0f} Hz  log-step uniform: True")
print(f"SPL@1k: {spl1k:.1f} dB  (RAA spec sensitivity: 127.2 dB/1mW)")
print(f"c0 rel vs c3 SPL-const: max dev {dev:.3f} dB (offset {offs:+.2f})")
print("E40 anchors:", anchors)
print(f"bass tilt 20Hz-1kHz: {anchors[20]-rel1k:+.2f} dB | mid peak: {peak[1]-rel1k:+.1f} dB @ {peak[0]:.0f} Hz | 5-9k dip: {dip[1]-rel1k:+.1f} dB @ {dip[0]:.0f} Hz")
print(f"HarmanSmooth@1k: {h1k:+.2f} dB (target line, sanity ~+1)")

# --- SVG: E40 vs Harman smoothed ---
W, H = 900, 460
L, R_, T, Bo = 60, 20, 20, 45
x0, x1 = math.log10(20), math.log10(20000)
y0, y1 = -40, 15
def X(f): return L + (math.log10(f)-x0)/(x1-x0)*(W-L-R_)
def Y(v): return T + (y1-v)/(y1-y0)*(H-T-Bo)

svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">',
       f'<rect width="{W}" height="{H}" fill="#fafafa"/>',
       f'<text x="{W/2}" y="14" text-anchor="middle" font-size="14">ATH-E40 — RAA SIEC rig, extracted from canvas vector data (1kHz-normalized)</text>']
for f in (20,50,100,200,500,1000,2000,5000,10000,20000):
    lbl = str(f if f < 1000 else f//1000) + ("k" if f >= 1000 else "")
    svg.append(f'<line x1="{X(f):.1f}" y1="{T}" x2="{X(f):.1f}" y2="{H-Bo}" stroke="#ddd"/>'
               f'<text x="{X(f):.1f}" y="{H-Bo+14}" text-anchor="middle" font-size="10" fill="#666">{lbl}</text>')
for v in range(-40, 16, 5):
    svg.append(f'<line x1="{L}" y1="{Y(v):.1f}" x2="{W-R_}" y2="{Y(v):.1f}" stroke="#ddd"/>'
               f'<text x="{L-6}" y="{Y(v)+3:.1f}" text-anchor="end" font-size="10" fill="#666">{v:+d}</text>')
def path(curve, color, width, dash=''):
    d = 'M' + ' L'.join(f'{X(f):.1f},{Y(v):.1f}' for f, v in curve)
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>'
svg.append(path([(f, v-rel1k) for f, v in HSM], '#e8a15d', 1.6, ' stroke-dasharray="5,3"'))
svg.append(path([(f, v-rel1k) for f, v in E40], '#094A78', 2.2))
svg.append(f'<text x="{W-R_-10}" y="{T+16}" text-anchor="end" font-size="11" fill="#094A78">ATH-E40 (RAA SIEC)</text>')
svg.append(f'<text x="{W-R_-10}" y="{T+32}" text-anchor="end" font-size="11" fill="#e8a15d">Harman IE 2019 target (711/SIEC)</text>')
svg.append('</svg>')
out = os.path.join(DIR, 'RAA_E40_SIEC_FR.svg')
open(out, 'w').write('\n'.join(svg))
print("SVG ->", out)
