# -*- coding: utf-8 -*-
"""
eq_parser.py - EQ 文本 / CSV / JSON 解析器

只解析不写入。支持:
- EqualizerAPO / AutoEq:
  Filter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 2.0
  Preamp: -4.0 dB
- CSV/行式: 105,-3.5,2.0
- JSON: [{"type":"PK","freq":105,"gain":-3.5,"q":2.0}, ...]
返回 {bands, preamp_db, warnings}
"""
import json
import re

# WebUI 编辑/拟合上限（app.js 中同样限制为 20 段）。
# 读取预设时必须显式传 max_bands=None，避免 20 段预设被静默截断。
MAX_BANDS = 20
TYPE_ALIASES = {
    'PK': 'PK', 'PEAKING': 'PK', 'PEAK': 'PK', 'P': 'PK',
    'LS': 'LS', 'LSC': 'LS', 'LOW_SHELF': 'LS', 'LOWSHELF': 'LS', 'LOW SHELF': 'LS',
    'HS': 'HS', 'HSC': 'HS', 'HIGH_SHELF': 'HS', 'HIGHSHELF': 'HS', 'HIGH SHELF': 'HS',
    'LP': 'LP', 'LOW_PASS': 'LP', 'LOWPASS': 'LP', 'LOW PASS': 'LP',
    'HP': 'HP', 'HIGH_PASS': 'HP', 'HIGHPASS': 'HP', 'HIGH PASS': 'HP',
}


def _clamp(v, lo, hi):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return lo


def _norm_band(raw):
    if not isinstance(raw, dict):
        return None
    t = str(raw.get('type') or raw.get('kind') or 'PK').strip().upper()
    t = TYPE_ALIASES.get(t, t if t in ('PK', 'LS', 'HS', 'LP', 'HP') else 'PK')
    freq = _clamp(raw.get('freq', raw.get('frequency', raw.get('fc', 1000))), 20, 20000)
    gain = _clamp(raw.get('gain', raw.get('gain_db', raw.get('db', 0))), -15, 15)
    q = _clamp(raw.get('q', raw.get('Q', 1)), 0.1, 10)
    return {
        'type': t,
        'freq': round(freq, 4),
        'gain_db': round(gain, 4),
        'q': round(q, 4),
        'enabled': raw.get('enabled', True) is not False,
    }


def parse_eq(text, max_bands=MAX_BANDS):
    """解析 EQ 文本。

    max_bands: 最多保留的频段数；None 表示不截断（预设读取路径必须用 None，
    否则 20 段预设会在“读回再重写”时静默丢失第 11 段以后）。
    """
    if text is None:
        return {'bands': [], 'preamp_db': 0, 'warnings': ['文本为空']}
    text = text.strip()
    if not text:
        return {'bands': [], 'preamp_db': 0, 'warnings': ['文本为空']}

    warnings = []

    # JSON 数组 / 对象
    if text.startswith('[') or text.startswith('{'):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                bands = data.get('bands') or data.get('filters') or []
                preamp = data.get('preamp_db', data.get('preamp', 0))
            else:
                bands = data
                preamp = 0
            if not isinstance(bands, list):
                raise ValueError('bands 必须是数组')
            out = [_norm_band(b) for b in bands]
            out = [b for b in out if b]
            preamp = _clamp(preamp, -30, 30)
            return _finish(out, preamp, warnings, max_bands)
        except Exception as e:
            return {'bands': [], 'preamp_db': 0, 'warnings': [f'JSON 解析失败: {e}']}

    # EqualizerAPO / AutoEq 文本
    is_apo = False
    for line in text.splitlines():
        if re.match(r'\s*(Filter\s+\d+:|Preamp:)', line, re.I):
            is_apo = True
            break

    if is_apo:
        out = []
        preamp = 0
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            m_pre = re.match(r'Preamp:\s*([-\d.]+)\s*dB', line, re.I)
            if m_pre:
                preamp = _clamp(m_pre.group(1), -30, 30)
                continue
            m = re.match(
                r'Filter\s+\d+:\s*(ON|OFF)?\s*'
                r'(PK|LS|LSC|HS|HSC|LP|HP|Peaking|Low Shelf|High Shelf|Low Pass|High Pass)\s+'
                r'Fc\s+([\d.]+)\s*Hz\s+Gain\s+([+-]?[\d.]+)\s*dB\s+Q\s+([\d.]+)',
                line, re.I
            )
            if not m:
                # 兼容无 Gain/Q 的行
                m = re.match(
                    r'Filter\s+\d+:\s*(ON|OFF)?\s*'
                    r'(PK|LS|LSC|HS|HSC|LP|HP|Peaking|Low Shelf|High Shelf|Low Pass|High Pass)\s+'
                    r'Fc\s+([\d.]+)\s*Hz(?:\s+Gain\s+([+-]?[\d.]+)\s*dB)?(?:\s+Q\s+([\d.]+))?',
                    line, re.I
                )
            if not m:
                # 兼容 Preamp 与 CSV 混写的粘贴文本
                parts = re.split(r'[,\t;]+', line)
                try:
                    freq = float(parts[0])
                    gain = float(parts[1])
                    q = float(parts[2]) if len(parts) >= 3 and parts[2] not in ('', '-') else 1.0
                    raw = {'type': 'PK', 'freq': freq, 'gain_db': gain, 'q': q, 'enabled': True}
                except (ValueError, IndexError):
                    continue
            else:
                enabled = m.group(1).upper() != 'OFF' if m.group(1) else True
                raw = {
                'type': TYPE_ALIASES.get(m.group(2).upper(), 'PK'),
                'freq': float(m.group(3)),
                'gain_db': float(m.group(4)) if m.group(4) else 0,
                'q': float(m.group(5)) if m.group(5) else 1,
                'enabled': enabled,
            }
            band = _norm_band(raw)
            if band:
                out.append(band)
        return _finish(out, preamp, warnings, max_bands)

    # CSV / 行式 freq,gain[,q]
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        parts = re.split(r'[,\t;]+', line)
        if parts[0].lower().startswith('freq') or parts[0].lower() in ('hz', 'frequency'):
            continue
        try:
            freq = float(parts[0])
            gain = float(parts[1])
            q = float(parts[2]) if len(parts) >= 3 and parts[2] not in ('', '-') else 1.0
        except ValueError:
            continue
        raw = {'type': 'PK', 'freq': freq, 'gain_db': gain, 'q': q, 'enabled': True}
        band = _norm_band(raw)
        if band:
            out.append(band)
    return _finish(out, 0, warnings)


