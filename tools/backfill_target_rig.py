# -*- coding: utf-8 -*-
"""backfill_target_rig.py - 为目标曲线补齐 rig 元数据（需求 R1）

背景:
  curves/targets/*.json 里早期导入的目标曲线 source 多为 'imported'，
  缺少 rig / rig_family / measurement_rig / measurement_url 等字段，
  导致前端与后端无法做跨 rig 拟合防护。

做什么:
  1. 修正常见别名：measurement_rig <- rig，measurement_url <- url。
  2. rig_family / rig_standard 缺失时用 AutoEqStore 的规则推导。
  3. source == 'imported' 时，优先用已有 measurement_source / variant，
     否则用本地 AutoEq 索引按“设备名 + 频响 RMS 比对”找回真实测量者与 rig。
  4. 只写缺失/为 imported 的字段，不覆盖用户手工填写的元数据。

用法:
  py tools/backfill_target_rig.py            # 预览（dry-run，不写盘）
  py tools/backfill_target_rig.py --apply    # 实际写盘
  py tools/backfill_target_rig.py --apply --target-id sennheiser-hd-490-pro-原始频响
"""
import argparse
import csv
import io
import json
import os
import re
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from autoeq_store import AutoEqStore, _rig_family_standard  # noqa: E402

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy 在项目环境中必然存在
    np = None

TARGETS_DIR = os.path.join(BASE_DIR, 'curves', 'targets')

META_FIELDS = (
    'source', 'measured_device', 'measurement_source', 'variant',
    'rig', 'rig_family', 'rig_standard', 'rig_note',
    'measurement_rig', 'measurement_url', 'url',
)


def normalize_name(value):
    s = str(value or '').lower()
    s = s.replace('原始频响', '').replace('鍘熷棰戝搷', '')
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'\btarget\b', '', s)
    s = re.sub(r'[^a-z0-9\u4e00-\u9fff]+', '', s)
    return s


def read_points(path):
    with open(path, 'rb') as f:
        obj = json.loads(f.read().decode('utf-8-sig'))
    out = []
    for p in obj.get('points') or []:
        try:
            freq, db = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if freq > 0:
            out.append((freq, db))
    out.sort(key=lambda x: x[0])
    return out


def read_csv_raw_points(csv_path):
    try:
        with open(csv_path, 'rb') as f:
            text = f.read().decode('utf-8-sig', errors='replace')
    except OSError:
        return []
    points = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            freq = float(row.get('frequency', ''))
            value = row.get('raw')
            if value in (None, ''):
                continue
            points.append((freq, float(value)))
        except (TypeError, ValueError):
            continue
    points.sort(key=lambda x: x[0])
    return points


def _align_np(points, lo=500.0, hi=2000.0):
    arr = np.asarray(points, dtype=float)
    mask = (arr[:, 0] >= lo) & (arr[:, 0] <= hi)
    if not mask.any():
        mask = np.ones(len(arr), dtype=bool)
    x = arr[:, 0]
    y = arr[:, 1] - float(arr[mask, 1].mean())
    return x, y


def rms_between(a_points, b_points):
    """按 log 频率对齐后比较 20Hz-20kHz RMS（都先做参考频段均值对齐）。"""
    if np is None or len(a_points) < 2 or len(b_points) < 2:
        return None
    ax, ay = _align_np(a_points)
    bx, by = _align_np(b_points)
    grid = np.geomspace(20.0, 20000.0, 256)
    ayi = np.interp(np.log(grid), np.log(ax), ay)
    byi = np.interp(np.log(grid), np.log(bx), by)
    return float(np.sqrt(np.mean((ayi - byi) ** 2)))


class AutoEqMatcher:
    def __init__(self):
        self.store = AutoEqStore()
        self.index = self.store.build_index()
        self.by_name = {}
        for entry in self.index:
            for key in {normalize_name(entry.get('name')), normalize_name(entry.get('id'))}:
                if key:
                    self.by_name.setdefault(key, []).append(entry)

    def candidates(self, curve):
        keys = [normalize_name(curve.get('name')), normalize_name(curve.get('id'))]
        for key in keys:
            if key and key in self.by_name:
                return list(self.by_name[key])
        # 宽松匹配：只用于唯一候选，避免张冠李戴
        loose = []
        for key in keys:
            if len(key) < 5:
                continue
            for cand_key, entries in self.by_name.items():
                if cand_key.startswith(key) or key.startswith(cand_key):
                    loose.extend(entries)
        uniq = {e['id']: e for e in loose}
        return list(uniq.values())

    def match(self, curve_path, curve, threshold=2.0):
        target_points = read_points(curve_path)
        cands = self.candidates(curve)
        if not cands:
            return None, 'no_candidate'
        if len(cands) == 1:
            return cands[0], 'unique_name'
        if not target_points:
            return None, 'ambiguous_no_points'
        scored = []
        for entry in cands:
            cand_points = read_csv_raw_points(entry.get('csv_path', ''))
            rms = rms_between(target_points, cand_points)
            if rms is not None:
                scored.append((rms, entry))
        if not scored:
            return None, 'ambiguous_no_csv'
        scored.sort(key=lambda x: x[0])
        best_rms, best = scored[0]
        if best_rms > threshold:
            return None, 'best_rms_%.2f' % best_rms
        return best, 'rms_%.2f' % best_rms


