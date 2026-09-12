# -*- coding: utf-8 -*-
"""
state_store.py - WebUI 本地编辑状态（按 preset id 存储）

state.json 字段:
{
  "applied": {"<preset_id>": {"bands": [], "preamp_db": 0, "snapshot_id": null}},
  "history": {"<preset_id>": [{"bands": [...], "preamp_db": 0}, ...]}
}
"""
import json
import os
import threading
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_STATE_PATH = os.path.join(BASE_DIR, 'state.json')


def _default_state():
    return {
        'applied': {},
        'history': {},
    }


class StateStore:
    def __init__(self, path=None):
        self.path = path or os.environ.get('MIXER_STATE_FILE') or DEFAULT_STATE_PATH
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'rb') as f:
                    data = json.loads(f.read().decode('utf-8-sig'))
                merged = _default_state()
                merged.update(data or {})
                # 旧版 track 数字键迁移：键都是非预设 id 字符串时先当历史档案保留，
                # 新版正常只会使用预设 id；这里不主动清空以免误删。
                return merged
            except Exception:
                return _default_state()
        return _default_state()

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(json.dumps(self._state, ensure_ascii=False, indent=2).encode('utf-8'))
        os.replace(tmp, self.path)

    def get_applied(self, preset_id):
        with self._lock:
            return dict(self._state.get('applied', {}).get(str(preset_id), {'bands': [], 'preamp_db': 0, 'snapshot_id': None}))

    def set_applied(self, preset_id, bands, preamp_db, snapshot_id=None):
        with self._lock:
            self._state.setdefault('applied', {})[str(preset_id)] = {
                'bands': bands,
                'preamp_db': preamp_db,
                'snapshot_id': snapshot_id,
            }
            self._save()
            return dict(self._state['applied'][str(preset_id)])

    def push_history(self, preset_id, bands, preamp_db):
        with self._lock:
            key = str(preset_id)
            hist = self._state.setdefault('history', {}).setdefault(key, [])
            hist.append({'bands': bands, 'preamp_db': preamp_db})
            if len(hist) > 20:
                del hist[:-20]
            self._save()
            return list(hist)

    def pop_history(self, preset_id):
        """返回上一个应用前快照；无历史返回 None。"""
        with self._lock:
            key = str(preset_id)
            hist = self._state.setdefault('history', {}).get(key, [])
            if not hist:
                return None
            prev = hist.pop()
            self._save()
            return prev

    def new_snapshot_id(self):
        return uuid.uuid4().hex[:12]


if __name__ == '__main__':
    s = StateStore(path=os.path.join(os.environ.get('TEMP', '.'), 'mixer-state-test.json'))
    s.set_applied('dt900prox-harman', [], 0)
    print(s.get_applied('dt900prox-harman'))