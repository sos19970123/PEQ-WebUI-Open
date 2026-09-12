# -*- coding: utf-8 -*-
"""
autoeq_store.py - 本地 AutoEq 源码数据访问层

从 AutoEq 源码目录读取：
- results/**/ParametricEQ.txt  -> 预计算 PEQ 配置
- results/**/*.csv             -> 频响测量数据
- webapp/data/targets.json     -> 目标曲线

默认 AutoEq 根目录：
<项目根>/../AutoEq-4.1.2/AutoEq-4.1.2（与本项目同级的 AutoEq 数据库）
可用环境变量 AUTOEQ_ROOT 覆盖。
"""
import csv
import io
import json
import os
import re

from eq_parser import parse_eq

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AUTOEQ_ROOT = os.path.normpath(
    os.path.join(_PROJECT_ROOT, '..', 'AutoEq-4.1.2', 'AutoEq-4.1.2')
)

# 各测量源的显示名 / 来源链接 / rig 回退信息（有 name_index.tsv 时以 rig 列为准）
SOURCE_URLS = {
    'oratory1990': 'https://www.reddit.com/r/oratory1990/wiki/index/list_of_presets/',
    'Rtings': 'https://www.rtings.com/headphones/tests/sound-quality',
    'Innerfidelity': 'https://www.stereophile.com/content/innerfidelity-headphone-measurements',
    'crinacle': 'https://crinacle.com/graphs/headphones/',
    'Super Review': 'https://squig.link/',
    'Kuulokenurkka': 'https://kuulokenurkka.com/',
    'Auriculares Argentina': 'https://auricularesargentina.squig.link/',
    'Headphone.com Legacy': 'https://www.headphone.com/',
}

RIG_FALLBACK = {
    # source -> (rig, rig_family, rig_standard, rig_note)
    'oratory1990': (
        'GRAS 45BC-10', 'KEMAR HATS',
        'GRAS 45BC-10 KEMAR 型头身模拟器（HATS）',
        'oratory1990/AutoEq 校准基准，与 Harman 目标同源；早期测量使用 GRAS 43AG-7 / 43AC（711 类）。',
    ),
    'Rtings': (
        'HMS II.3', 'HATS',
        'HEAD acoustics HMS II.3 头身模拟器（RTINGS 旧版原始图）',
        'AutoEq 收录 RTINGS 原始频响图时其 rig 记录为 HMS II.3；RTINGS 官方现行测试台已改用 B&K 5128-B HATS。',
    ),
    'Innerfidelity': (
        'HMS II.3', 'HATS',
        'HEAD acoustics HMS II.3 头身模拟器（IEC 60268-7 耳廓 + HRTF 补偿）',
        'Tyll Hertsens 的 InnerFidelity 测量程序说明使用 HMS II.3，5 次佩戴平均。',
    ),
    'crinacle': (
        'IEC 60318-4 (711)', '711 coupler',
        'IEC 60318-4（“711”）耦合器（crinacle 系统）',
        'crinacle 的耳机测量基于 711 类系统；其新测量使用 GRAS 43AG-7。',
    ),
    'Super Review': (
        'KB006x + 711', '711 coupler',
        'GRAS KB006x 人工耳廓 + IEC 60318-4（“711”）',
        'Super* Review（squig.link 主站），其 IEM 测量 rig 标注为 clone IEC 711。',
    ),
    'Kuulokenurkka': (
        'KB501x + 711', '711 coupler',
        'GRAS KB501x 人工耳廓 + IEC 60318-4（“711”）',
        'Kuulokenurkka（芬兰）；曾使用 MiniDSP EARS（HEQ 补偿）。',
    ),
    'Auriculares Argentina': (
        'KB501x + 711', '711 coupler',
        'GRAS KB501x 人工耳廓 + IEC 60318-4（“711”）',
        'Auriculares Argentina（阿根廷）。',
    ),
    'Headphone.com Legacy': (
        'Legacy 夹具', 'legacy',
        'HeadRoom/Headphone.com 时代老式测量夹具',
        '旧 Headphone.com Legacy 数据（AutoEq README 注明其与公司现行测量不同）。',
    ),
}