def _finish(bands, preamp_db, warnings, max_bands=MAX_BANDS):
    if max_bands is not None and max_bands > 0 and len(bands) > max_bands:
        warnings.append(f'解析结果超过 {max_bands} 个频段，已截断为前 {max_bands} 个')
        bands = bands[:max_bands]
    return {'bands': bands, 'preamp_db': round(preamp_db, 4), 'warnings': warnings}


def read_text_file(path):
    """读取 PEQ 文件，优先 UTF-8，兼容 GBK/ANSI。"""
    with open(path, 'rb') as f:
        data = f.read()
    for enc in ('utf-8-sig', 'utf-8', 'gbk'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def parse_eq_file(path, max_bands=MAX_BANDS):
    """直接读取本地 PEQ 配置文件并解析。"""
    try:
        text = read_text_file(path)
    except OSError as e:
        return {'bands': [], 'preamp_db': 0, 'warnings': [f'读取文件失败: {e}']}
    result = parse_eq(text, max_bands=max_bands)
    result['source_path'] = path
    return result


# ReaEQ 固定段（P0 #10 实测）：
# LS -> 1, PK -> 2/3, HS -> 4, HP -> 5；LP 不支持。
REAEQ_SECTIONS = [
    {'slot': 1, 'type': 'LS'},
    {'slot': 2, 'type': 'PK'},
    {'slot': 3, 'type': 'PK'},
    {'slot': 4, 'type': 'HS'},
    {'slot': 5, 'type': 'HP'},
]


def adapt_to_reaeq(bands):
    """把解析出的通用 PEQ bands 适配到 ReaEQ 固定 5 段。

    返回:
      bands    : 实际可写入 ReaEQ 的 bands
      warnings : 丢弃/无法表示的原因
      dropped  : 被丢弃的 bands
    """
    warnings = []
    dropped = []
    assigned = []
    used = set()
    category_group = {'LS': [1], 'PK': [2, 3], 'HS': [4], 'HP': [5], 'LP': []}

    for b in bands or []:
        if not b or not b.get('enabled', True):
            continue
        t = str(b.get('type') or 'PK').upper()
        if t == 'LP':
            warnings.append('ReaEQ 不支持 LP(Low Pass)，已忽略')
            dropped.append(b)
            continue
        if t not in category_group:
            t = 'PK'
        slots = category_group[t]
        chosen = next((s for s in slots if s not in used), None)
        if chosen is None:
            warnings.append(f'ReaEQ 可用槽位不足，已忽略: {t}')
            dropped.append(b)
            continue
        used.add(chosen)
        assigned.append({
            'type': t,
            'freq': float(b['freq']),
            'gain_db': float(b['gain_db']),
            'q': float(b['q']),
            'enabled': True,
        })

    # 按 ReaEQ 物理槽位顺序输出，便于前端预览
    slot_order = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4}
    assigned.sort(key=lambda x: slot_order[{'LS': 1, 'PK': 2, 'HS': 4, 'HP': 5}[x['type']]])
    return {'bands': assigned, 'warnings': warnings, 'dropped': dropped}


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        result = parse_eq_file(sys.argv[1])
        adapted = adapt_to_reaeq(result['bands'])
        result['adapted'] = adapted
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        sample = """Filter 1: ON PK Fc 105 Hz Gain -3.5 dB Q 2.0
Filter 2: OFF LS Fc 250 Hz Gain -1.5 dB Q 0.7
Preamp: -4.0 dB
"""
        print(parse_eq(sample))