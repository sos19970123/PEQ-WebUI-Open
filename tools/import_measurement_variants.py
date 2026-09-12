# -*- coding: utf-8 -*-
"""
import_measurement_variants.py - 从本地 AutoEq 测量库导入设备频响的多个 rig 版本

背景（《开发维护文档.md》§7.10/§11.6）:
- 同一只耳机的“原始频响”在网络上存在多个测量版本，差异来自测量 rig（人工耳/人头 + 补偿策略）。
- 本工具把 AutoEq 测量库（measurements/<source>/data/over-ear/*.csv 的 frequency,raw 列）
  转成 peq-webui curves/devices/<device>-<source>.json，并在 JSON 中写入 rig 元数据，
  供前端下拉框展示 rig 标签与策略说明。

用法:
    py tools/import_measurement_variants.py
环境变量:
    AUTOEQ_ROOT  本地 AutoEq 根目录（默认 <项目根>/../AutoEq-4.1.2/AutoEq-4.1.2）
    PEWEBUI_DIR  peq-webui 目录（默认本文件所在目录的上级）

生成的文件（同一设备多个版本全部列出）:
    DT 900 Pro X   dt900prox[.json]  dt900prox-rtings  dt900prox-superreview  dt900prox-kuulokenurkka
    ATH-R70X       r70x[.json]       r70x-rtings       r70x-innerfidelity     r70x-kuulokenurkka
                   r70x-auriculares-argentina
    （id 不带 -source 的为默认/推荐版本 = oratory1990，保持与历史预设的 device_id 兼容）
"""
import csv
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # peq-webui/
AUTOEQ_ROOT = os.environ.get(
    'AUTOEQ_ROOT',
    os.path.normpath(os.path.join(BASE_DIR, '..', 'AutoEq-4.1.2', 'AutoEq-4.1.2')),
)
DEVICES_DIR = os.path.join(BASE_DIR, 'curves', 'devices')

# 设备英文名 -> (id 前缀, 中文名, kind, AutoEq 测量文件相对路径)
DEVICES = [
    ('dt900prox', '拜亚动力 DT 900 Pro X', 'headphone',
     'measurements/oratory1990/data/over-ear/Beyerdynamic DT 900 Pro X.csv'),
    ('dt900prox-rtings', '拜亚动力 DT 900 Pro X', 'headphone',
     'measurements/Rtings/data/over-ear/Beyerdynamic DT 900 Pro X.csv'),
    ('dt900prox-superreview', '拜亚动力 DT 900 Pro X', 'headphone',
     'measurements/Super Review/data/over-ear/Beyerdynamic DT 900 Pro X.csv'),
    ('dt900prox-kuulokenurkka', '拜亚动力 DT 900 Pro X', 'headphone',
     'measurements/Kuulokenurkka/data/over-ear/Beyerdynamic DT 900 Pro X.csv'),
    ('r70x', '铁三角 ATH-R70X', 'headphone',
     'measurements/oratory1990/data/over-ear/Audio-Technica ATH-R70x.csv'),
    ('r70x-rtings', '铁三角 ATH-R70X', 'headphone',
     'measurements/Rtings/data/over-ear/Audio-Technica ATH-R70x.csv'),
    ('r70x-innerfidelity', '铁三角 ATH-R70X', 'headphone',
     'measurements/Innerfidelity/data/over-ear/Audio-Technica ATH-R70x.csv'),
    ('r70x-kuulokenurkka', '铁三角 ATH-R70X', 'headphone',
     'measurements/Kuulokenurkka/data/over-ear/Audio-Technica ATH-R70x.csv'),
    ('r70x-auriculares-argentina', '铁三角 ATH-R70X', 'headphone',
     'measurements/Auriculares Argentina/data/over-ear/Audio-Technica ATH-R70x.csv'),
]

