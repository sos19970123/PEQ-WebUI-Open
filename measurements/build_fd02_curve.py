# -*- coding: utf-8 -*-
"""
build_fd02_curve.py - 用 crinacle graph.hangout.audio 工具提取的原始 L/R 测量
重建 peq-webui 的 fd02 设备曲线(替换旧的图片描点数据)。

数据来源: graph.hangout.audio/iem/711/ 页面 #fr-graph SVG path.__data__.p.rawChannels
(未做 bass/tilt 调整的原始声道数据, 480 点, 20Hz-20.2kHz)
"""
import json
import os
import sys

TEMP = os.environ.get('TEMP', r'C:\Users\97405\AppData\Local\Temp')
PEQ_DIR = r'F:\MIMO-Space\PEQ-WebUI'
MEAS_DIR = r'F:\MIMO-Space\PEQ-WebUI\measurements'

sys.path.insert(0, PEQ_DIR)
from curve_align import align_points_to_reference  # noqa: E402

# 1. 读取 WebBridge 抓回来的声道数据
wrapper_path = os.path.join(TEMP, 'fd02_channels.json')
with open(wrapper_path, 'rb') as f:
    wrapper = json.loads(f.read().decode('utf-8-sig'))
value = json.loads(wrapper['data']['value']) if isinstance(wrapper.get('data', {}).get('value'), str) else wrapper['data']['value']
ch_l = [[float(a), float(b)] for a, b in value['ch0']]
ch_r = [[float(a), float(b)] for a, b in value['ch1']]
assert len(ch_l) == len(ch_r) == 480, f'点数异常: {len(ch_l)}/{len(ch_r)}'
for (fl, dl), (fr, dr) in zip(ch_l, ch_r):
    assert abs(fl - fr) < 1e-9, f'声道频率不一致: {fl} vs {fr}'

# 2. L/R 平均
avg = [[fl, round((dl + dr) / 2.0, 5)] for (fl, dl), (_, dr) in zip(ch_l, ch_r)]

# 3. 与库内其他曲线一致的对齐(500-2000Hz 均值 -> 0)
aligned, offset = align_points_to_reference(avg, ref_low=500.0, ref_high=2000.0, method='mean')
print(f'points: {len(aligned)}, align_offset: {offset:.4f} dB')
print(f'range after align: {min(d for _, d in aligned):.2f} .. {max(d for _, d in aligned):.2f} dB')

# 4. 写设备曲线(覆盖 fd02.json, 老文件已有备份 + git 兜底)
curve = {
    'id': 'fd02',
    'name': 'JVC HA-FD02',
    'kind': 'iem',
    'source': 'crinacle',
    'points': [[f, round(d, 4)] for f, d in aligned],
    'alignment': {
        'enabled': True,
        'method': 'mean',
        'ref_low': 500.0,
        'ref_high': 2000.0,
        'offset_db': round(float(offset), 4),
    },
    'measurement_rig': 'IEC60318-4 (711 coupler)',
    'measurement_source': 'crinacle / graph.hangout.audio iem 711 tool (L+R avg, 480 pts)',
    'measurement_url': 'https://graph.hangout.audio/iem/711/?share=FD02',
    'extracted_date': '2026-08-28',
}
out_path = os.path.join(PEQ_DIR, 'curves', 'devices', 'fd02.json')
with open(out_path, 'wb') as f:
    f.write(json.dumps(curve, ensure_ascii=False, indent=2).encode('utf-8'))
print('written:', out_path)

# 5. 归档原始数据(用户规则: 数据按项目归档)
def write_csv(path, pts):
    with open(path, 'w', encoding='utf-8') as f:
        f.write('frequency_hz,relative_db\n')
        for fr, db in pts:
            f.write(f'{fr},{db}\n')

write_csv(os.path.join(MEAS_DIR, 'fd02_crinacle_raw_L.csv'), ch_l)
write_csv(os.path.join(MEAS_DIR, 'fd02_crinacle_raw_R.csv'), ch_r)
write_csv(os.path.join(MEAS_DIR, 'fd02_crinacle_avg_aligned.csv'), aligned)
print('archived: fd02_crinacle_raw_L.csv / fd02_crinacle_raw_R.csv / fd02_crinacle_avg_aligned.csv')

# 6. 用 CurveStore 验证加载
from curve_store import CurveStore  # noqa: E402
item = CurveStore().get_device('fd02')
print(f"CurveStore check: id={item['id']} name={item['name']} kind={item['kind']} points={len(item['points'])}")
