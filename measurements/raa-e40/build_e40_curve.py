# -*- coding: utf-8 -*-
"""
build_e40_curve.py - 用 RAA(reference-audio-analyzer.pro)报告 #796 的 canvas
矢量数据还原 ATH-E40 频响, 建 peq-webui 的 e40 设备曲线。

数据来源: RAA report 796 (SIEC 台架, Right+Left summary), 从页面内联
FR-SCRIPT 绘图指令解析逆映射提取(见 measurements/raa-e40/extract-raa.ps1),
251 点对数网格 20Hz-19.45kHz, RAA 原生 1kHz 归一。
入库时按库惯例再对齐: 500-2000Hz 均值 -> 0。
"""
import csv
import json
import os
import sys

PEQ_DIR = r'F:\Hermes-Deepseek\headphone-lab\peq-webui'
MEAS_DIR = r'F:\Hermes-Deepseek\headphone-lab\measurements\raa-e40'

sys.path.insert(0, PEQ_DIR)
from curve_align import align_points_to_reference  # noqa: E402

# 1. 读取 RAA 提取的 E40 曲线(canvas0, Frequency response SIEC Summary R+L)
src = os.path.join(MEAS_DIR, 'RAA_E40_c0_Frequency_response_SIEC_Summar_E40.csv')
points = []
with open(src, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        points.append([float(row['freq']), float(row['dB'])])
assert len(points) == 251, f'点数异常: {len(points)}'
assert abs(points[0][0] - 20.0) < 0.5 and 19000 < points[-1][0] < 20100

# 2. 按库惯例对齐(500-2000Hz 均值 -> 0)
aligned, offset = align_points_to_reference(points, ref_low=500.0, ref_high=2000.0, method='mean')
print(f'points: {len(aligned)}, align_offset: {offset:.4f} dB')
lo = min(d for _, d in aligned); hi = max(d for _, d in aligned)
print(f'range after align: {lo:.2f} .. {hi:.2f} dB')
assert -60 <= lo and hi <= 60, '超出 curve_store 归一化范围'

# 3. 写设备曲线(新增 curves/devices/e40.json, 覆盖内置空元数据)
curve = {
    'id': 'e40',
    'name': '铁三角 ATH-E40',
    'kind': 'iem',
    'source': 'RAA',
    'points': [[f, round(d, 4)] for f, d in aligned],
    'alignment': {
        'enabled': True,
        'method': 'mean',
        'ref_low': 500.0,
        'ref_high': 2000.0,
        'offset_db': round(float(offset), 4),
    },
    'measurement_rig': 'SIEC stand (711 coupler based, RAA proprietary)',
    'measurement_source': 'Reference Audio Analyzer report #796, canvas vector extraction (R+L summary, 251 pts)',
    'measurement_url': 'https://reference-audio-analyzer.pro/en/report/hp/audio-technica-ath-e40.php',
    'extracted_date': '2026-08-29',
}
out_path = os.path.join(PEQ_DIR, 'curves', 'devices', 'e40.json')
with open(out_path, 'wb') as f:
    f.write(json.dumps(curve, ensure_ascii=False, indent=2).encode('utf-8'))
print('written:', out_path)

# 4. 归档对齐后的均值曲线(原始提取 CSV 已在 raa-e40/)
arch = os.path.join(MEAS_DIR, 'e40_raa_avg_aligned.csv')
with open(arch, 'w', encoding='utf-8') as f:
    f.write('frequency_hz,relative_db\n')
    for fr, db in aligned:
        f.write(f'{fr},{round(db, 4)}\n')
print('archived:', arch)

# 5. 用 CurveStore 验证加载
from curve_store import CurveStore  # noqa: E402
item = CurveStore().get_device('e40')
print(f"CurveStore check: id={item['id']} name={item['name']} kind={item['kind']} "
      f"source={item['source']} points={len(item['points'])}")
