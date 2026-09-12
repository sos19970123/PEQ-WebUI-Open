# -*- coding: utf-8 -*-
"""从 AutoEq targets 目录导入常用音频目标曲线到 peq-webui curves/targets，并补充 rig/标准字段。"""
import csv
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_AUTOEQ = os.path.normpath(os.path.join(BASE_DIR, '..', 'AutoEq-4.1.2', 'AutoEq-4.1.2'))
AUTOEQ_ROOT = os.environ.get('AUTOEQ_ROOT', _DEFAULT_AUTOEQ)
SRC = os.path.join(AUTOEQ_ROOT, 'targets')
OUT = os.path.join(BASE_DIR, 'curves', 'targets')

COMMON_FILES = [
    ("Diffuse field 5128.csv", {"id": "diffuse_field_5128", "name": "扩散场 5128 (B&K)", "target_type": "diffuse_field", "rig": "B&K 5128", "rig_family": "5128", "rig_standard": "B&K 5128 diffuse field target"}),
    ("Diffuse field 5128 -1dB per octave.csv", {"id": "diffuse-field-5128-1-db-oct", "name": "Diffuse Field 5128 (-1 dB/oct)", "target_type": "diffuse_field", "rig": "B&K 5128", "rig_family": "5128", "rig_standard": "B&K 5128 diffuse field target, -1 dB/oct slope"}),
    ("Diffuse field GRAS KEMAR.csv", {"id": "diffuse_field_gras_kemar", "name": "扩散场 GRAS KEMAR", "target_type": "diffuse_field", "rig": "GRAS KEMAR", "rig_family": "KEMAR HATS", "rig_standard": "GRAS KEMAR diffuse field target (oratory 族)"}),
    ("Diffuse field ISO 11904-1.csv", {"id": "diffuse_field", "name": "扩散场 ISO 11904-1", "target_type": "diffuse_field", "rig": "ISO 11904-1", "rig_family": "diffuse_field", "rig_standard": "ISO 11904-1 diffuse field"}),
    ("LMG 5128 0.6.csv", {"id": "lmg_5128_0_6", "name": "LMG 5128 0.6", "target_type": "lmg", "rig": "B&K 5128", "rig_family": "5128", "rig_standard": "LMG 5128 0.6 target"}),
    ("LMG 5128 0.6 without bass.csv", {"id": "lmg-5128-0-6-without-bass", "name": "LMG 5128 0.6 without bass", "target_type": "lmg", "rig": "B&K 5128", "rig_family": "5128", "rig_standard": "LMG 5128 0.6 target, without bass"}),
    ("711 5128 delta.csv", {"id": "711_5128_delta", "name": "711 5128 delta", "target_type": "delta", "rig_family": "delta", "rig_standard": "711 to 5128 delta compensation curve"}),
    ("Harman over-ear 2013.csv", {"id": "harman_overear_2013", "name": "Harman 头戴 2013", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman over-ear target 2013"}),
    ("Harman over-ear 2013 without bass.csv", {"id": "harman_overear_2013_without_bass", "name": "Harman 头戴 2013 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman over-ear target 2013 without bass"}),
    ("Harman over-ear 2015.csv", {"id": "harman_overear_2015", "name": "Harman 头戴 2015", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman over-ear target 2015"}),
    ("Harman over-ear 2015 without bass.csv", {"id": "harman_overear_2015_without_bass", "name": "Harman 头戴 2015 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman over-ear target 2015 without bass"}),
    ("Harman over-ear 2018.csv", {"id": "harman_overear_2018", "name": "Harman 头戴 2018", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman over-ear target 2018"}),
    ("Harman over-ear 2018 without bass.csv", {"id": "harman_overear_2018_without_bass", "name": "Harman 头戴 2018 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman over-ear target 2018 without bass"}),
    ("Harman in-ear 2016.csv", {"id": "harman_inear_2016", "name": "Harman 入耳 2016", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2016"}),
    ("Harman in-ear 2016 without bass.csv", {"id": "harman_inear_2016_without_bass", "name": "Harman 入耳 2016 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2016 without bass"}),
    ("Harman in-ear 2017-1.csv", {"id": "harman_inear_2017_1", "name": "Harman 入耳 2017-1", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2017-1"}),
    ("Harman in-ear 2017-1 without bass.csv", {"id": "harman_inear_2017_1_without_bass", "name": "Harman 入耳 2017-1 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2017-1 without bass"}),
    ("Harman in-ear 2017-2.csv", {"id": "harman_inear_2017_2", "name": "Harman 入耳 2017-2", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2017-2"}),
    ("Harman in-ear 2017-2 without bass.csv", {"id": "harman_inear_2017_2_without_bass", "name": "Harman 入耳 2017-2 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2017-2 without bass"}),
    ("Harman in-ear 2019.csv", {"id": "harman_in-ear_2019", "name": "Harman 入耳 2019", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2019"}),
    ("Harman in-ear 2019 without bass.csv", {"id": "harman_inear_2019_without_bass", "name": "Harman 入耳 2019 (no bass)", "target_type": "harman", "rig_family": "harman", "rig_standard": "Harman in-ear target 2019 without bass"}),
    ("AutoEq in-ear.csv", {"id": "autoeq-in-ear", "name": "AutoEq in-ear", "target_type": "autoeq", "rig_family": "autoeq", "rig_standard": "AutoEq in-ear target"}),
]

def slug_name(name):
    return re.sub(r'[^a-z0-9]+', '-', name.strip().lower()).strip('-') or 'auto-target'

def read_points(path):
    pts = []
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
        except Exception:
            f.seek(0)
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) < 2:
                    continue
                try:
                    pts.append([float(row[0]), float(row[1])])
                except ValueError:
                    continue
            pts.sort(key=lambda x: x[0])
            return pts
        # determine freq col and raw col
        freq_col = None
        raw_col = None
        for field in fields:
            fl = field.strip().lower()
            if freq_col is None and ('freq' in fl or fl.startswith('*')):
                freq_col = field
            if raw_col is None and (fl in ('raw', 'spl(db)', 'db', 'target')) and freq_col is not None:
                raw_col = field
        if freq_col is None:
            freq_col = fields[0]
        if raw_col is None:
            # 第二列（跳过 frequency 列）
            raw_col = fields[1] if len(fields) > 1 else fields[0]
        for row in reader:
            try:
                fr = float(str(row.get(freq_col, '')).strip().replace('*', '').strip())
                db = float(str(row.get(raw_col, '')).strip())
            except (TypeError, ValueError):
                continue
            if 20 <= fr <= 20000 and -60 <= db <= 60:
                pts.append([fr, db])
    pts.sort(key=lambda x: x[0])
    # 去重
    dedup = []
    for p in pts:
        if not dedup or p[0] != dedup[-1][0]:
            dedup.append(p)
    return dedup

def main():
    os.makedirs(OUT, exist_ok=True)
    if not os.path.isdir(SRC):
        print('SRC not found:', SRC)
        sys.exit(1)
    imported = []
    updated = []
    for fname, meta in COMMON_FILES:
        src_path = os.path.join(SRC, fname)
        if not os.path.isfile(src_path):
            print('skip missing:', fname)
            continue
        points = read_points(src_path)
        target_id = meta.get('id') or slug_name(meta.get('name') or fname)
        out_path = os.path.join(OUT, target_id + '.json')
        obj = {
            'id': target_id,
            'name': meta['name'],
            'kind': 'target',
            'category': 'common',
            'source': 'autoeq',
            'target_type': meta.get('target_type', ''),
            'rig': meta.get('rig', ''),
            'rig_family': meta.get('rig_family', ''),
            'rig_standard': meta.get('rig_standard', ''),
            'points': points,
        }
        if os.path.exists(out_path):
            try:
                with open(out_path, 'r', encoding='utf-8') as f:
                    old = json.load(f)
            except Exception:
                old = {}
            # 保留原 points，若旧 points 非空则沿用
            if old.get('points'):
                obj['points'] = old['points']
            # 合并额外字段，保留 id/name/kind 等
            for k, v in old.items():
                obj.setdefault(k, v)
            updated.append(target_id)
        else:
            imported.append(target_id)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        print(f'{target_id:45s} {len(obj["points"]):5d} pts -> {out_path}')
    print('imported:', imported or 'none')
    print('updated:', updated or 'none')

if __name__ == '__main__':
    main()