def resolve_metadata(entry, store=None):
    return (store or AutoEqStore()).measurement_meta(entry)


def patch_obj(obj, matched_meta):
    """就地补齐字段，返回实际修改的键值。"""
    changes = {}
    rig = str(obj.get('rig') or '').strip()
    if not rig and matched_meta:
        rig = str(matched_meta.get('rig') or '').strip()

    # 1) 别名
    if rig and not obj.get('measurement_rig'):
        obj['measurement_rig'] = rig
        changes['measurement_rig'] = rig
    url = obj.get('url') or (matched_meta.get('url') if matched_meta else '')
    url = str(url or '').strip()
    if url and not obj.get('measurement_url'):
        obj['measurement_url'] = url
        changes['measurement_url'] = url

    # 2) 从 rig 推导 family / standard
    if rig:
        fam, standard = _rig_family_standard(rig)
        if not obj.get('rig_family') and (fam or (matched_meta or {}).get('rig_family')):
            obj['rig_family'] = fam or matched_meta.get('rig_family')
            changes['rig_family'] = obj['rig_family']
        if not obj.get('rig_standard') and standard:
            obj['rig_standard'] = standard
            changes['rig_standard'] = standard
    if not obj.get('rig_note') and matched_meta and matched_meta.get('rig_note'):
        obj['rig_note'] = matched_meta['rig_note']
        changes['rig_note'] = obj['rig_note']

    # 3) source == imported 时找回真实测量者
    if str(obj.get('source') or '').strip().lower() in ('', 'imported'):
        src = ''
        for key in ('measurement_source', 'variant'):
            val = str(obj.get(key) or '').strip()
            if val and val.lower() != 'imported':
                src = val
                break
        if not src and matched_meta:
            src = str(matched_meta.get('source') or '').strip()
        if src:
            obj['source'] = src
            changes['source'] = src
        if not obj.get('measurement_source') and src:
            obj['measurement_source'] = src
            changes['measurement_source'] = src

    # 4) 匹配到的其它元数据（只补缺失）
    if matched_meta:
        for key in META_FIELDS:
            if key in ('source',):
                continue
            val = matched_meta.get(key)
            if val not in (None, '') and obj.get(key) in (None, ''):
                obj[key] = val
                changes[key] = val

    # 5) 分类兜底
    if not obj.get('category') and (obj.get('measured_device') or obj.get('rig') or obj.get('measurement_source')):
        obj['category'] = 'headphone'
        changes['category'] = 'headphone'
    return changes


def main():
    parser = argparse.ArgumentParser(description='为目标曲线补齐 rig 元数据')
    parser.add_argument('--apply', action='store_true', help='实际写盘（默认预览）')
    parser.add_argument('--target-id', default='', help='只处理指定 id')
    parser.add_argument('--threshold', type=float, default=2.0,
                        help='AutoEq RMS 匹配阈值(dB)，默认 2.0')
    args = parser.parse_args()

    matcher = AutoEqMatcher()
    files = []
    for fname in sorted(os.listdir(TARGETS_DIR)):
        if not fname.lower().endswith('.json'):
            continue
        cid = os.path.splitext(fname)[0]
        if args.target_id and cid != args.target_id:
            continue
        files.append(os.path.join(TARGETS_DIR, fname))

    touched = 0
    for path in files:
        cid = os.path.splitext(os.path.basename(path))[0]
        with open(path, 'rb') as f:
            obj = json.loads(f.read().decode('utf-8-sig'))

        need_match = (
            str(obj.get('source') or '').strip().lower() in ('', 'imported')
            or not str(obj.get('rig') or '').strip()
        )
        matched_meta = None
        note = ''
        if need_match:
            entry, note = matcher.match(path, obj, threshold=args.threshold)
            if entry:
                matched_meta = resolve_metadata(entry, store=matcher.store)

        changes = patch_obj(obj, matched_meta)
        if not changes:
            print(f'[skip] {cid}  {note}')
            continue
        touched += 1
        print(f'[{"write" if args.apply else "dry"}] {cid}  match={note}')
        for key, val in changes.items():
            print(f'    {key}: {val}')
        if args.apply:
            with open(path, 'wb') as f:
                f.write(json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8'))

    print()
    print(f'{"已写入" if args.apply else "待写入"} {touched} 个目标曲线文件'
          f'{"（dry-run，加 --apply 生效）" if not args.apply else ""}')


if __name__ == '__main__':
    main()
