# -*- coding: utf-8 -*-
"""
mixer_web.py - PEQ WebUI 鍚庣锛圗qualizerAPO 鐗?/ 鏂规 A锛?

鐗规€?
- 鍙洃鍚?127.0.0.1:9100銆?
- 鍚屾簮鎵樼 peq-webui/webui 闈欐€佹枃浠讹紝REST + SSE銆?
- 鎵€鏈?APO 鍐欓兘鏄師瀛愭枃浠舵浛鎹紝鏃犵淮鎶ゆā寮忋€佹棤 Reaper/8080 渚濊禆銆?
- 棰勮鍐呭鍞竴鍐欒€呬负鏈悗绔紱鍛婄ず鏉?鍏朵粬杩涚▼涔熷彲鎵ц婵€娲伙紝鏈€鍚庡啓鑰呰耽銆?

杩愯:
  py mixer_web.py [--port 9100]
鐜鍙橀噺:
  MIXER_STATE_FILE=...        瑕嗙洊 state.json
  MIXER_WEBUI_DIR=...         瑕嗙洊鍓嶇闈欐€佺洰褰?
  APO_PRESET_DIR=...          瑕嗙洊棰勮浠撳簱锛堟祴璇曠敤锛?
  APO_CONFIG_DIR=...          瑕嗙洊 APO 閰嶇疆鐩綍锛堟祴璇曠敤锛?
"""
import argparse
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WEBUI_DIR = os.path.join(BASE_DIR, 'webui')
# /api/eq/apply 缺省 ui_state 的图例默认值：四项主曲线全开。
DEFAULT_LEGEND = {
    'device': True,
    'target': True,
    'eq': True,
    'equalized': True,
    'applied': False,
    'draft': False,
    'preview': False,
}
SINGLETON_LOCK_PATH = os.path.join(BASE_DIR, 'peq-webui.lock')
_singleton_lock_fd = None

from apo_backend import ApoBackend, render_original_preset
from autoeq_store import AutoEqStore
from curve_store import CurveStore, apply_curve_delta
from eq_parser import parse_eq, parse_eq_file
from autofit import autofit
from autoeq_engine import autofit_precise, PRECISE_AVAILABLE
from rig_guard import CROSS_RIG_FMAX, check_cross_rig
from state_store import StateStore

apo = ApoBackend()
store = StateStore()
curves = CurveStore()
autoeq = AutoEqStore()


def _acquire_singleton_lock(wait=False, timeout=30.0):
    """跨进程单例锁：保证同一时间只有一个 mixer_web.py 后端进程。

    使用 Windows msvcrt 对 peq-webui.lock 首字节加非阻塞锁；进程退出时系统自动释放。
    wait=True 用于 /api/admin/restart 拉起的新进程：旧进程即将退出，等待其释放锁后再接管。
    返回值：True=已获得锁；False=已有实例占用；None=锁文件操作失败（非占用）。
    """
    global _singleton_lock_fd
    try:
        import msvcrt
    except ImportError:
        # 非 Windows 环境退化为端口互斥，不额外阻止启动。
        return True

    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(SINGLETON_LOCK_PATH, os.O_RDWR | os.O_CREAT)
        except OSError:
            if wait and time.time() < deadline:
                time.sleep(0.2)
                continue
            return None

        try:
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'0')
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError:
                os.close(fd)
                if wait and time.time() < deadline:
                    time.sleep(0.5)
                    continue
                return False

            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, ('%010d' % os.getpid()).encode('ascii'))
            os.fsync(fd)
            _singleton_lock_fd = fd
            return True
        except Exception:
            try:
                os.close(fd)
            except Exception:
                pass
            return None


def _release_singleton_lock():
    """显式释放单例锁（进程退出时也会自动释放）。"""
    global _singleton_lock_fd
    if _singleton_lock_fd is None:
        return
    try:
        import msvcrt
        os.lseek(_singleton_lock_fd, 0, os.SEEK_SET)
        msvcrt.locking(_singleton_lock_fd, msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    try:
        os.close(_singleton_lock_fd)
    except Exception:
        pass
    _singleton_lock_fd = None


_sse_clients = []
_sse_lock = threading.Lock()


def broadcast(event, data=None):
    payload = data if data is not None else {}
    with _sse_lock:
        clients = list(_sse_clients)
    body = f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'
    for wfile in clients:
        try:
            wfile.write(body.encode('utf-8'))
            wfile.flush()
        except Exception:
            try:
                if wfile in _sse_clients:
                    _sse_clients.remove(wfile)
            except Exception:
                pass


# ---- external active-state watcher (2026-08-29) ----
# Bidirectional display sync: external writers (DesktopWidget apo-engine,
# by='widget') update activation state via apo-state.json, but the backend
# never notices and the webui frontend stays stale. This watcher polls the
# (updated_at, active_id, by) signal of apo-state.json and broadcasts
# 'preset_activated' whenever the state changed by a non-backend writer, so
# the frontend auto-refreshes to whatever is actually loaded in APO.
_last_state_sig = None


def _read_state_sig():
    """Read apo-state.json as (updated_at, active_id, by); None on failure."""
    try:
        with open(apo.state_path, 'rb') as f:
            raw = f.read()
    except Exception:
        return None
    try:
        st = json.loads(raw.decode('utf-8-sig'))
        return (st.get('updated_at'), st.get('active_id'), st.get('by'))
    except Exception:
        return None


def _state_watcher():
    global _last_state_sig
    _last_state_sig = _read_state_sig()
    while True:
        time.sleep(1)
        try:
            sig = _read_state_sig()
            if sig is None or sig == _last_state_sig:
                continue
            _last_state_sig = sig
            by = sig[2] or 'external'
            if by == 'backend':
                # backend 自身激活已由 activate 显式广播,避免重复刷新
                continue
            try:
                # 以实际生效内容(hl-active.txt 哈希对账)为准
                active_id = apo.active_preset_id()
            except Exception:
                active_id = sig[1]
            broadcast('preset_activated', {'active_preset_id': active_id, 'by': by})
        except Exception:
            pass


def read_body(handler):
    try:
        length = int(handler.headers.get('Content-Length') or 0)
    except (TypeError, ValueError):
        length = 0
    if length <= 0:
        return {}
    try:
        raw = handler.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}


