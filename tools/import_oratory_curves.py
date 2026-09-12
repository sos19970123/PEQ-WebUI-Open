# -*- coding: utf-8 -*-
"""Convert oratory1990 frequency,raw CSV -> peq-webui curves/devices/<id>.json"""
import csv, json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEAS = os.path.join(BASE, 'measurements')
SRC = {
  'r70x': {
    'csv': os.path.join(MEAS, 'Audio-Technica ATH-R70x.csv'),
    'name': '铁三角 ATH-R70X',
    'kind': 'headphone',
    'source': 'oratory1990',
  },
  'dt900prox': {
    'csv': os.path.join(MEAS, 'Beyerdynamic DT 900 Pro X.csv'),
    'name': '拜亚动力 DT 900 Pro X',
    'kind': 'headphone',
    'source': 'oratory1990',
  },
}

CURVES_DIR = os.path.join(BASE, 'curves', 'devices')

def load_points(csvpath):
    pts = []
    with open(csvpath, 'r', encoding='utf-8-sig') as f:
        rd = csv.reader(f)
        header = next(rd, None)
        for row in rd:
            if len(row) < 2:
                continue
            try:
                freq = float(row[0])
                db = float(row[1])
            except ValueError:
                continue
            if 20 <= freq <= 20000 and -60 <= db <= 60:
                pts.append([freq, db])
    pts.sort(key=lambda x: x[0])
    return pts

def main():
    os.makedirs(CURVES_DIR, exist_ok=True)
    for cid, meta in SRC.items():
        pts = load_points(meta['csv'])
        print(f'{cid}: {len(pts)} points, {pts[0][0]:.2f}Hz..{pts[-1][0]:.2f}Hz')
        obj = {
            'id': cid,
            'name': meta['name'],
            'kind': meta['kind'],
            'source': meta['source'],
            'points': pts,
        }
        path = os.path.join(CURVES_DIR, cid + '.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False)
        print(f'  -> {path} ({os.path.getsize(path)} bytes)')

if __name__ == '__main__':
    main()
