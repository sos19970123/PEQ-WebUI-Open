# -*- coding: utf-8 -*-
"""
apo_backend.py - EqualizerAPO 控制底座（方案 A）

职责:
- 渲染 bands -> EqualizerAPO 原生文本
- 原子写预设文件 / hl-active.txt / apo-state.json
- install/uninstall（接管 config.txt）
- 状态探测（installed/managed/mounted_fiio/active_preset_id）
- 归一化哈希对账：激活态以 hl-active.txt 内容为准
- 预设 UI 状态保存（设备选择、目标曲线、开关状态）

路径约定:
- APO_PRESET_DIR 环境变量可覆盖预设仓库（测试用临时目录）
- APO_CONFIG_DIR 环境变量可覆盖 APO 配置目录（测试用临时目录）
- 默认预设仓库: <项目根>/apo-presets
- 默认 APO 配置目录: <项目根>/apo-config（迁移后项目内可写目录）
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

from eq_parser import parse_eq

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PRESET_DIR = os.path.join(BASE_DIR, 'apo-presets')
DEFAULT_APO_SCOPE = 'Fiio'
MANAGED_MARKER = '# Managed by peq-webui mixer_web.'
# Legacy Managed marker kept only for recognition of older configs; not written anymore
LEGACY_MANAGED_MARKER = '# Managed by headphone-lab mixer_web.'
MANAGED_INCLUDE = 'Include: hl-active.txt'
REGISTRY_KEY_PATH = r'SOFTWARE\EqualizerAPO'


def _default_user_config_dir():
    return os.path.join(BASE_DIR, 'apo-config')


def _is_protected_program_files(path):
    return 'program files' in str(path).lower()


def _get_apo_config_dir():
    env = os.environ.get('APO_CONFIG_DIR')
    if env:
        return env
    local_dir = os.path.join(BASE_DIR, 'apo-config')
    migration_file = os.path.join(DEFAULT_PRESET_DIR, 'migration.json')
    if os.path.isfile(migration_file):
        try:
            with open(migration_file, 'rb') as f:
                info = json.loads(f.read().decode('utf-8-sig'))
            if info.get('migrated') and os.path.isdir(local_dir):
                return local_dir
        except Exception:
            pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY_PATH) as key:
            value, _ = winreg.QueryValueEx(key, 'ConfigPath')
            if value:
                return str(value)
    except Exception:
        pass
    return r'C:\Program Files\EqualizerAPO\config'


def _slug(name):
    s = re.sub(r'[^\w\u4e00-\u9fff]+', '-', str(name).strip().lower()).strip('-')
    if not s:
        s = 'preset'
    return s


def normalize_text(text):
    if text is None:
        return ''
    s = str(text).lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n')
    lines = [ln.rstrip() for ln in s.split('\n')]
    while lines and lines[0].strip() == '':
        lines.pop(0)
    while lines and lines[-1].strip() == '':
        lines.pop()
    return '\n'.join(lines) + '\n'


def _hash_text(text):
    return hashlib.sha256(normalize_text(text).encode('utf-8')).hexdigest()


def _atomic_write(path, text):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(str(text).encode('utf-8'))
    os.replace(tmp, path)


def _read_text(path):
    if not os.path.isfile(path):
        return None
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8-sig', 'utf-8'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def _parse_meta(lines):
    name = ''
    device_id = ''
    target_id = ''
    device_scope = ''
    for line in lines:
        if line.startswith('# name:'):
            name = line[len('# name:'):].strip()
        elif line.startswith('# device:'):
            device_id = line[len('# device:'):].strip()
        elif line.startswith('# target:'):
            target_id = line[len('# target:'):].strip()
        elif line.lower().startswith('device:'):
            device_scope = line[len('Device:'):].strip()
    return name, device_id, target_id, device_scope


def _parse_notes(lines):
    notes = []
    for line in lines:
        if line.startswith('# note:'):
            notes.append(line[len('# note:'):].strip())
    return '\n'.join(notes)


def _parse_fit(lines):
    for line in lines:
        if line.startswith('# fit:'):
            raw = line[len('# fit:'):].strip()
            try:
                data = json.loads(raw)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


def _parse_ui_state(lines):
    for line in lines:
        if line.startswith('# ui_state:'):
            raw = line[len('# ui_state:'):].strip()
            try:
                data = json.loads(raw)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
    return {}


# 元数据行优先级：仅用于在缺失字段时决定插入位置，不改变原有行序。
_META_PREFIX_ORDER = ('# name:', '# device:', '# target:', '# fit:', '# ui_state:', '# note:', '# generated:')


def _meta_prefix_rank(line):
    s = str(line or '').strip().lower()
    for i, prefix in enumerate(_META_PREFIX_ORDER):
        if s.startswith(prefix):
            return i
    return -1


def _split_preset_header(text):
    """把预设文本拆成“头部注释”和“正文（Device/Preamp/Filter）”。

    正文从第一行非空且不是注释的行开始，保证 Device/Preamp/Filter 一字不动。
    """
    lines = str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    split = len(lines)
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not (s.startswith('#') or s.startswith('//') or s.startswith(';')):
            split = i
            break
    return lines[:split], lines[split:]


def _insert_meta_line(header_lines, new_line, rank):
    """按元数据优先级插入缺失行；优先插在比它优先级更低的行之前。"""
    out = list(header_lines)
    idx = None
    for i, line in enumerate(out):
        if _meta_prefix_rank(line) > rank:
            idx = i
            break
    if idx is None:
        idx = len(out)
        while idx > 0 and out[idx - 1].strip() == '':
            idx -= 1
    out.insert(idx, new_line)
    return out


def rewrite_preset_meta(text, name=None, device_id=None, target_id=None,
                        notes=None, fit=None, ui_state=None, generated_by='mixer_web'):
    """只改元数据行，保留 Device / Preamp / Filter 与未知注释行。

    约定（与需求文档 §1.6 一致）:
    - 传 None 的字段保持原行不变；
    - name/device_id/target_id 传空字符串表示删除该元数据行；
    - notes 传字符串时删除全部旧的 # note: 行，在原位置按新内容逐行写入；
      notes=None 时保持原样；
    - fit/ui_state 传 None 时原样保留（元数据接口路径不会重渲染 bands）；
    - 只会更新 # generated: 时间戳。
    """
    header, body = _split_preset_header(text)
    new_header = []
    seen = {'name': False, 'device': False, 'target': False, 'fit': False,
            'ui_state': False, 'note': False, 'generated': False}

    for line in header:
        low = line.strip().lower()
        if low.startswith('# name:'):
            if seen['name']:
                continue
            seen['name'] = True
            if name is None:
                new_header.append(line)
            elif str(name).strip():
                new_header.append(f'# name: {str(name).strip()}')
            continue
        if low.startswith('# device:'):
            if seen['device']:
                continue
            seen['device'] = True
            if device_id is None:
                new_header.append(line)
            elif str(device_id).strip():
                new_header.append(f'# device: {str(device_id).strip()}')
            continue
        if low.startswith('# target:'):
            if seen['target']:
                continue
            seen['target'] = True
            if target_id is None:
                new_header.append(line)
            elif str(target_id).strip():
                new_header.append(f'# target: {str(target_id).strip()}')
            continue
        if low.startswith('# fit:'):
            if seen['fit']:
                continue
            seen['fit'] = True
            if fit is None:
                new_header.append(line)
            else:
                new_header.append('# fit: ' + json.dumps(fit, ensure_ascii=False, separators=(',', ':')))
            continue
        if low.startswith('# ui_state:'):
            if seen['ui_state']:
                continue
            seen['ui_state'] = True
            if ui_state is None:
                new_header.append(line)
            else:
                new_header.append('# ui_state: ' + json.dumps(ui_state, ensure_ascii=False, separators=(',', ':')))
            continue
        if low.startswith('# note:'):
            if seen['note']:
                continue
            seen['note'] = True
            if notes is None:
                for other in header:
                    if other.strip().lower().startswith('# note:'):
                        new_header.append(other)
            else:
                for note_line in str(notes).splitlines():
                    new_header.append(f'# note: {note_line}')
            continue
        if low.startswith('# generated:'):
            if seen['generated']:
                continue
            seen['generated'] = True
            stamp = datetime.datetime.now().isoformat(timespec='seconds')
            new_header.append(f'# generated: {stamp} by {generated_by}')
            continue
        new_header.append(line)

    # 补充原文件中缺失的字段（保持标准顺序）
    if name is not None and not seen['name'] and str(name).strip():
        new_header = _insert_meta_line(new_header, f'# name: {str(name).strip()}', 0)
    if device_id is not None and not seen['device'] and str(device_id).strip():
        new_header = _insert_meta_line(new_header, f'# device: {str(device_id).strip()}', 1)
    if target_id is not None and not seen['target'] and str(target_id).strip():
        new_header = _insert_meta_line(new_header, f'# target: {str(target_id).strip()}', 2)
    if fit is not None and not seen['fit']:
        new_header = _insert_meta_line(
            new_header,
            '# fit: ' + json.dumps(fit, ensure_ascii=False, separators=(',', ':')),
            3,
        )
    if ui_state is not None and not seen['ui_state']:
        new_header = _insert_meta_line(
            new_header,
            '# ui_state: ' + json.dumps(ui_state, ensure_ascii=False, separators=(',', ':')),
            4,
        )
    if notes is not None and not seen['note'] and str(notes).strip():
        for note_line in str(notes).splitlines():
            new_header = _insert_meta_line(new_header, f'# note: {note_line}', 5)
    if not seen['generated']:
        stamp = datetime.datetime.now().isoformat(timespec='seconds')
        new_header = _insert_meta_line(new_header, f'# generated: {stamp} by {generated_by}', 6)

    return '\n'.join(new_header + body)


def _format_preamp(preamp_db):
    preamp_val = float(preamp_db or 0)
    if abs(preamp_val) >= 100:
        return f'{preamp_val:.2f}'.rstrip('0').rstrip('.')
    return f'{preamp_val:.4f}'.rstrip('0').rstrip('.')


def render_preset(bands, preamp_db=0.0, name='', device_id='', target_id='',
                  device_scope=DEFAULT_APO_SCOPE, generated_by='mixer_web',
                  notes='', fit=None, ui_state=None):
    lines = []
    if name:
        lines.append(f'# name: {name}')
    if device_id:
        lines.append(f'# device: {device_id}')
    if target_id:
        lines.append(f'# target: {target_id}')
    if fit:
        lines.append(f'# fit: {json.dumps(fit, ensure_ascii=False, separators=(",", ":"))}')
    if ui_state:
        lines.append(f'# ui_state: {json.dumps(ui_state, ensure_ascii=False, separators=(",", ":"))}')
    if notes:
        for note_line in str(notes).splitlines():
            lines.append(f'# note: {note_line}')
    lines.append(f'# generated: {datetime.datetime.now().isoformat(timespec="seconds")} by {generated_by}')
    lines.append('')
    lines.append(f'Device: {device_scope or DEFAULT_APO_SCOPE}')
    lines.append(f'Preamp: {_format_preamp(preamp_db)} dB')
    lines.append('')
    n = 0
    for band in bands or []:
        n += 1
        enabled = band.get('enabled', True) is not False
        btype = str(band.get('type') or 'PK').upper()
        if btype not in ('PK', 'LS', 'HS', 'LP', 'HP'):
            btype = 'PK'
        freq = float(band.get('freq') or 1000)
        gain = float(band.get('gain_db', band.get('gain', 0)) or 0)
        q = float(band.get('q') or band.get('Q') or 1)
        state = 'ON' if enabled else 'OFF'
        if btype in ('LP', 'HP'):
            lines.append(f'Filter {n}: {state} {btype} Fc {freq:g} Hz')
        else:
            lines.append(f'Filter {n}: {state} {btype} Fc {freq:g} Hz Gain {gain:g} dB Q {q:g}')
    return '\n'.join(lines) + '\n'


def render_original_preset(preset_id, preamp_db=0.0, name='', device_id='',
                           target_id='', device_scope=DEFAULT_APO_SCOPE,
                           generated_by='mixer_web'):
    lines = []
    if name:
        lines.append(f'# name: {name}')
    if device_id:
        lines.append(f'# device: {device_id}')
    if target_id:
        lines.append(f'# target: {target_id}')
    lines.append('# ab: original')
    lines.append(f'# original_of: {preset_id}')
    lines.append(f'# generated: {datetime.datetime.now().isoformat(timespec="seconds")} by {generated_by} (original)')
    lines.append('')
    lines.append(f'Device: {device_scope or DEFAULT_APO_SCOPE}')
    lines.append(f'Preamp: {_format_preamp(preamp_db)} dB')
    lines.append('')
    return '\n'.join(lines) + '\n'


class ApoBackend:
    def __init__(self, preset_dir=None, config_dir=None):
        self.preset_dir = preset_dir or os.environ.get('APO_PRESET_DIR') or DEFAULT_PRESET_DIR
        self.config_dir = config_dir or os.environ.get('APO_CONFIG_DIR') or _get_apo_config_dir()
        self.presets_path = os.path.join(self.preset_dir, 'presets.json')
        self.state_path = os.path.join(self.preset_dir, 'apo-state.json')
        self.active_path = os.path.join(self.config_dir, 'hl-active.txt')
        self.config_path = os.path.join(self.config_dir, 'config.txt')
        self._lock = threading.RLock()
        os.makedirs(self.preset_dir, exist_ok=True)

    def _preset_path(self, preset_id):
        return os.path.join(self.preset_dir, str(preset_id) + '.txt')

    def _read_preset_text(self, preset_id):
        path = self._preset_path(preset_id)
        return _read_text(path)

    def _write_preset_text(self, preset_id, text):
        _atomic_write(self._preset_path(preset_id), text)

    def _write_presets_cache(self, presets):
        _atomic_write(self.presets_path, json.dumps(presets, ensure_ascii=False, indent=2))

    def _write_apo_state(self, active_id, by='backend', original=False):
        _atomic_write(self.state_path, json.dumps({
            'active_id': active_id,
            'original': bool(original),
            'updated_at': datetime.datetime.now().isoformat(timespec='seconds'),
            'by': by,
        }, ensure_ascii=False, indent=2))

    # ---------- 预设排序 ----------
    # 约定:
    # - pure 固定置顶
    # - preset-order.json 保存用户拖动后的完整顺序（数组 = 预设 id）
    # - 新建/改绑设备时自动插到同设备预设块内，保持同设备预设相邻
    def _preset_order_path(self):
        return os.path.join(self.preset_dir, 'preset-order.json')

    def _load_preset_order(self):
        try:
            with open(self._preset_order_path(), 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data if isinstance(x, (str, int))]
        except Exception:
            pass
        return []

    def _write_preset_order(self, order):
        clean = []
        for x in order:
            if isinstance(x, str) and x not in clean:
                clean.append(x)
        _atomic_write(self._preset_order_path(), json.dumps(clean, ensure_ascii=False, indent=2))

    def _scan_preset_items(self):
        items = []
        if os.path.isdir(self.preset_dir):
            for fname in sorted(os.listdir(self.preset_dir)):
                if not fname.lower().endswith('.txt'):
                    continue
                if fname in ('hl-active.txt', 'config.txt'):
                    continue
                preset_id = fname[:-4]
                text = _read_text(os.path.join(self.preset_dir, fname))
                if text is None:
                    continue
                lines = text.splitlines()
                name, device_id, target_id, _ = _parse_meta(lines)
                notes = _parse_notes(lines)
                # 预设库允许最多 20 段；读取时必须关闭解析器截断，否则 band_count 会虚报。
                parsed = parse_eq(text, max_bands=None)
                items.append({
                    'id': preset_id,
                    'name': name or preset_id,
                    'device_id': device_id,
                    'target_id': target_id,
                    'band_count': len(parsed.get('bands', [])),
                    'notes': notes,
                    'ui_state': _parse_ui_state(lines),
                    'mtime': os.path.getmtime(os.path.join(self.preset_dir, fname)),
                })
        return items

    def _normalize_preset_order(self, order, items):
        by_id = {p['id']: p for p in items}
        used = set()
        out = []
        if 'pure' in by_id:
            out.append('pure')
            used.add('pure')
        for pid in order or []:
            pid = str(pid).strip()
            if pid and pid in by_id and pid not in used:
                out.append(pid)
                used.add(pid)
        remaining = [p for p in items if p['id'] not in used]
        groups = []
        group_index = {}
        for p in remaining:
            dev = p.get('device_id') or ''
            if dev not in group_index:
                group_index[dev] = len(groups)
                groups.append([])
            groups[group_index[dev]].append(p)
        for group in groups:
            dev = group[0].get('device_id') or ''
            insert_at = len(out)
            for i in range(len(out) - 1, -1, -1):
                if out[i] == 'pure':
                    continue
                if (by_id[out[i]].get('device_id') or '') == dev:
                    insert_at = i + 1
                    break
            for j, p in enumerate(group):
                out.insert(insert_at + j, p['id'])
        return out

    def _insert_preset_in_order(self, preset_id):
        items = self._scan_preset_items()
        target = next((p for p in items if p['id'] == preset_id), None)
        if target is None:
            return
        others = [p for p in items if p['id'] != preset_id]
        order = self._normalize_preset_order(self._load_preset_order(), others)
        order = [str(x) for x in order if str(x) != preset_id]
        by_id = {p['id']: p for p in others}
        dev = target.get('device_id') or ''
        same_positions = [i for i, pid in enumerate(order) if pid != 'pure' and (by_id.get(pid, {}).get('device_id') or '') == dev]
        if same_positions:
            order.insert(same_positions[-1] + 1, preset_id)
        else:
            order.append(preset_id)
        self._write_preset_order(order)

    def set_preset_order(self, order):
        with self._lock:
            items = self._scan_preset_items()
            normalized = self._normalize_preset_order(order, items)
            self._write_preset_order(normalized)
            return self.list_presets()

    def list_presets(self):
        with self._lock:
            items = self._scan_preset_items()
            order = self._load_preset_order()
            normalized = self._normalize_preset_order(order, items)
            if normalized != order:
                self._write_preset_order(normalized)
            by_id = {p['id']: p for p in items}
            ordered_items = [by_id[pid] for pid in normalized]
            for idx, p in enumerate(ordered_items):
                p['sort_order'] = idx
            self._write_presets_cache(ordered_items)
            return ordered_items

    def get_preset(self, preset_id):
        with self._lock:
            text = self._read_preset_text(preset_id)
            if text is None:
                return None
            lines = text.splitlines()
            name, device_id, target_id, device_scope = _parse_meta(lines)
            notes = _parse_notes(lines)
            # 关闭截断：预设文件可含 20 段（自动拟合上限），读回后前端才能完整显示。
            parsed = parse_eq(text, max_bands=None)
            return {
                'id': preset_id,
                'name': name or preset_id,
                'device_id': device_id,
                'target_id': target_id,
                'device_scope': device_scope or DEFAULT_APO_SCOPE,
                'bands': parsed.get('bands', []),
                'preamp_db': parsed.get('preamp_db', 0),
                'notes': notes,
                'fit': _parse_fit(lines),
                'ui_state': _parse_ui_state(lines),
                'config_text': text,
            }

    def create_preset(self, name, device_id=''):
        with self._lock:
            name = str(name or '新预设').strip() or '新预设'
            base = _slug(name)
            preset_id = base
            n = 2
            while os.path.exists(self._preset_path(preset_id)):
                preset_id = f'{base}-{n}'
                n += 1
            text = render_preset([], -6.0, name=name, device_id=device_id, target_id='')
            self._write_preset_text(preset_id, text)
            self._insert_preset_in_order(preset_id)
            self.list_presets()
            return self.get_preset(preset_id)

    def update_preset(self, preset_id, bands, preamp_db=0.0, name=None, device_id=None,
                      target_id=None, device_scope=None, notes=None, fit=None, ui_state=None,
                      auto_preamp=True):
        """重写预设。

        auto_preamp=True 时按 bands 的串联频响峰值自动计算 Preamp；
        撤销/回退场景传 auto_preamp=False，以原样恢复历史版本的 Preamp。
        """
        with self._lock:
            existing = self.get_preset(preset_id)
            if existing is None:
                return None
            cur_name = existing['name'] if name is None else name
            cur_device_id = existing['device_id'] if device_id is None else device_id
            cur_target_id = existing['target_id'] if target_id is None else target_id
            cur_scope = existing['device_scope'] if device_scope is None else device_scope
            cur_notes = existing['notes'] if notes is None else notes
            cur_fit = existing.get('fit') if fit is None else fit
            cur_ui_state = existing.get('ui_state') if ui_state is None else ui_state
            if auto_preamp:
                try:
                    from autofit import calculate_preamp_db
                    preamp_db = calculate_preamp_db(bands)
                except Exception:
                    # 自动计算失败时保留调用方传入值，避免保存被拖垮。
                    pass
            text = render_preset(
                bands, preamp_db,
                name=cur_name,
                device_id=cur_device_id,
                target_id=cur_target_id,
                device_scope=cur_scope,
                notes=cur_notes,
                fit=cur_fit,
                ui_state=cur_ui_state,
            )
            self._write_preset_text(preset_id, text)
            if cur_device_id != existing.get('device_id'):
                self._insert_preset_in_order(preset_id)
            self.list_presets()
            return self.get_preset(preset_id)

    def update_preset_meta(self, preset_id, notes=None, device_id=None, target_id=None,
                           name=None, fit=None, ui_state=None, generated_by='mixer_web'):
        """只替换元数据行；Device/Preamp/Filter 行一字不动。

        这是 notes/device/target/rename 等元数据接口的专用写入路径，避免
        “get_preset(有损读取) -> render_preset(整篇重渲染)”导致 >10 段预设被截断。
        传入 None 的字段保持原值；fit/ui_state 默认原样保留。
        """
        with self._lock:
            text = self._read_preset_text(preset_id)
            if text is None:
                return None
            old_device_id = _parse_meta(text.splitlines())[1]
            new_text = rewrite_preset_meta(
                text,
                name=name,
                device_id=device_id,
                target_id=target_id,
                notes=notes,
                fit=fit,
                ui_state=ui_state,
                generated_by=generated_by,
            )
            self._write_preset_text(preset_id, new_text)
            if device_id is not None and str(device_id).strip() != old_device_id:
                self._insert_preset_in_order(preset_id)
            self.list_presets()
            return self.get_preset(preset_id)

    def delete_preset(self, preset_id):
        with self._lock:
            if self.active_preset_id() == preset_id:
                self.activate(None)
            path = self._preset_path(preset_id)
            if os.path.exists(path):
                os.remove(path)
            order = self._load_preset_order()
            if preset_id in order:
                order.remove(preset_id)
                self._write_preset_order(order)
            self.list_presets()
            return True

    def activate(self, preset_id, by='backend', original=False):
        with self._lock:
            self._ensure_config_writable()
            if preset_id is None:
                _atomic_write(self.active_path, '# peq-webui direct bypass\n')
                self._write_apo_state(None, by=by)
                return True
            preset = self.get_preset(preset_id)
            if preset is None:
                raise ValueError('preset_not_found')
            if original:
                text = render_original_preset(
                    preset_id,
                    preset['preamp_db'],
                    name=preset['name'],
                    device_id=preset['device_id'],
                    target_id=preset['target_id'],
                    device_scope=preset['device_scope'],
                    generated_by=by or 'backend',
                )
            else:
                text = preset['config_text']
            _atomic_write(self.active_path, text)
            self._write_apo_state(preset_id, by=by, original=bool(original))
            return True

    @staticmethod
    def _active_original_from_text(active_text):
        if not active_text:
            return False
        for line in active_text.splitlines():
            if line.strip().lower().startswith('# ab:'):
                return 'original' in line.strip().lower()
        return False

    def active_preset_id(self):
        with self._lock:
            active_text = _read_text(self.active_path)
            if not active_text or not normalize_text(active_text).strip('# \t\r\n'):
                return None
            if self._active_original_from_text(active_text):
                original_of = None
                for line in active_text.splitlines():
                    if line.startswith('# original_of:'):
                        original_of = line[len('# original_of:'):].strip()
                        break
                if original_of:
                    if os.path.isfile(self._preset_path(original_of)):
                        return original_of
                    return None
            active_hash = _hash_text(active_text)
            if os.path.isdir(self.preset_dir):
                for fname in os.listdir(self.preset_dir):
                    if not fname.lower().endswith('.txt'):
                        continue
                    if fname in ('hl-active.txt', 'config.txt'):
                        continue
                    preset_id = fname[:-4]
                    ptext = _read_text(os.path.join(self.preset_dir, fname))
                    if ptext is not None and _hash_text(ptext) == active_hash:
                        return preset_id
            return None

    def active_original(self):
        with self._lock:
            active_text = _read_text(self.active_path)
            return self._active_original_from_text(active_text)

    def is_installed(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY_PATH) as key:
                value, _ = winreg.QueryValueEx(key, 'ConfigPath')
                return bool(value)
        except Exception:
            return False

    def is_managed(self):
        text = _read_text(self.config_path)
        if not text:
            return False
        if 'Include: hl-active.txt' not in text:
            return False
        return MANAGED_MARKER in text or LEGACY_MANAGED_MARKER in text

    def is_mounted_fiio(self):
        for fname in os.listdir(self.preset_dir) if os.path.isdir(self.preset_dir) else []:
            if not fname.lower().endswith('.txt'):
                continue
            if fname in ('hl-active.txt', 'config.txt'):
                continue
            text = _read_text(os.path.join(self.preset_dir, fname))
            if text and 'Device: Fiio' in text:
                return True
        return False

    def is_elevated(self):
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def status(self):
        active_id = self.active_preset_id()
        active_name = None
        if active_id:
            p = self.get_preset(active_id)
            if p:
                active_name = p.get('name') or active_id
        return {
            'installed': self.is_installed(),
            'managed': self.is_managed(),
            'mounted_fiio': self.is_mounted_fiio(),
            'active_preset_id': active_id,
            'active_preset_name': active_name,
            'active_original': self.active_original(),
            'elevated': self.is_elevated(),
        }

    def _ensure_config_writable(self):
        if not os.path.isdir(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
        probe = os.path.join(self.config_dir, '.write-probe')
        try:
            with open(probe, 'w', encoding='utf-8') as f:
                f.write('ok')
            os.remove(probe)
        except OSError:
            if not self._grant_config_dir_write_permission():
                raise OSError(f'APO 配置目录不可写: {self.config_dir}')

    def _probe_config_writable(self):
        try:
            self._ensure_config_writable()
            return True
        except OSError:
            return False

    def _grant_config_dir_write_permission(self):
        if not os.path.isdir(self.config_dir):
            return False
        script = os.path.join(tempfile.gettempdir(), 'grant-apo-config-write.ps1')
        lines = [
            "Continue = 'Stop'",
            f"icacls '{self.config_dir}' /grant '*S-1-5-32-545:(OI)(CI)F' /T",
        ]
        try:
            with open(script, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-Command', f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-File','{script}'"],
                timeout=120, check=False,
            )
        except Exception:
            return False
        finally:
            try:
                if os.path.isfile(script):
                    os.remove(script)
            except Exception:
                pass
        return self._probe_config_writable()

    def _migration_info_path(self):
        return os.path.join(self.preset_dir, 'migration.json')

    def _load_migration_info(self):
        path = self._migration_info_path()
        if os.path.isfile(path):
            try:
                with open(path, 'rb') as f:
                    return json.loads(f.read().decode('utf-8-sig'))
            except Exception:
                pass
        return {}

    def _save_migration_info(self, info):
        _atomic_write(self._migration_info_path(), json.dumps(info, ensure_ascii=False, indent=2))

    def _set_config_path_registry(self, path):
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY_PATH) as key:
                winreg.SetValueEx(key, 'ConfigPath', 0, winreg.REG_SZ, str(path))
            return True
        except Exception:
            return False

    def _read_config_path_registry(self):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REGISTRY_KEY_PATH) as key:
                value, _ = winreg.QueryValueEx(key, 'ConfigPath')
                return str(value)
        except Exception:
            return None

    def _set_config_path_registry_elevated(self, path):
        script = os.path.join(tempfile.gettempdir(), 'set-apo-config-path.ps1')
        try:
            with open(script, 'w', encoding='utf-8') as f:
                f.write(
                    f"Continue = 'Stop'\n"
                    f"New-Item -Path 'HKLM:\\SOFTWARE\\EqualizerAPO' -Force | Out-Null\n"
                    f"Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\EqualizerAPO' -Name 'ConfigPath' -Value '{path}'\n"
                )
            subprocess.run(
                ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                 '-Command', f"Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile','-File','{script}'"],
                timeout=120, check=False,
            )
        except Exception:
            return False
        finally:
            try:
                if os.path.isfile(script):
                    os.remove(script)
            except Exception:
                pass
        return self._read_config_path_registry() == str(path)

    def migrate_to_user_config_dir(self):
        local_dir = _default_user_config_dir()
        os.makedirs(local_dir, exist_ok=True)
        original_dir = self._read_config_path_registry()
        if not original_dir:
            original_dir = r'C:\Program Files\EqualizerAPO\config'
        src_config = os.path.join(original_dir, 'config.txt')
        dst_config = os.path.join(local_dir, 'config.txt')
        if not os.path.isfile(dst_config) and os.path.isfile(src_config):
            shutil.copyfile(src_config, dst_config)
        elif not os.path.isfile(dst_config):
            _atomic_write(dst_config, MANAGED_MARKER + '\n' + MANAGED_INCLUDE + '\n')
        hl = os.path.join(local_dir, 'hl-active.txt')
        if not os.path.isfile(hl):
            _atomic_write(hl, '# peq-webui direct bypass\n')
        bak = os.path.join(local_dir, 'config.txt.bak-headphonelab')
        if not os.path.isfile(bak) and os.path.isfile(src_config):
            try:
                shutil.copyfile(src_config, bak)
            except Exception:
                pass
        self.config_dir = local_dir
        self.active_path = os.path.join(self.config_dir, 'hl-active.txt')
        self.config_path = os.path.join(self.config_dir, 'config.txt')
        if not self._set_config_path_registry(local_dir):
            self._set_config_path_registry_elevated(local_dir)
        self._save_migration_info({
            'migrated': True,
            'original_config_dir': original_dir,
            'local_config_dir': local_dir,
            'migrated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        })
        return True

    def install(self, by='backend'):
        if not os.path.isdir(self.config_dir):
            self.migrate_to_user_config_dir()
        self._ensure_config_writable()
        text = _read_text(self.config_path)
        if not text:
            text = ''
        if MANAGED_INCLUDE not in text:
            lines = []
            if MANAGED_MARKER not in text:
                lines.append(MANAGED_MARKER)
            if text.strip():
                lines.append(text.rstrip())
            lines.append(MANAGED_INCLUDE)
            _atomic_write(self.config_path, '\n'.join(lines) + '\n')
        if not os.path.isfile(self.active_path):
            _atomic_write(self.active_path, '# peq-webui direct bypass\n')
        return self.status()

    def uninstall(self, by='backend'):
        info = self._load_migration_info()
        original_dir = info.get('original_config_dir')
        local_dir = self.config_dir
        text = _read_text(self.config_path) or ''
        new_lines = []
        for line in text.splitlines():
            if line.strip() == MANAGED_INCLUDE:
                continue
            if line.strip() in (MANAGED_MARKER, LEGACY_MANAGED_MARKER):
                continue
            new_lines.append(line)
        _atomic_write(self.config_path, '\n'.join(new_lines).rstrip() + '\n')
        if original_dir and original_dir != local_dir:
            if not self._set_config_path_registry(original_dir):
                self._set_config_path_registry_elevated(original_dir)
        self._save_migration_info({'migrated': False, 'original_config_dir': original_dir})
        return self.status()

    def _auto_install_flag_path(self):
        return os.path.join(self.preset_dir, 'auto-install.json')

    def is_auto_install_enabled(self):
        path = self._auto_install_flag_path()
        if os.path.isfile(path):
            try:
                with open(path, 'rb') as f:
                    return bool(json.loads(f.read().decode('utf-8-sig')).get('enabled', False))
            except Exception:
                pass
        return False

    def set_auto_install_enabled(self, enabled):
        _atomic_write(self._auto_install_flag_path(), json.dumps({'enabled': bool(enabled)}, ensure_ascii=False, indent=2))

    def auto_install(self):
        if not self.is_auto_install_enabled():
            return self.status()
        if self.is_managed() and os.path.isfile(self.active_path):
            return self.status()
        return self.install(by='auto')


if __name__ == '__main__':
    apo = ApoBackend()
    print(json.dumps(apo.status(), ensure_ascii=False, indent=2))
    print('presets:', [p['id'] for p in apo.list_presets()])