def send_json(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.end_headers()
    handler.wfile.write(body)


def ok(**kwargs):
    return {'ok': True, **kwargs}


def fail(msg):
    return {'ok': False, 'error': msg}


def get_str(params, name, default=None):
    val = params.get(name, default)
    if isinstance(val, list):
        val = val[0] if val else default
    return val


class MixerHTTPHandler(BaseHTTPRequestHandler):
    server_version = 'PEQWeb/1.0'

    def log_message(self, fmt, *args):
        sys.stderr.write('[peq_web %s] %s\n' % (self.log_date_time_string(), fmt % args))

    def _send_json(self, obj, status=200):
        send_json(self, obj, status=status)

    def _read_json(self):
        return read_body(self)

    # ---------- routing ----------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        if path == '/api/events':
            return self._handle_events()
        if path.startswith('/api/'):
            return self._handle_api_get(path, params)
        return self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        return self._handle_api_post(parsed.path)

    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        return self._handle_api_put(parsed.path)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    # ---------- API GET ----------
    def _handle_api_get(self, path, params):
        if path == '/api/status':
            st = apo.status()
            presets = apo.list_presets()
            active_name = st.get('active_preset_id')
            if active_name:
                active_preset = apo.get_preset(active_name)
                if active_preset:
                    active_name = active_preset.get('name') or active_name
            st['active_preset_name'] = active_name or None
            return self._send_json(ok(
                online=True,
                apo=st,
                preset_count=len(presets),
            ))
        if path == '/api/manual':
            manual_path = os.path.join(BASE_DIR, '用户操作手册.md')
            try:
                with open(manual_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            except OSError as e:
                return self._send_json(fail(f'用户操作手册读取失败: {e}'), status=500)
            return self._send_json(ok(text=text, name=os.path.basename(manual_path)))

        if path == '/api/presets':
            presets = apo.list_presets()
            active_id = apo.active_preset_id()
            devices = {d['id']: d for d in curves.list_devices()}
            out = []
            for p in presets:
                dev = devices.get(p.get('device_id', ''), {})
                out.append({
                    'id': p['id'],
                    'name': p['name'],
                    'device_id': p.get('device_id', ''),
                    'device_name': dev.get('name', ''),
                    'target_id': p.get('target_id', ''),
                    'band_count': p.get('band_count', 0),
                    'sort_order': p.get('sort_order', 0),
                    'active': p['id'] == active_id,
                    'mtime': p.get('mtime'),
                    'ui_state': p.get('ui_state', {}),
                })
            return self._send_json(ok(presets=out, active_preset_id=active_id, order=[p['id'] for p in presets]))

        if path == '/api/devices':
            return self._send_json(curves.list_devices())

        if path == '/api/targets':
            return self._send_json(curves.list_targets())
        if path == '/api/autoeq/search':
            q = get_str(params, 'q', '')
            return self._send_json(ok(devices=autoeq.search(q)))

        if path == '/api/eq/bands':
            preset = get_str(params, 'preset')
            if not preset:
                return self._send_json(fail('缺少 preset 参数'))
            p = apo.get_preset(preset)
            if not p:
                return self._send_json(fail('preset_not_found'))
            applied = store.get_applied(preset)
            return self._send_json(ok(
                applied=applied.get('bands', p.get('bands', [])),
                preamp_db=applied.get('preamp_db', p.get('preamp_db', 0)),
                snapshot_id=applied.get('snapshot_id'),
                device_id=p.get('device_id', ''),
                target_id=p.get('target_id', ''),
                fit=p.get('fit') or {},
                ui_state=p.get('ui_state') or {},
            ))

        if path == '/api/preset/config':
            preset = get_str(params, 'id')
            if not preset:
                return self._send_json(fail('缺少 id 参数'))
            p = apo.get_preset(preset)
            if not p:
                return self._send_json(fail('preset_not_found'))
            original = get_str(params, 'original', '') in ('1', 'true', 'yes', 'on')
            config_text = p['config_text']
            if original:
                config_text = render_original_preset(
                    preset,
                    p['preamp_db'],
                    name=p['name'],
                    device_id=p['device_id'],
                    target_id=p['target_id'],
                    device_scope=p['device_scope'],
                )
            return self._send_json(ok(
                id=preset,
                name=p['name'],
                device_id=p['device_id'],
                target_id=p['target_id'],
                notes=p.get('notes', ''),
                ui_state=p.get('ui_state', {}),
                config_text=config_text,
            ))

        if path == '/api/curves/rig_diff':
            device_id = get_str(params, 'device_id')
            rig_from = get_str(params, 'rig_from')
            rig_to = get_str(params, 'rig_to')
            if not device_id:
                return self._send_json(fail('缺少 device_id'))
            diff = curves.rig_diff(device_id, rig_from=rig_from or None, rig_to=rig_to or None)
            if not diff:
                return self._send_json(fail('rig_diff_unavailable: 未找到同型号双 rig 数据'), status=404)
            return self._send_json(ok(**diff))

        m = re.match(r'^/api/curves/device/([^/]+)$', path)
        if m:
            item = curves.get_device(urllib.parse.unquote(m.group(1)))
            if not item:
                return self._send_json(fail('device_not_found'))
            return self._send_json(ok(**item))

        m = re.match(r'^/api/curves/target/([^/]+)$', path)
        if m:
            item = curves.get_target(urllib.parse.unquote(m.group(1)))
            if not item:
                return self._send_json(fail('target_not_found'))
            return self._send_json(ok(**item))

        return self._send_json(fail('api_not_found'), status=404)

    # ---------- API POST ----------
    def _handle_api_post(self, path):
        body = self._read_json()

        if path == '/api/eq/parse':
            res = parse_eq(str(body.get('text', '')))
            res.pop('adapted', None)
            return self._send_json(ok(**res))

        if path == '/api/eq/parse_file':
            file_path = str(body.get('path', '')).strip()
            return self._send_json(ok(**parse_eq_file(file_path)))

        if path == '/api/eq/autofit':
            return self._send_json(self._autofit(body))

        if path == '/api/autoeq/import':
            return self._send_json(self._autoeq_import(body))
        if path == '/api/autoeq/import_target':
            return self._send_json(self._autoeq_import_target(body))

        if path == '/api/curves/import':
            return self._send_json(self._import_curve(body))
            return self._send_json(self._import_curve(body))

        if path == '/api/eq/apply':
            return self._send_json(self._apply(body))

        if path == '/api/eq/revert':
            return self._send_json(self._revert(body))

        if path == '/api/preset/activate':
            return self._send_json(self._activate(body))

        if path == '/api/preset/add':
            return self._send_json(self._add_preset(body))

        if path == '/api/preset/del':
            return self._send_json(self._del_preset(body))
        if path == '/api/preset/order':
            return self._send_json(self._set_preset_order(body))
        if path == '/api/preset/rename':
            return self._send_json(self._rename_preset(body))

        if path == '/api/admin/install':
            return self._send_json(self._install())
            return self._send_json(self._install())

        if path == '/api/admin/uninstall':
            return self._send_json(self._uninstall())

        if path == '/api/admin/restart-elevated':
            return self._send_json(self._restart_elevated())

        if path == '/api/admin/stop':
            return self._send_json(self._stop_service())
        if path == '/api/admin/restart':
            return self._send_json(self._restart_service())

        if path == '/api/admin/maintenance':
            # 鏂规 A锛氬簾寮冩帴鍙ｏ紝淇濈暀涓?no-op 鍏煎鏃у墠绔?
            return self._send_json(ok(maintenance=False))

        return self._send_json(fail('api_not_found'), status=404)

    # ---------- API PUT ----------
    def _handle_api_put(self, path):
        if path == '/api/preset/device':
            return self._send_json(self._preset_device(self._read_json()))
        if path == '/api/preset/target':
            return self._send_json(self._preset_target(self._read_json()))
        if path == '/api/preset/notes':
            return self._send_json(self._preset_notes(self._read_json()))
        return self._send_json(fail('api_not_found'), status=404)

    # ---------- implementations ----------
    def _autofit(self, body):
        preset = str(body.get('preset') or body.get('preset_id') or '').strip()
        device_id = body.get('device_id')
        if not device_id and preset:
            p = apo.get_preset(preset)
            device_id = p['device_id'] if p else ''
        if not device_id:
            return fail('autofit 需要 preset 或 device_id')
        device = curves.get_device(device_id)
        target_id = body.get('target')
        if not target_id:
            return fail('缺少 target')
        target = curves.get_target(target_id)
        if not device or not target:
            return fail('device/target not found')
        engine = str(body.get('engine') or 'quick').lower()
        auto_shelf = body.get('auto_shelf', False)
        auto_shelf = auto_shelf in (True, 1, '1', 'true', 'on', 'True')
        # 默认开启听感安全后处理，避免高 Q/正负对消导致声音碎。
        sanitize_enabled = body.get('sanitize_bands', True) in (True, 1, '1', 'true', 'on', 'True')
        # Imported headphone raw curves are already reference-band aligned.
        # For headphone-to-headphone fitting, min_mean_error would subtract real
        # broad tonal differences between models and make the fit look short,
        # so keep it off by default for this target category.
        default_min_mean_error = target.get('category') != 'headphone'
        smooth_enabled = body.get('smooth', True) in (True, 1, '1', 'true', 'on', 'True')
        sharpness_penalty = body.get('sharpness_penalty', True) in (True, 1, '1', 'true', 'on', 'True')
        weight_profile = str(body.get('weight_profile') or 'none').lower()

        # ---- 跨 rig 防护（需求 R2/R3）----
        rig_check = check_cross_rig(device, target)
        allow_cross_rig_hf = body.get('allow_cross_rig_hf', False) in (True, 1, '1', 'true', 'on', 'True')
        try:
            user_fmax = float(body.get('fmax', 10000) or 10000)
        except (TypeError, ValueError):
            return fail('autofit 参数错误: fmax 必须是数字')
        fmax_used = user_fmax
        fmax_clamped = False
        fmax_reason = ''
        warnings_extra = list(rig_check.get('warnings') or [])
        if rig_check.get('cross'):
            if not allow_cross_rig_hf:
                fmax_used = min(user_fmax, CROSS_RIG_FMAX)
                fmax_reason = 'cross-rig'
                if fmax_used < user_fmax:
                    fmax_clamped = True
                    warnings_extra.append(
                        f'已自动将 fmax 从 {user_fmax:g}Hz 收敛到 {fmax_used:g}Hz'
                        f'（跨 rig：目标 {rig_check.get("target_rig") or "未知"}，'
                        f'设备 {rig_check.get("device_rig") or "未知"}）。'
                        f'如需强制高频拟合，请显式传 allow_cross_rig_hf=true。'
                    )
            else:
                fmax_reason = 'cross-rig-allowed'
                warnings_extra.append(
                    f'已按请求允许跨 rig 高频拟合（fmax {user_fmax:g}Hz）：9kHz 以上结果不可验证，请谨慎采用。'
                )

        # 目标曲线快速整形：调整后的目标只用于本次拟合，不写回曲线库
        target_points = target.get('points', []) or [[20, 0], [20000, 0]]
        target_adjust = body.get('target_adjust')
        if isinstance(target_adjust, dict) and any(k in target_adjust and target_adjust.get(k) not in (None, '') for k in ('amount', 'bass_db', 'treble_db', 'tilt_db')):
            try:
                from curve_adjust import apply_target_adjust
                target_points = apply_target_adjust(device.get('points', []), target_points, target_adjust)
            except Exception as e:
                return fail(f'target_adjust 参数错误: {e}')

        # 去 rig 修正（需求 R4，可选）：target' = target + tilt(目标 rig -> 设备 rig)
        de_rig = body.get('de_rig', False) in (True, 1, '1', 'true', 'on', 'True')
        if de_rig:
            target_selector = ' '.join(str(x) for x in (
                rig_check.get('target_source'), rig_check.get('target_rig')) if x)
            device_selector = ' '.join(str(x) for x in (
                rig_check.get('device_source'), rig_check.get('device_rig')) if x)
            try:
                tilt = curves.rig_diff(
                    device_id,
                    rig_from=(target_selector or None),
                    rig_to=(device_selector or None),
                )
            except Exception as e:
                tilt = None
                warnings_extra.append(f'去 rig 修正计算失败：{e}')
            if tilt and tilt.get('points'):
                target_points = apply_curve_delta(target_points, tilt['points'])
                warnings_extra.append(
                    f'已应用去 rig 修正：{tilt.get("rig_from")} → {tilt.get("rig_to")}'
                    f'（同型号双 rig 实测差 RMS {float(tilt.get("rms_db") or 0):.2f}dB）'
                )
            else:
                warnings_extra.append('去 rig 修正不可用：未找到同型号双 rig 数据，已按原目标曲线拟合。')

        common = {
            'source_points': device.get('points', []) or [[20, 0], [20000, 0]],
            'target_points': target_points,
            'filters': int(body.get('filters', 10)),
            'fmin': float(body.get('fmin', 100)),
            'fmax': fmax_used,
            'max_gain_db': float(body.get('max_gain_db', 6)),
            'max_q': float(body.get('max_q', 3)),
            'align': body.get('align', True) in (True, 1, '1', 'true', 'on', 'True'),
            'align_ref_low': float(body.get('align_ref_low', 500.0)),
            'align_ref_high': float(body.get('align_ref_high', 2000.0)),
            'min_mean_error': body.get('min_mean_error', default_min_mean_error) in (True, 1, '1', 'true', 'on', 'True'),
            'min_mean_low': float(body.get('min_mean_low', 100.0)),
            'min_mean_high': float(body.get('min_mean_high', 10000.0)),
            'smooth_oct': (1.0 / 12.0) if smooth_enabled else 0.0,
            'sanitize': sanitize_enabled,
            'weight_profile': weight_profile,
        }

        def finish(res):
            out = dict(res or {})
            out['warnings'] = list(out.get('warnings') or []) + warnings_extra
            return out

        def run_fit(n):
            c = dict(common)
            c['filters'] = n
            q = dict(c)
            q['sharpness_penalty'] = sharpness_penalty
            if engine == 'precise':
                try:
                    hi_fidelity = body.get('hi_fidelity', False) in (True, 1, '1', 'true', 'on', 'True')
                    res = autofit_precise(**c, auto_shelf=auto_shelf, hi_fidelity=hi_fidelity)
                    if target.get('category') == 'headphone' and not hi_fidelity:
                        quick_res = autofit(**q, auto_shelf=auto_shelf)
                        if quick_res.get('rms_db', 1e9) < res.get('rms_db', 1e9) - 0.01:
                            quick_res['warnings'] = list(quick_res.get('warnings') or [])
                            quick_res['warnings'].append('precise engine did not improve this headphone raw fit; using quick result')
                            quick_res['engine'] = 'quick'
                            res = quick_res
                except Exception as e:
                    res = autofit(**q, auto_shelf=auto_shelf)
                    res['warnings'] = list(res.get('warnings') or []) + [f'精确引擎不可用，已回退快速模式: {e}']
                    res['engine'] = 'quick'
            else:
                res = autofit(**q, auto_shelf=auto_shelf)
            return res

        try:
            auto_filters = body.get('auto_filters', False) in (True, 1, '1', 'true', 'on', 'True')
            if auto_filters:
                max_filters = int(body.get('max_filters', 20))
                target_rms = float(body.get('target_rms', 0.5))
                candidates = [n for n in (5, 10, 15, 20) if n <= max_filters]
                if not candidates:
                    candidates = [max_filters]
                suggestions = []
                best = None
                for n in candidates:
                    res = run_fit(n)
                    if res is None:
                        continue
                    suggestions.append({
                        'filters': n,
                        'rms_db': res.get('rms_db'),
                        'weighted_rms_db': res.get('weighted_rms_db'),
                        'preamp_db': res.get('preamp_db'),
                        'res': res,
                    })
                    if best is None or res.get('rms_db', 1e9) < best.get('rms_db', 1e9):
                        best = res
                if not suggestions:
                    return fail('autofit 没有可用结果')
                chosen = next((s for s in suggestions if (s.get('rms_db') or 1e9) <= target_rms), None)
                if chosen is not None:
                    res = chosen['res']
                else:
                    res = best
                    res['warnings'] = list(res.get('warnings') or [])
                    res['warnings'].append(f'目标 RMS {target_rms:.2f} dB 未能达到，已返回最优结果')
                res = finish(res)
                clean_suggestions = []
                for s in suggestions:
                    item = {k: v for k, v in s.items() if k != 'res'}
                    item['bands'] = s['res'].get('bands', [])
                    item['warnings'] = s['res'].get('warnings', [])
                    clean_suggestions.append(item)
                return ok(**res, device_id=device_id, target=target_id, preset=preset or None,
                          auto_filter_suggestions=clean_suggestions,
                          fmax_used=fmax_used, fmax_clamped=fmax_clamped, fmax_reason=fmax_reason,
                          de_rig=bool(de_rig), rig=rig_check)
            else:
                res = run_fit(common['filters'])
        except (TypeError, ValueError) as e:
            return fail(f'autofit 参数错误: {e}')
        res = finish(res)
        return ok(**res, device_id=device_id, target=target_id, preset=preset or None,
                  fmax_used=fmax_used, fmax_clamped=fmax_clamped, fmax_reason=fmax_reason,
                  de_rig=bool(de_rig), rig=rig_check)

    def _import_curve(self, body):
        curve_type = body.get('curve_type')
        name = str(body.get('name', '')).strip()
        text = str(body.get('text', ''))
        kind = body.get('kind')
        category = body.get('category') or body.get('target_category')
        if curve_type not in ('device', 'target'):
            return fail('curve_type 必须是 device 或 target')
        if not name:
            return fail('name 不能为空')
        align_val = body.get('align', True)
        if isinstance(align_val, str):
            align_val = align_val.lower() in ('1', 'true', 'on', 'yes')
        try:
            item = curves.import_curve(
                curve_type, name, text, kind=kind, category=category,
                align=align_val,
                align_ref_low=float(body.get('align_ref_low', 500.0)),
                align_ref_high=float(body.get('align_ref_high', 2000.0)),
                align_method=str(body.get('align_method', 'mean') or 'mean'),
            )
        except ValueError as e:
            return fail(str(e))
        broadcast('status', {'curve': item['id']})
        return ok(item=item)
    def _autoeq_form_kind(self, form):
        if form in ('over-ear', 'on-ear'):
            return 'headphone'
        if form == 'earbud':
            return 'earbud'
        return 'iem'

    def _autoeq_import(self, body):
        device_id = str(body.get('device_id') or '').strip()
        preset_id = str(body.get('preset') or body.get('preset_id') or '').strip()
        activate = bool(body.get('activate', False))
        if not device_id:
            return fail('缺少 device_id')
        entry = autoeq.get(device_id)
        if not entry:
            return fail('autoeq_device_not_found')
        eq = autoeq.read_eq(entry)
        points = autoeq.read_device_csv_points(entry.get('csv_path', ''), column='raw')
        if not points:
            return fail('autoeq_measurement_empty')
        text = '\n'.join(f'{f:.4f},{d:.4f}' for f, d in points)
        meta = autoeq.measurement_meta(entry)
        try:
            curve = curves.import_curve(
                'device', entry['name'], text,
                kind=self._autoeq_form_kind(entry.get('form', 'iem')),
                extra=meta,
            )
        except ValueError as e:
            return fail(f'曲线导入失败: {e}')
        target_id = None
        try:
            target_points = autoeq.read_device_target_points(entry.get('csv_path', ''))
            if target_points:
                target_text = '\n'.join(f'{f:.4f},{d:.4f}' for f, d in target_points)
                target_item = curves.import_curve('target', entry['name'] + ' Target', target_text, kind='target', category='headphone')
                target_id = target_item['id']
        except Exception:
            target_id = None

        if preset_id:
            p = apo.get_preset(preset_id)
            if not p:
                return fail('preset_not_found')
        else:
            p = apo.create_preset(entry['name'], curve['id'])
            preset_id = p['id']

        was_active = apo.active_preset_id() == preset_id
        updated = apo.update_preset(
            preset_id,
            eq.get('bands', []),
            eq.get('preamp_db', 0),
            name=p['name'],
            device_id=curve['id'],
            target_id=target_id,
            device_scope=p['device_scope'],
        )
        if updated is None:
            return fail('preset_not_found')
        preamp_db = float(updated.get('preamp_db', eq.get('preamp_db', 0)) or 0)
        if activate or was_active:
            apo.activate(preset_id, by='backend')
            broadcast('preset_activated', {'active_preset_id': preset_id, 'by': 'backend'})
        broadcast('preset_changed', {'preset': preset_id})
        return ok(
            preset=preset_id,
            applied=updated.get('bands', eq.get('bands', [])),
            preamp_db=preamp_db,
            curve=curve,
            target_id=target_id,
        )
    def _autoeq_import_target(self, body):
        device_id = str(body.get('device_id') or '').strip()
        if not device_id:
            return fail('缺少 device_id')
        entry = autoeq.get(device_id)
        if not entry:
            return fail('autoeq_device_not_found')
        # 浼樺厛璇诲彇 AutoEq CSV 涓殑鍘熷棰戝搷锛坮aw锛夛紝涓埆鏁版嵁娌℃湁 raw 鏃堕€€鍥?smoothed
        points = autoeq.read_device_raw_points(entry.get('csv_path', ''))
        if not points:
            points = autoeq.read_device_csv_points(entry.get('csv_path', ''), column='smoothed')
        if not points:
            return fail('autoeq_measurement_empty')
        name = f'{entry["name"]} (原始频响)'
        text = '\n'.join(f'{f:.4f},{d:.4f}' for f, d in points)
        meta = autoeq.measurement_meta(entry)
        try:
            item = curves.import_curve('target', name, text, kind='target', category='headphone', extra=meta)
        except ValueError as e:
            return fail(f'目标曲线导入失败: {e}')
        broadcast('status', {'curve': item['id']})
        return ok(target_id=item['id'], curve=item)

    def _apply(self, body):
        preset = str(body.get('preset') or body.get('preset_id') or '').strip()
        if not preset:
            return fail('缺少 preset')
        p = apo.get_preset(preset)
        if not p:
            return fail('preset_not_found')
        bands = body.get('bands', [])
        if not isinstance(bands, list):
            return fail('bands 必须是数组')
        requested_preamp_db = float(body.get('preamp_db', 0) or 0)
        activate = bool(body.get('activate', False))
        target_id = body.get('target_id', p.get('target_id') or '')
        target_id = str(target_id).strip() if target_id is not None else ''
        prev = store.get_applied(preset)
        if not prev.get('snapshot_id') and p.get('bands'):
            prev = {'bands': p['bands'], 'preamp_db': p['preamp_db']}
        display_name = p.get('name') or p.get('id') or '预设'
        store.push_history(preset, prev.get('bands', []), prev.get('preamp_db', 0))
        was_active = apo.active_preset_id() == preset

        fit = body.get('fit')
        if not isinstance(fit, dict):
            fit = None
        
        # 获取UI状态：设备选择、自动拟合开关、图例开关。
        # 请求省略 ui_state/legend/auto_fit_enabled 时必须回落到预设现有值，
        # 不能把预设里已有的 UI 状态覆盖为默认关闭。
        ui_state = body.get('ui_state') or {}
        prev_ui = p.get('ui_state') or {}
        device_id = ui_state.get('device_id', p.get('device_id') or '')
        device_id = str(device_id).strip() if device_id is not None else ''
        auto_fit_enabled = ui_state.get('auto_fit_enabled', prev_ui.get('auto_fit_enabled', False))
        legend_state = ui_state.get('legend') or prev_ui.get('legend') or dict(DEFAULT_LEGEND)
        
        updated = apo.update_preset(
            preset,
            bands,
            requested_preamp_db,
            name=display_name,
            device_id=device_id,
            target_id=target_id,
            device_scope=p.get('device_scope'),
            fit=fit,
            ui_state={
                'auto_fit_enabled': auto_fit_enabled,
                'legend': legend_state
            },
            auto_preamp=True,
        )
        if updated is None:
            return fail('preset_not_found')
        # 保存时由后端按当前 bands 重算 Preamp，前端传入值只作兜底。
        preamp_db = float(updated.get('preamp_db', requested_preamp_db) or 0)
        store.set_applied(preset, bands, preamp_db, snapshot_id=store.new_snapshot_id())

        deployed = bool(activate or was_active)
        if deployed:
            apo.activate(preset, by='backend')
            broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        active_id = apo.active_preset_id()
        broadcast('eq_applied', {'preset': preset, 'applied': bands, 'preamp_db': preamp_db, 'activate': deployed})
        broadcast('preset_changed', {'preset': preset})
        return ok(
            applied=bands,
            preamp_db=preamp_db,
            active_preset_id=active_id,
            deployed=deployed,
            config_text=updated['config_text'],
            target_id=target_id,
        )

    def _revert(self, body):
        preset = str(body.get('preset') or body.get('preset_id') or '').strip()
        if not preset:
            return fail('缺少 preset')
        p = apo.get_preset(preset)
        if not p:
            return fail('preset_not_found')
        prev = store.pop_history(preset)
        if prev is None:
            return fail('没有可撤销记录')
        bands = prev.get('bands', [])
        preamp_db = prev.get('preamp_db', 0)
        was_active = apo.active_preset_id() == preset
        updated = apo.update_preset(
            preset,
            bands,
            preamp_db,
            name=p.get('name'),
            device_id=p.get('device_id'),
            target_id=p.get('target_id'),
            device_scope=p.get('device_scope'),
            auto_preamp=False,
        )
        if updated is None:
            return fail('preset_not_found')
        # 回退必须原样恢复历史版本的 Preamp，不能按恢复后的 bands 重算。
        preamp_db = float(updated.get('preamp_db', preamp_db) or 0)
        store.set_applied(preset, bands, preamp_db, snapshot_id=store.new_snapshot_id())
        # 濡傛灉鎾ら攢鐨勬鏄綋鍓嶆縺娲婚璁撅紝閲嶆柊閮ㄧ讲閬垮厤鍐呭涓嶄竴鑷?
        if was_active:
            apo.activate(preset, by='backend')
            broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        broadcast('eq_applied', {'preset': preset, 'applied': bands})
        broadcast('preset_changed', {'preset': preset})
        return ok(preset=preset, applied=bands, preamp_db=preamp_db, config_text=updated['config_text'])

    def _activate(self, body):
        preset = body.get('id')
        if preset is not None:
            preset = str(preset).strip() or None
        original = body.get('original', False) in (True, 1, '1', 'true', 'on', 'True')
        try:
            apo.activate(preset, by='backend', original=original)
        except ValueError as e:
            return fail(str(e))
        broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        return ok(active_preset_id=preset, active_original=bool(preset is not None and original))

    def _add_preset(self, body):
        name = str(body.get('name', '').strip()) or '新预设'
        device_id = str(body.get('device_id', '')).strip()
        p = apo.create_preset(name, device_id)
        broadcast('preset_changed', {'preset': p['id']})
        return ok(preset=p)
    def _set_preset_order(self, body):
        order = body.get('order')
        if not isinstance(order, list):
            return fail('order 必须是数组')
        order = [str(x).strip() for x in order if str(x).strip()]
        try:
            presets = apo.set_preset_order(order)
        except Exception as e:
            return fail('排序保存失败: ' + str(e))
        return ok(order=[p['id'] for p in presets])
    def _rename_preset(self, body):
        preset = str(body.get('id') or body.get('preset') or '').strip()
        name = str(body.get('name', '')).strip()
        if not preset or not name:
            return fail('缺少 id 或 name')
        p = apo.get_preset(preset)
        if not p:
            return fail('preset_not_found')
        was_active = apo.active_preset_id() == preset
        was_original = bool(apo.status().get('active_original', False))
        # 只改元数据：不做 bands 往返，避免 >10 段预设被 parse_eq 静默截断。
        updated = apo.update_preset_meta(preset, name=name)
        if updated is None:
            return fail('preset_not_found')
        if was_active:
            apo.activate(preset, by='backend', original=was_original)
            broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        broadcast('preset_changed', {'preset': preset})
        return ok(preset=updated)

    def _del_preset(self, body):
        preset = str(body.get('id') or body.get('preset') or '').strip()
        if not preset:
            return fail('缺少 id')
        active_before = apo.active_preset_id()
        if active_before == preset:
            apo.activate(None, by='backend')
            broadcast('preset_activated', {'active_preset_id': None, 'by': 'backend'})
        apo.delete_preset(preset)
        broadcast('preset_changed', {'preset': preset})
        return ok(deleted=preset)

    def _preset_notes(self, body):
        preset = str(body.get('id') or body.get('preset') or '').strip()
        if not preset:
            return fail('缺少 id')
        p = apo.get_preset(preset)
        if not p:
            return fail('preset_not_found')
        notes = str(body.get('notes', '') or '')
        was_active = apo.active_preset_id() == preset
        was_original = bool(apo.status().get('active_original', False))
        # 只改元数据：不做 bands 往返，避免 >10 段预设被 parse_eq 静默截断。
        updated = apo.update_preset_meta(preset, notes=notes)
        if updated is None:
            return fail('preset_not_found')
        if was_active:
            apo.activate(preset, by='backend', original=was_original)
            broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        broadcast('preset_changed', {'preset': preset})
        return ok(preset=preset, notes=updated.get('notes', ''))

    def _preset_device(self, body):
        preset = str(body.get('id') or body.get('preset') or '').strip()
        device_id = str(body.get('device_id', '')).strip()
        if not preset:
            return fail('缺少 id')
        p = apo.get_preset(preset)
        if not p:
            return fail('preset_not_found')
        target_id = p.get('target_id') or ''
        was_active = apo.active_preset_id() == preset
        was_original = bool(apo.status().get('active_original', False))
        # 只改元数据：不做 bands 往返，避免 >10 段预设被 parse_eq 静默截断。
        updated = apo.update_preset_meta(preset, device_id=device_id)
        if updated is None:
            return fail('preset_not_found')
        if was_active:
            apo.activate(preset, by='backend', original=was_original)
            broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        broadcast('preset_changed', {'preset': preset})
        return ok(preset=preset, device_id=device_id, device_name=(curves.get_device(device_id) or {}).get('name', ''))
    def _preset_target(self, body):
        preset = str(body.get('id') or body.get('preset') or '').strip()
        target_id = body.get('target_id', '')
        target_id = str(target_id).strip() if target_id is not None else ''
        if not preset:
            return fail('缺少 id')
        p = apo.get_preset(preset)
        if not p:
            return fail('preset_not_found')
        was_active = apo.active_preset_id() == preset
        # 只改元数据：不做 bands 往返，避免 >10 段预设被 parse_eq 静默截断。
        updated = apo.update_preset_meta(preset, target_id=target_id)
        if updated is None:
            return fail('preset_not_found')
        if was_active:
            apo.activate(preset, by='backend', original=bool(apo.status().get('active_original', False)))
            broadcast('preset_activated', {'active_preset_id': preset, 'by': 'backend'})
        broadcast('preset_changed', {'preset': preset})
        return ok(preset=preset, target_id=target_id, target_name=(curves.get_target(target_id) or {}).get('name', ''))

    def _install(self):
        try:
            apo.install(by='backend')
            broadcast('apo_state', apo.status())
            return ok(**apo.status())
        except OSError as e:
            return fail(f'安装失败: {e}')

    def _uninstall(self):
        try:
            apo.uninstall(by='backend')
            broadcast('apo_state', apo.status())
            return ok(**apo.status())
        except OSError as e:
            return fail(f'卸载失败: {e}')

    def _restart_elevated(self):
        if apo.is_elevated():
            return ok(already_elevated=True)
        script = os.path.join(BASE_DIR, 'start-webui.ps1')
        if not os.path.isfile(script):
            return fail('未找到 start-webui.ps1')
        try:
            import ctypes
            ret = ctypes.windll.shell32.ShellExecuteW(
                None,
                'runas',
                'powershell.exe',
                f'-NoProfile -ExecutionPolicy Bypass -File "{script}" -Elevated',
                None,
                0,
            )
            if ret <= 32:
                return fail('无法启动管理员 PowerShell（UAC 可能被拒绝）')
            return ok(restarting=True)
        except Exception as e:
            return fail(f'重启失败: {e}')

    # ---------- 鏈嶅姟鐢熷懡鍛ㄦ湡锛氬仠姝?/ 閲嶅惎 ----------
    # 璇存槑锛歍hreadingHTTPServer.shutdown() 蹇呴』鍦ㄩ潪璇锋眰绾跨▼涓皟鐢紝涓斿搷搴斿厛鍙戝洖瀹㈡埛绔紝
    #       鎵€浠ヨ繖閲岀敤寤惰繜瀹氭椂鍣細鍏堣繑鍥?ok 鍝嶅簲锛屽啀鍏抽棴杩涚▼銆?
    def _schedule_shutdown(self, delay_s=0.8):
        server = getattr(self, 'server', None)
        if server is None:
            return
        def _do():
            try:
                server.shutdown()
            except Exception:
                pass
        threading.Timer(delay_s, _do).start()

    def _stop_service(self):
        """响应延迟 1 秒，停止前后端进程。"""
        port = self.server.server_address[1] if self.server else 9100
        self._schedule_shutdown(0.8)
        return ok(action='stop', port=port, message='服务将在 1 秒内停止')

    def _restart_service(self):
        """在当前进程内拉起独立的后端进程，随后关闭自己（新进程带端口重试，避免端口冲突）。"""
        try:
            import subprocess
        except Exception as e:
            return fail(f'restart 不可用: {e}')
        if self.server is None:
            return fail('无法获取服务实例')
        port = self.server.server_address[1]
        py = sys.executable or 'py'
        script = os.path.abspath(__file__)
        script_dir = os.path.dirname(script)
        out_log = None
        err_log = None
        try:
            out_log = open(os.path.join(script_dir, 'peq-webui.log'), 'ab')
            err_log = open(os.path.join(script_dir, 'peq-webui.err.log'), 'ab')
            creationflags = 0
            if hasattr(subprocess, 'DETACHED_PROCESS'):
                creationflags = subprocess.DETACHED_PROCESS | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            subprocess.Popen(
                [py, script, '--port', str(port), '--wait-lock'],
                cwd=script_dir,
                stdout=out_log,
                stderr=err_log,
                creationflags=creationflags,
                close_fds=True,
            )
        except Exception as e:
            for f in (out_log, err_log):
                try:
                    if f: f.close()
                except Exception:
                    pass
            return fail(f'重启拉起失败: {e}')
        # 鏂拌繘绋嬪惎鍔ㄩ渶瑕佹棫杩涚▼閲婃斁绔彛锛氭柊杩涚▼鍐呯疆绔彛閲嶈瘯锛岃繖閲屽欢杩?1.5 绉掑啀鍏虫棫杩涚▼
        self._schedule_shutdown(1.5)
        return ok(action='restart', port=port, message='已在后台拉起新服务进程，页面将自动重连')

    # ---------- static ----------
    def _serve_static(self, path):
        webui_dir = os.environ.get('MIXER_WEBUI_DIR') or DEFAULT_WEBUI_DIR
        if path == '/':
            path = '/index.html'
        rel = os.path.normpath(path.lstrip('/'))
        if rel.startswith('..') or os.path.isabs(rel):
            return self._send_json(fail('forbidden'), status=403)
        full = os.path.join(webui_dir, rel)
        if not os.path.isfile(full):
            return self._send_json(fail('file_not_found'), status=404)
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        with open(full, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text/') else ''))
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(data)

    # ---------- SSE ----------
    def _handle_events(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        with _sse_lock:
            _sse_clients.append(self.wfile)
        try:
            self.wfile.write(b': connected\n\n')
            self.wfile.flush()
            while True:
                time.sleep(15)
                self.wfile.write(b': heartbeat\n\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_lock:
                try:
                    _sse_clients.remove(self.wfile)
                except ValueError:
                    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=9100)
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--wait-lock', action='store_true',
                    help='等待单例锁释放后启动（/api/admin/restart 内部使用）')
    args = ap.parse_args()
    lock_state = _acquire_singleton_lock(wait=args.wait_lock, timeout=30.0 if args.wait_lock else 0)
    if lock_state is not True:
        if lock_state is None:
            print('PEQ WebUI cannot acquire singleton lock file; startup aborted.', file=sys.stderr, flush=True)
            sys.exit(1)
        if args.wait_lock:
            print('PEQ WebUI timeout waiting for singleton lock; another instance is still running.', file=sys.stderr, flush=True)
            sys.exit(1)
        print('PEQ WebUI already running (singleton lock held), only one instance is allowed.', flush=True)
        sys.exit(0)
    # 绔彛缁戝畾閲嶈瘯锛氫緵 /api/admin/restart 閲嶅惎浜ゆ帴鏈熶娇鐢紙鏃ц繘绋嬮噴鏀惧湪鍏堛€佹柊杩涚▼缁戝畾鍦ㄥ悗锛?
    server = None
    for attempt in range(30):
        try:
            server = ThreadingHTTPServer((args.host, args.port), MixerHTTPHandler)
            break
        except OSError:
            if attempt >= 29:
                raise
            print(f'port {args.port} busy, retry {attempt + 1}/30 ...', flush=True)
            time.sleep(0.5)
    server.daemon_threads = True
    print(f'peq-webui listening on http://{args.host}:{args.port}', flush=True)
    # 外部激活状态 watcher:外部写者（中控等）切换时广播 SSE,webui 前端自动同步(2026-08-29)
    threading.Thread(target=_state_watcher, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\npeq-webui stopped', flush=True)
    finally:
        try:
            server.server_close()
        except Exception:
            pass
        _release_singleton_lock()


if __name__ == '__main__':
    main()