def _slug(name):
    s = re.sub(r'[^\w\u4e00-\u9fff]+', '-', name.strip().lower()).strip('-')
    return s or 'autoeq-device'


def _rig_family_standard(rig):
    """根据 rig 字符串推导 rig 族与标准说明（name_index 有 rig 但无 family 时使用）。"""
    r = (rig or '').lower()
    if '45bc' in r or '43ag' in r or '43ac' in r:
        return ('KEMAR HATS', f'{rig}（KEMAR 型 HATS，oratory/GRAS 系）')
    if '5128' in r:
        return ('5128', f'{rig}（B&K 5128 类 HATS）')
    if 'hms' in r or 'ii.3' in r:
        return ('HATS', f'{rig}（HEAD acoustics 头身模拟器）')
    if '711' in r or '60318' in r:
        return ('711 coupler', f'{rig}（人工耳廓 + IEC 60318-4 “711”）')
    if 'ears' in r:
        return ('EARS', f'{rig}（MiniDSP EARS 类）')
    return ('', '')


class AutoEqStore:
    def __init__(self, root=None):
        self.root = root or os.environ.get('AUTOEQ_ROOT') or DEFAULT_AUTOEQ_ROOT
        self.results_dir = os.path.join(self.root, 'results')
        self.targets_path = os.path.join(self.root, 'webapp', 'data', 'targets.json')
        self._index_cache = None

    # ---------- 设备索引 ----------
    def build_index(self, refresh=False):
        if self._index_cache is not None and not refresh:
            return self._index_cache
        index = []
        if not os.path.isdir(self.results_dir):
            self._index_cache = index
            return index
        for source_name in sorted(os.listdir(self.results_dir)):
            source_dir = os.path.join(self.results_dir, source_name)
            if not os.path.isdir(source_dir):
                continue
            for form in ('in-ear', 'earbud', 'over-ear', 'on-ear'):
                form_dir = os.path.join(source_dir, form)
                if not os.path.isdir(form_dir):
                    continue
                for device_name in sorted(os.listdir(form_dir)):
                    device_dir = os.path.join(form_dir, device_name)
                    if not os.path.isdir(device_dir):
                        continue
                    eq_path = self._find_eq(device_dir, device_name)
                    csv_path = os.path.join(device_dir, device_name + '.csv')
                    if not eq_path or not os.path.isfile(csv_path):
                        continue
                    index.append({
                        'id': _slug(f'{source_name}-{form}-{device_name}'),
                        'name': device_name,
                        'source': source_name,
                        'form': form,
                        'eq_path': eq_path,
                        'csv_path': csv_path,
                    })
        self._index_cache = index
        return index

    @staticmethod
    def _find_eq(device_dir, device_name):
        candidates = [
            os.path.join(device_dir, device_name + ' ParametricEQ.txt'),
            os.path.join(device_dir, device_name + '.txt'),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        for fname in os.listdir(device_dir):
            if 'ParametricEQ' in fname and fname.lower().endswith('.txt'):
                return os.path.join(device_dir, fname)
        return None

    def search(self, query):
        q = query.strip().lower()
        index = self.build_index()
        if not q:
            return index[:50]
        return [d for d in index if q in d['name'].lower() or q in d['source'].lower()][:100]

    def get(self, device_id):
        for d in self.build_index():
            if d['id'] == device_id:
                return d
        return None

    # ---------- 测量装置（rig）元数据 ----------
    def measurement_meta(self, entry):
        """为 AutoEq 结果条目解析测量装置信息。

        优先读取 measurements/<source>/name_index.tsv 的 rig 列（精确匹配设备名），
        找不到时回退到内置 RIG_FALLBACK 表。返回可直接写入曲线 JSON 的元数据字典。
        """
        source = str(entry.get('source') or '')
        name = str(entry.get('name') or '')
        source_url = SOURCE_URLS.get(source, '')
        fallback = RIG_FALLBACK.get(source)

        rig, family, standard, note = (fallback or ('', '', '', ''))
        rig = self._lookup_rig(source, name) or rig
        if rig and family == '' and standard == '':
            family, standard = _rig_family_standard(rig)

        return {
            'source': source,
            'measured_device': name,
            'measurement_source': source,
            'variant': source,
            'rig': rig,
            'rig_family': family,
            'rig_standard': standard,
            'rig_note': note,
            'measurement_rig': rig,
            'measurement_url': source_url,
            'url': source_url,
        }

    def _lookup_rig(self, source, device_name):
        """在 measurements/<source>/name_index.tsv 中按设备名精确匹配 rig 列。"""
        if not source or not device_name:
            return ''
        idx_path = os.path.join(self.root, 'measurements', source, 'name_index.tsv')
        if not os.path.isfile(idx_path):
            return ''
        try:
            with open(idx_path, 'rb') as f:
                lines = f.read().decode('utf-8-sig', errors='replace').splitlines()
        except OSError:
            return ''
        header = lines[0].split('\t') if lines else []
        try:
            name_col = header.index('name')
            rig_col = header.index('rig')
        except ValueError:
            name_col, rig_col = 3, 4
        target = device_name.strip().lower()
        for line in lines[1:]:
            cols = line.split('\t')
            if len(cols) <= max(name_col, rig_col):
                continue
            cell = cols[name_col].strip().lower()
            if cell == target:
                rig = cols[rig_col].strip()
                if rig:
                    return rig
        return ''

    # ---------- 导入到 WebUI ----------
    def read_device_csv_points(self, csv_path, column='raw'):
        """读取 AutoEq CSV 的 frequency + 指定列（默认 raw 原始频响）作为频响曲线。"""
        points = []
        with open(csv_path, 'rb') as f:
            text = f.read().decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                freq = float(row.get('frequency', ''))
                value = row.get(column)
                if value is None or value == '':
                    value = row.get('smoothed' if column == 'raw' else 'raw')
                if value is None or value == '':
                    continue
                db = float(value)
            except (TypeError, ValueError):
                continue
            if freq > 0:
                points.append([freq, db])
        return points

    def read_device_raw_points(self, csv_path):
        """读取 AutoEq CSV 的 raw 原始频响；若没有 raw 列则返回空列表。"""
        points = []
        with open(csv_path, 'rb') as f:
            text = f.read().decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        if 'raw' not in (reader.fieldnames or []):
            return []
        for row in reader:
            try:
                freq = float(row.get('frequency', ''))
                val = row.get('raw')
                if val is None or val == '':
                    continue
                db = float(val)
            except (TypeError, ValueError):
                continue
            if freq > 0:
                points.append([freq, db])
        return points

    def read_device_target_points(self, csv_path):
        points = []
        with open(csv_path, 'rb') as f:
            text = f.read().decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            try:
                freq = float(row.get('frequency', ''))
                db = float(row.get('target', ''))
            except (TypeError, ValueError):
                continue
            if freq > 0:
                points.append([freq, db])
        return points

    def read_eq(self, entry):
        try:
            with open(entry['eq_path'], 'rb') as f:
                text = f.read().decode('utf-8-sig', errors='replace')
        except OSError:
            return {'bands': [], 'preamp_db': 0, 'warnings': ['读取 EQ 文件失败']}
        return parse_eq(text)

    def read_targets(self):
        """读取 AutoEq targets.json，转换为 curve_store 可用的目标曲线结构。"""
        if not os.path.isfile(self.targets_path):
            return []
        with open(self.targets_path, 'rb') as f:
            data = json.loads(f.read().decode('utf-8-sig'))
        out = []
        for t in data or []:
            label = t.get('label') or 'AutoEq Target'
            fr = t.get('fr') or {}
            freqs = fr.get('frequency') or []
            dbs = fr.get('raw') or []
            points = [[float(f), float(d)] for f, d in zip(freqs, dbs) if f and d is not None]
            out.append({
                'id': _slug(label),
                'name': label,
                'kind': 'target',
                'points': points,
                'bass_boost': t.get('bassBoost'),
            })
        return out


if __name__ == '__main__':
    store = AutoEqStore()
    print('devices', len(store.build_index()))
    for d in store.search('AKG K371')[:3]:
        print(d)
    print('targets', len(store.read_targets()))