# -*- coding: utf-8 -*-
"""生成“预设 ID 与文件路径对照.md”。

运行方式（在 peq-webui 目录下）：
    py tools/generate_preset_mapping.py

脚本会读取 apo-presets/presets.json，按“预设 ID = 文件名去掉 .txt”的规则
生成/更新根目录下的《预设ID与文件路径对照.md》。
"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRESETS_JSON = PROJECT_ROOT / 'apo-presets' / 'presets.json'
OUTPUT_MD = PROJECT_ROOT / '预设ID与文件路径对照.md'


def load_presets():
    if not PRESETS_JSON.exists():
        raise FileNotFoundError(f'未找到 {PRESETS_JSON}')
    with PRESETS_JSON.open('r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError('presets.json 格式不是数组')
    return data


def build_markdown(presets):
    lines = []
    lines.append('# 预设 ID 与文件路径对照表')
    lines.append('')
    lines.append('> 本文件由 `tools/generate_preset_mapping.py` 自动生成，请勿手写维护。')
    lines.append('> 用于确认 WebUI 中预设 ID 对应的实际文件名和文件地址。')
    lines.append('> 你不需要手动管理这些文件；后端会按此规则读写。')
    lines.append('')
    lines.append('## 对应规则')
    lines.append('')
    lines.append('- 预设 ID = 文件名去掉 `.txt` 后缀')
    lines.append('- 预设文件默认目录：`apo-presets/`')
    lines.append('- 例如 ID `e40` 对应文件 `apo-presets/e40.txt`')
    lines.append('- 重命名 WebUI 中的标题只修改文件内的 `# name:` 字段，不会改变预设 ID/文件名')
    lines.append('')
    lines.append('## 当前预设列表')
    lines.append('')
    lines.append('| 预设 ID | 显示名称 | 文件名 | 相对路径 | 绝对路径 |')
    lines.append('|---|---|---|---|---|')
    for p in presets:
        pid = p.get('id', '')
        name = p.get('name') or ''
        filename = pid + '.txt'
        rel = 'apo-presets/' + filename
        absolute = (PROJECT_ROOT / 'apo-presets' / filename).as_posix()
        name_esc = name.replace('|', '\\|')
        lines.append(f'| {pid} | {name_esc} | {filename} | `{rel}` | `{absolute}` |')
    lines.append('')
    lines.append('## 文件存在性检查')
    lines.append('')
    all_ok = True
    for p in presets:
        pid = p.get('id', '')
        path = PROJECT_ROOT / 'apo-presets' / (pid + '.txt')
        if not path.exists():
            all_ok = False
            lines.append(f'- ❌ `{pid}` -> 缺少文件 `{path}`')
    if all_ok:
        lines.append('- ✅ 所有预设 ID 都能对应到实际文件。')
    lines.append('')
    return '\n'.join(lines)


def main():
    presets = load_presets()
    md = build_markdown(presets)
    OUTPUT_MD.write_text(md, encoding='utf-8')
    print(f'已更新: {OUTPUT_MD}')
    print(f'预设数量: {len(presets)}')


if __name__ == '__main__':
    main()
