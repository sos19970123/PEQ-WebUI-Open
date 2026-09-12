# -*- coding: utf-8 -*-
"""
curve_store.py - 本地曲线库（设备原始频响 / 目标曲线）

设计:
- 目录: curves/devices/*.json, curves/targets/*.json
- 热加载: 每次列表/读取重新扫描目录；单文件用 mtime 做内容缓存。
- 用户可手写 JSON 扩充；无需重启后端。
- 内置 6 台设备元数据在无曲线文件时仍出现在设备列表中。
"""
import json
import math
import os
import re
import time

from curve_align import align_points_to_reference
from rig_guard import rig_family_key

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CURVES_DIR = os.path.join(BASE_DIR, 'curves')
DEVICES_DIR = os.path.join(CURVES_DIR, 'devices')
TARGETS_DIR = os.path.join(CURVES_DIR, 'targets')

BUILTIN_DEVICES = [
    {"id": "r70x", "name": "铁三角 ATH-R70X", "kind": "headphone", "source": "oratory1990", "points": []},
    {"id": "dt900prox", "name": "拜亚动力 DT 900 Pro X", "kind": "headphone", "source": "oratory1990", "points": []},
    {"id": "t100", "name": "创新 T100", "kind": "speaker", "source": "manual/local", "points": []},
    {"id": "fd02", "name": "JVC HA-FD02", "kind": "iem", "source": "crinacle", "points": []},
    {"id": "e40", "name": "铁三角 ATH-E40", "kind": "iem", "source": "crinacle", "points": []},
    {"id": "xlm", "name": "原道小蓝帽", "kind": "earbud", "source": "manual/local", "points": []},
]

BUILTIN_TARGETS = [
    {"id": "harman_overear_2018", "name": "Harman 头戴 2018", "kind": "target", "category": "common", "points": []},
    {"id": "harman_in-ear_2019", "name": "Harman 入耳 2019", "kind": "target", "category": "common", "points": []},
    {"id": "diffuse_field", "name": "扩散场 Diffuse Field", "kind": "target", "category": "common", "points": []},
    {"id": "flat", "name": "平直 Flat", "kind": "target", "category": "common", "points": [[20, 0], [20000, 0]]},
]


def _ensure_dirs():
    for d in (DEVICES_DIR, TARGETS_DIR):
        os.makedirs(d, exist_ok=True)


def _slug(name):
    s = re.sub(r'[^\w\u4e00-\u9fff]+', '-', name.strip().lower()).strip('-')
    if not s:
        s = 'curve'
    return s


def _read_json(path):
    """读取并校验 JSON。返回 dict 或抛 ValueError。"""
    with open(path, 'rb') as f:
        raw = f.read().decode('utf-8-sig')
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError('曲线文件必须是 JSON 对象')
    return obj


def _normalize_points(points):
    out = []
    for p in points or []:
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            freq, db = float(p[0]), float(p[1])
        elif isinstance(p, dict) and 'freq' in p and 'db' in p:
            freq, db = float(p['freq']), float(p['db'])
        elif isinstance(p, dict) and 'frequency' in p and 'gain' in p:
            freq, db = float(p['frequency']), float(p['gain'])
        else:
            continue
        if freq <= 0 or not (-60 <= db <= 60):
            continue
        out.append([freq, db])
    out.sort(key=lambda x: x[0])
    # 合并重复 freq（保留后出现的值）
    merged = []
    for freq, db in out:
        if merged and merged[-1][0] == freq:
            merged[-1][1] = db
        else:
            merged.append([freq, db])
    return merged


def _interp_log(points, freq):
    """按 log10(f) 线性插值一个频点；输入 [[freq, db], ...]。"""
    if not points:
        return None
    pts = sorted(([float(p[0]), float(p[1])] for p in points if p and len(p) >= 2), key=lambda x: x[0])
    if not pts:
        return None
    if freq <= pts[0][0]:
        return pts[0][1]
    if freq >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        f0, d0 = pts[i - 1]
        f1, d1 = pts[i]
        if freq <= f1:
            if f1 <= f0 or f0 <= 0 or f1 <= 0:
                return d1
            t = (math.log10(freq) - math.log10(f0)) / (math.log10(f1) - math.log10(f0))
            return d0 + t * (d1 - d0)
    return pts[-1][1]


def apply_curve_delta(base_points, delta_points):
    """把 delta（如去 rig tilt）叠加到 base 曲线上，返回同频率采样点。"""
    if not base_points or not delta_points:
        return list(base_points or [])
    freqs = {20.0, 20000.0}
    for p in list(base_points) + list(delta_points):
        try:
            f = float(p[0])
        except (TypeError, ValueError, IndexError):
            continue
        if 20.0 <= f <= 20000.0:
            freqs.add(f)
    out = []
    for freq in sorted(freqs):
        b = _interp_log(base_points, freq)
        d = _interp_log(delta_points, freq)
        if b is None or d is None:
            continue
        out.append([round(freq, 4), round(b + d, 4)])
    return out