# source -> rig 元数据（rig 值取自 AutoEq measurements/<source>/name_index.tsv 的 rig 列）
RIG_META = {
    'oratory1990': {
        'source': 'oratory1990',
        'variant': 'oratory1990',
        'rig': 'GRAS 45BC-10',
        'rig_family': 'KEMAR HATS',
        'rig_standard': 'GRAS 45BC-10 KEMAR 型头身模拟器（Head-and-Torso Simulator）',
        'rig_note': 'oratory1990 团队/AutoEq 校准基准，与 Harman 目标同源。低频到中高频参考价值最高，'
                    '本库默认/推荐版本。早期资料中其部分测量使用 GRAS 43AG-7 / 43AC（IEC 60318-4 类）。',
        'url': 'https://www.reddit.com/r/oratory1990/wiki/index/list_of_presets/',
        'default': True,
    },
    'rtings': {
        'source': 'rtings',
        'variant': 'RTINGS',
        'rig': 'HMS II.3',
        'rig_family': 'HATS',
        'rig_standard': 'HEAD acoustics HMS II.3 头身模拟器（HATS，IEC 60268-7 耳廓 + HRTF 补偿）',
        'rig_note': 'RTINGS 旧版原始频响图（AutoEq 收录时其 rig 记录为 HMS II.3）。'
                    'RTINGS 官方现行测试台已改用 B&K 5128-B HATS，官网新图与这份数据基线不同。',
        'url': 'https://www.rtings.com/headphones/tests/sound-quality',
        'default': False,
    },
    'innerfidelity': {
        'source': 'innerfidelity',
        'variant': 'InnerFidelity',
        'rig': 'HMS II.3',
        'rig_family': 'HATS',
        'rig_standard': 'HEAD acoustics HMS II.3 人头模拟器（IEC 60268-7 耳廓，HRTF 补偿，5 次佩戴平均）',
        'rig_note': 'Tyll Hertsens 的 InnerFidelity 测量程序说明同样使用 HMS II.3。历史站点已关闭，'
                    '此数据经 AutoEq 归档。',
        'url': 'https://www.stereophile.com/content/innerfidelity-headphone-measurement-procedures',
        'default': False,
    },
    'kuulokenurkka': {
        'source': 'kuulokenurkka',
        'variant': 'Kuulokenurkka',
        'rig': 'KB501x + 711',
        'rig_family': '711 coupler',
        'rig_standard': 'GRAS KB501x 人工耳廓 + IEC 60318-4（“711”）模拟耳',
        'rig_note': '芬兰耳机评测站 Kuulokenurkka，数据经 kuulokenurkka.squig.link。'
                    '曾使用 MiniDSP EARS（HEQ 补偿），现在其 rig 记录为 KB501x + 711。',
        'url': 'https://kuulokenurkka.com/en/headphone-frequency-response-measurements-with-the-minidsp-ears-device/',
        'default': False,
    },
    'auriculares-argentina': {
        'source': 'auriculares-argentina',
        'variant': 'Auriculares Argentina',
        'rig': 'KB501x + 711',
        'rig_family': '711 coupler',
        'rig_standard': 'GRAS KB501x 人工耳廓 + IEC 60318-4（“711”）模拟耳',
        'rig_note': '阿根廷评测站 Auriculares Argentina，数据经 auricularesargentina.squig.link。',
        'url': 'https://auricularesargentina.squig.link/',
        'default': False,
    },
    'superreview': {
        'source': 'superreview',
        'variant': 'Super* Review',
        'rig': 'KB006x + 711',
        'rig_family': '711 coupler',
        'rig_standard': 'GRAS KB006x 人工耳廓（克隆） + IEC 60318-4（“711”）模拟耳',
        'rig_note': 'Super* Review（squig.link 主站）的耳机测量。KB006x 克隆 rig 亦被众多发烧友/评测者使用；'
                    '其 IEM 测量在 squig.link 上标注 rig 为 “clone IEC 711”。',
        'url': 'https://squig.link/',
        'default': False,
    },
}


def read_raw_csv(path):
    """读取 AutoEq 测量 CSV 的 frequency,raw 两列 -> [[freq, db], ...]（毫升排序，4 位有效）。"""
    pts = []
    with open(path, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            try:
                freq = float(row['frequency'])
                db = float(row['raw'])
            except (KeyError, TypeError, ValueError):
                continue
            if freq > 0 and -60 <= db <= 60:
                pts.append([round(freq, 4), round(db, 2)])
    pts.sort(key=lambda x: x[0])
    # 合并重复频率
    merged = []
    for freq, db in pts:
        if merged and merged[-1][0] == freq:
            merged[-1][1] = db
        else:
            merged.append([freq, db])
    return merged


def main():
    os.makedirs(DEVICES_DIR, exist_ok=True)
    written = []
    for cid, name, kind, relpath in DEVICES:
        csv_path = os.path.join(AUTOEQ_ROOT, relpath)
        if not os.path.exists(csv_path):
            print('SKIP  missing {} -> {}'.format(csv_path, cid))
            continue
        points = read_raw_csv(csv_path)
        source = cid.split('-', 1)[1] if '-' in cid else 'oratory1990'
        meta = RIG_META[source]
        obj = {
            'id': cid,
            'name': name,
            'kind': kind,
            'source': meta['source'],
            'variant': meta['variant'],
            'rig': meta['rig'],
            'rig_family': meta['rig_family'],
            'rig_standard': meta['rig_standard'],
            'rig_note': meta['rig_note'],
            'url': meta['url'],
            'default': meta['default'],
            'points': points,
        }
        path = os.path.join(DEVICES_DIR, cid + '.json')
        with open(path, 'wb') as f:
            f.write(json.dumps(obj, ensure_ascii=False, indent=1).encode('utf-8'))
        written.append((cid, len(points), meta['rig']))
        print('OK   {:34s} {} pts  rig={}'.format(cid, len(points), meta['rig']))
    print('\n共写入 {} 个设备频响版本。'.format(len(written)))


if __name__ == '__main__':
    main()