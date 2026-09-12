# -*- coding: utf-8 -*-
"""构建水月雨 VDSF 目标曲线 → peq-webui curves/targets/moondrop-vdsf.json

数据源: ankramutt.squig.link/data/VDSF Target.txt (REW 格式, 958 pts, 20Hz-20kHz)
归一化: 500-2000Hz 均值归零(与库内设备曲线/目标曲线惯例一致)
产物:
  - peq-webui/curves/targets/moondrop-vdsf.json (webui 热加载)
  - measurements/targets/Moondrop VDSF.csv (归档)
"""
import csv
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, "vdsf_target_raw.txt")
WEBUI = os.path.abspath(os.path.join(BASE, "..", "peq-webui"))
sys.path.insert(0, WEBUI)
from curve_align import align_points_to_reference  # noqa: E402

# 1. 解析 REW 文件: 注释行以 * 开头, 数据两列 Freq(Hz)\tSPL(dB)
points = []
with open(RAW, "r", encoding="utf-8-sig", errors="replace") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("*"):
            continue
        parts = line.replace(",", "\t").split()
        if len(parts) < 2:
            continue
        try:
            freq = float(parts[0])
            db = float(parts[1])
        except ValueError:
            continue
        if 0 < freq <= 20000 and -200 < db < 200:
            points.append([freq, db])

points.sort(key=lambda p: p[0])
print(f"parsed points: {len(points)}, freq {points[0][0]}-{points[-1][0]} Hz")

# 2. 归一化: 500-2000Hz 均值归零
aligned, offset = align_points_to_reference(points, ref_low=500, ref_high=2000, method="mean")
print(f"alignment offset: {offset:.4f} dB (500-2000Hz mean)")
dbs = [p[1] for p in aligned]
print(f"aligned db range: {min(dbs):.2f} .. {max(dbs):.2f}")

# 3. 写 target json
target = {
    "id": "moondrop-vdsf",
    "name": "水月雨 VDSF",
    "kind": "target",
    "category": "common",
    "source": "ankramutt-squig",
    "target_type": "vdsf",
    "alignment": {
        "enabled": True,
        "method": "mean",
        "ref_low": 500.0,
        "ref_high": 2000.0,
        "offset_db": round(offset, 4),
    },
    "measurement_source": "Ankramutt squig (ankramutt.squig.link) data/VDSF Target.txt, REW import 2023-05-29, 958 pts 20Hz-20kHz, 1/48 oct",
    "measurement_url": "https://ankramutt.squig.link/data/VDSF%20Target.txt",
    "extracted_date": "2026-08-29",
    "points": [[round(p[0], 3), round(p[1], 3)] for p in aligned],
}

out_json = os.path.join(WEBUI, "curves", "targets", "moondrop-vdsf.json")
with open(out_json, "w", encoding="utf-8", newline="\n") as f:
    json.dump(target, f, ensure_ascii=False, indent=2)
print(f"wrote {out_json} ({len(target['points'])} pts)")

# 4. 归档 CSV
os.makedirs(os.path.join(BASE, "targets"), exist_ok=True)
out_csv = os.path.join(BASE, "targets", "Moondrop VDSF.csv")
with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["frequency", "db"])
    for p in aligned:
        w.writerow([f"{p[0]:.3f}", f"{p[1]:.3f}"])
print(f"wrote {out_csv}")

# 5. 验证
sys.path.insert(0, WEBUI)
from curve_store import CurveStore  # noqa: E402
s = CurveStore()
t = s.get_target("moondrop-vdsf")
print("CurveStore.get_target ->", t["id"], t["name"], "pts:", len(t["points"]))