def _default_target_category(obj):
    """目标曲线缺省分类：导入的其他耳机频响归为耳机目标曲线，其余归为音频常用目标曲线。"""
    if obj.get('category'):
        return obj['category']
    source = str(obj.get('source') or '').lower()
    name = str(obj.get('name') or '')
    if source == 'imported':
        return 'headphone'
    # AutoEq 导入的目标曲线会带测量者/rig 元数据；source 已保留测量者名，
    # 不能再按 source != 'imported' 误判成 common。
    if obj.get('measured_device') or obj.get('measurement_source') or obj.get('rig'):
        return 'headphone'
    if '原始频响' in name or '原始频响' in str(obj.get('id') or ''):
        return 'headphone'
    return 'common'


class CurveStore:
    def __init__(self, curves_dir=None):
        self.curves_dir = curves_dir or CURVES_DIR
        self.devices_dir = os.path.join(self.curves_dir, 'devices')
        self.targets_dir = os.path.join(self.curves_dir, 'targets')
        self._cache = {}  # path -> (mtime, obj)
        _ensure_dirs()

    def _load_file(self, path):
        if not os.path.exists(path):
            return None
        mtime = os.path.getmtime(path)
        cached = self._cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        obj = _read_json(path)
        obj['points'] = _normalize_points(obj.get('points'))
        self._cache[path] = (mtime, obj)
        return obj

    def _scan_dir(self, dirpath, builtins, kind_field):
        items = {}
        for d in builtins:
            key = d['id']
            items[key] = dict(d)
        if os.path.isdir(dirpath):
            for fname in os.listdir(dirpath):
                if not fname.lower().endswith('.json'):
                    continue
                path = os.path.join(dirpath, fname)
                try:
                    obj = self._load_file(path)
                    if not obj:
                        continue
                except Exception:
                    continue
                cid = obj.get('id') or os.path.splitext(fname)[0]
                if not obj.get('points'):
                    # 保留手写元数据，但曲线为空时列表仍可显示
                    pass
                items[cid] = obj
        # 稳定顺序：先内置顺序，再按 id
        ordered = []
        seen = set()
        for key in [d['id'] for d in builtins]:
            if key in items:
                ordered.append(items[key])
                seen.add(key)
        for key in sorted(items):
            if key not in seen:
                ordered.append(items[key])
        return ordered

    def list_devices(self):
        return self._scan_dir(self.devices_dir, BUILTIN_DEVICES, 'device')

    def list_targets(self):
        items = self._scan_dir(self.targets_dir, BUILTIN_TARGETS, 'target')
        for item in items:
            item['category'] = _default_target_category(item)
        return items

    def get_device(self, did):
        for item in self.list_devices():
            if item['id'] == did:
                return item
        return None

    def get_target(self, tid):
        for item in self.list_targets():
            if item['id'] == tid:
                return item
        return None

    def rig_diff(self, device_id, rig_from=None, rig_to=None):
        """计算同型号耳机在两个 rig 下的实测差 tilt(f) = raw(rig_to) - raw(rig_from)。

        用于“去 rig 修正”：把目标曲线换算到设备 rig 的口径后再拟合。
        找不到同型号双 rig 数据时返回 None。
        """
        devices = self.list_devices()
        base = next((d for d in devices if d.get('id') == device_id), None)
        if not base:
            return None
        name = str(base.get('name') or '').strip()
        if not name:
            return None
        siblings = [
            d for d in devices
            if str(d.get('name') or '').strip() == name
            and (d.get('rig') or d.get('measurement_rig'))
            and len(d.get('points') or []) >= 2
        ]
        if len(siblings) < 2:
            return None

        def matches(d, selector):
            if not selector:
                return False
            low = str(selector).strip().lower()
            blob = ' '.join(str(d.get(k) or '') for k in (
                'id', 'rig', 'measurement_rig', 'rig_family', 'rig_standard',
                'variant', 'source', 'measurement_source',
            )).lower()
            tokens = [t for t in re.split(r'[\s/|+]+', low) if t]
            if not tokens:
                return False
            return all(tok in blob for tok in tokens)

        to = next((d for d in siblings if matches(d, rig_to)), None) if rig_to else None
        if to is None:
            to = base if (base.get('rig') or base.get('measurement_rig')) else siblings[0]
        from_ = next((d for d in siblings if matches(d, rig_from)), None) if rig_from else None
        if from_ is None or from_.get('id') == to.get('id'):
            to_fam = rig_family_key(to.get('rig_family'), to.get('rig'))
            from_ = next(
                (d for d in siblings
                 if d.get('id') != to.get('id')
                 and rig_family_key(d.get('rig_family'), d.get('rig')) != to_fam),
                None,
            )
        if from_ is None or from_.get('id') == to.get('id'):
            return None

        grid = [20.0 * (20000.0 / 20.0) ** (i / 199.0) for i in range(200)]
        points = []
        for freq in grid:
            a = _interp_log(from_.get('points'), freq)
            b = _interp_log(to.get('points'), freq)
            if a is None or b is None:
                continue
            points.append([round(freq, 4), round(b - a, 4)])
        if len(points) < 2:
            return None
        rms = math.sqrt(sum(p[1] * p[1] for p in points) / len(points))
        return {
            'device_id': device_id,
            'name': name,
            'from_id': from_.get('id'),
            'to_id': to.get('id'),
            'rig_from': str(from_.get('rig') or from_.get('measurement_rig') or ''),
            'rig_to': str(to.get('rig') or to.get('measurement_rig') or ''),
            'family_from': rig_family_key(from_.get('rig_family'), from_.get('rig')),
            'family_to': rig_family_key(to.get('rig_family'), to.get('rig')),
            'points': points,
            'rms_db': round(rms, 4),
        }

    def import_curve(self, curve_type, name, text, kind=None, category=None, extra=None,
                     align=True, align_ref_low=500.0, align_ref_high=2000.0, align_method='mean'):
        if curve_type not in ('device', 'target'):
            raise ValueError('curve_type 必须是 device 或 target')
        points = parse_points_text(text)
        align_offset_db = 0.0
        if align:
            points, align_offset_db = align_points_to_reference(
                points, ref_low=align_ref_low, ref_high=align_ref_high, method=align_method)
        if len(points) < 2:
            raise ValueError('曲线至少需要 2 个数据点')
        cid = _slug(name)
        dirpath = self.devices_dir if curve_type == 'device' else self.targets_dir
        extra = extra if isinstance(extra, dict) else {}
        # AutoEq 导入时保留真实测量者（source），不要一律写成无信息的 'imported'；
        # 这关系到前端 rig 提示与 /api/curves/target 的元数据可读性。
        source = str(
            extra.get('source')
            or extra.get('measurement_source')
            or 'imported'
        ).strip() or 'imported'
        # 同名曲线直接覆盖：后导入的替代先导入的
        obj = {
            'id': cid,
            'name': name,
            'kind': 'target' if curve_type == 'target' else (kind or 'headphone'),
            'source': source,
            'points': points,
            'alignment': {
                'enabled': bool(align),
                'method': align_method,
                'ref_low': float(align_ref_low),
                'ref_high': float(align_ref_high),
                'offset_db': round(float(align_offset_db), 4),
            },
        }
        if curve_type == 'target':
            obj['category'] = category or 'common'
        # 附加元数据（如 AutoEq 导入的测量设备 / rig 信息，见 autoeq_store.measurement_meta）
        for k, v in extra.items():
            if v not in (None, ''):
                obj[k] = v
        # 统一 rig 字段别名，兼容旧脚本/前端的不同命名
        if obj.get('rig'):
            obj.setdefault('measurement_rig', obj['rig'])
        if obj.get('url'):
            obj.setdefault('measurement_url', obj['url'])
        path = os.path.join(dirpath, cid + '.json')
        os.makedirs(dirpath, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(json.dumps(obj, ensure_ascii=False, indent=2).encode('utf-8'))
        self._cache.pop(path, None)
        return obj


def parse_points_text(text):
    """解析 'freq,db' / 'freq\\tdb' 行 / EqualizerAPO GraphicEQ，兼容带表头 CSV。返回 [[freq, db], ...]"""
    text = (text or '').strip()
    # EqualizerAPO GraphicEQ: 20 -8.6; 21 -8.5; ...
    if 'GraphicEQ:' in text:
        points = []
        body = text.split('GraphicEQ:', 1)[1]
        for token in body.replace(';', ' ').split():
            token = token.strip()
            if not token:
                continue
        # 重新按空白分割 pair
        parts = body.replace(';', ' ').split()
        for i in range(0, len(parts) - 1, 2):
            try:
                freq = float(parts[i])
                db = float(parts[i + 1])
            except (TypeError, ValueError):
                continue
            if freq > 0 and -60 <= db <= 60:
                points.append([freq, db])
        points.sort(key=lambda x: x[0])
        return points

    points = []
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        parts = re.split(r'[,\t;]+', line)
        if parts[0].lower().startswith('freq') or parts[0].lower() in ('frequency', 'hz'):
            continue
        if len(parts) < 2:
            continue
        try:
            freq = float(parts[0])
            db = float(parts[1])
            if freq <= 0 or not (-60 <= db <= 60):
                continue
            points.append([freq, db])
        except ValueError:
            continue
    points.sort(key=lambda x: x[0])
    return points


if __name__ == '__main__':
    store = CurveStore()
    print('devices:', [d['id'] for d in store.list_devices()])
    print('targets:', [t['id'] for t in store.list_targets()])
