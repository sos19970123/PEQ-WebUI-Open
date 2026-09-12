# -*- coding: utf-8 -*-
"""扫描 targets 目录所有曲线的低频抬升情况"""
import json, os, glob

d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curves", "targets")
files = sorted(glob.glob(os.path.join(d, "*.json")))

def val_at(points, freq):
    """取最接近 freq 的 dB 值"""
    best = None
    for f, db in points:
        if best is None or abs(f - freq) < abs(best[0] - freq):
            best = (f, db)
    return best[1] if best else None

print(f"{'id':<45} {'20Hz':>7} {'50Hz':>7} {'100Hz':>7} {'200Hz':>7} {'bass_range':>10}")
print("-" * 90)
for fp in files:
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"{os.path.basename(fp):<45} ERROR: {e}")
        continue
    pts = data.get("points", [])
    if not pts:
        print(f"{data.get('id','?'):<45} (no points)")
        continue
    v20 = val_at(pts, 20); v50 = val_at(pts, 50)
    v100 = val_at(pts, 100); v200 = val_at(pts, 200)
    # bass 抬升判定: 20Hz 或 50Hz 相对 200Hz 有没有 >2dB 抬升
    ref = v200 if v200 is not None else 0
    bass_peak = max([x for x in (v20, v50, v100) if x is not None] + [-999])
    diff = bass_peak - ref
    flag = "BASS-UP" if diff > 2 else ("flat/low" if diff > -0.5 else "NO-BASS")
    print(f"{data.get('id','?'):<45} {v20:>7.2f} {v50:>7.2f} {v100:>7.2f} {v200:>7.2f} {diff:>8.2f}  {flag}")
