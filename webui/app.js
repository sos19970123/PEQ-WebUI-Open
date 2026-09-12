'use strict';

/* =========================================================================
 * PEQ WebUI 璺?EqualizerAPO 閸撳秶
    toast('APO 配置已接管', 'success');
 * ====================================================================== */

/* ---------- helpers ---------- */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function clamp(v, min, max) {
  return Math.min(max, Math.max(min, v));
}

function clone(v) {
  return JSON.parse(JSON.stringify(v));
}

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
/* ---------- help manual（已迁移到 webui/manual.js 全新实现） ---------- */
function openHelpManual() {
  if (window.PeqManual && typeof window.PeqManual.open === 'function') {
    window.PeqManual.open();
  }
}

function toast(msg, type = 'info', timeout = 3500) {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  $('#toast-container').appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity .3s';
    setTimeout(() => el.remove(), 350);
  }, timeout);
}

/* ---------- API wrapper ---------- */
async function api(path, options = {}) {
  const opts = { method: options.method || 'GET', headers: {}, ...options };
  if (opts.body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(opts.body);
  }
  try {
    let resp;
    try {
      resp = await fetch(path, opts);
    } catch (e) {
      throw new Error('网络连接失败: ' + (e.message));
    }
    let data = null;
    try {
      data = await resp.json();
    } catch (_) {
      throw new Error('响应不是 JSON(HTTP ' + (resp.status) + ')');
    }
    if (data && data.ok === false) {
      const err = new Error(data.error || '请求失败');
      err.business = true;
      throw err;
    }
    return data;
  } catch (e) {
    throw e;
  }
}

/* ---------- band / curve normalization ---------- */
const BAND_TYPE_MAP = {
  PK: 'peaking',
  LS: 'low_shelf',
  HS: 'high_shelf',
  LP: 'low_pass',
  HP: 'high_pass'
};
const TYPE_TO_SHORT = {
  peaking: 'PK',
  low_shelf: 'LS',
  high_shelf: 'HS',
  low_pass: 'LP',
  high_pass: 'HP'
};
const TYPE_OPTIONS = ['PK', 'LS', 'HS', 'LP', 'HP'];

const BAND_ZONES = [
  {
    id: 'sub-bass',
    en: 'Sub Bass',
    cn: '极低频',
    min: 20,
    max: 100,
    color: '#ffa43d',
    bg: 'rgba(255,164,61,0.10)',
    instruments: '底鼓 / 大鼓 / 贝斯 / 管风琴 / 合成器Bass',
    tip: '低频下潜。提升可增加冲击力、氛围和身体感；过量容易浑浊、轰头，建议用小增益宽 Q（LS/PK）微调。'
  },
  {
    id: 'mid-bass',
    en: 'Mid Bass',
    cn: '低频',
    min: 100,
    max: 250,
    color: '#ffb45e',
    bg: 'rgba(255,180,94,0.10)',
    instruments: '男声低音 / 大提琴 / 贝斯 / 钢琴低音 / 鼓腔',
    tip: '人声厚度。提升让声音更温暖厚实，过量会发闷/轰头；觉得人声薄可在此 +1~3dB，Q 0.7~1.2。'
  },
  {
    id: 'low-mid',
    en: 'Low Mids',
    cn: '中低频',
    min: 250,
    max: 600,
    color: '#5aa9ff',
    bg: 'rgba(90,169,255,0.10)',
    instruments: '人声胸腔 / 木吉他 / 钢琴中低音 / 大提琴 / 军鼓',
    tip: '人声与器乐饱满度。降低可提高清晰度，但降太多人声会发虚、缺少力度；想增加饱满度可在此微增。'
  },
  {
    id: 'mid',
    en: 'Mids',
    cn: '中频',
    min: 600,
    max: 1000,
    color: '#4c9aff',
    bg: 'rgba(76,154,255,0.12)',
    instruments: '人声 / 中提琴 / 萨克斯 / 电吉他 / 钢琴中音 / 军鼓',
    tip: '人声主体频段。少了人声有点虚，多了会出“收音机声”，不建议大幅调整；如确有鼻音/盒感可在中频窄 Q 衰减。'
  },
  {
    id: 'high-mid',
    en: 'High Mids',
    cn: '中高频',
    min: 1000,
    max: 2000,
    color: '#6db3ff',
    bg: 'rgba(109,179,255,0.10)',
    instruments: '人声 / 小提琴 / 长笛 / 吉他 / 钢琴高音 / 镲片',
    tip: '清晰度、声场。提升让人声更近、有头中效应；少了人声远、虚、塑料感。调整时从 ±1~2dB 开始。'
  },
  {
    id: 'presence',
    en: 'Presence',
    cn: '高频',
    min: 2000,
    max: 5000,
    color: '#b57bff',
    bg: 'rgba(181,123,255,0.10)',
    instruments: '小提琴 / 木管 / 铜管 / 吉他泛音 / 人声辅音 / 镲片',
    tip: '器乐清晰度/锐利感。多了高频碎、毛刺感；少了缺律动但更柔和。人声“近/亮”也主要看此段。'
  },
  {
    id: 'brilliance',
    en: 'Brilliance',
    cn: '高频',
    min: 5000,
    max: 10000,
    color: '#c99bff',
    bg: 'rgba(201,155,255,0.10)',
    instruments: '镲片 / 三角铁 / 沙锤 / 打击乐泛音 / 人声齿音',
    tip: '清晰度、齿音。提升更亮、更多空气细节；过量齿音（s/t）刺耳。齿音重可在此段窄 Q 衰减。'
  },
  {
    id: 'ultra-high',
    en: 'Ultra High',
    cn: '极高频',
    min: 10000,
    max: 20000,
    color: '#e0c3ff',
    bg: 'rgba(224,195,255,0.10)',
    instruments: '镲片泛音 / 三角铁 / 空气声 / 弦乐泛音 / 金属打击乐',
    tip: '泛音、空气感、通透度。提升更开放、通透、明亮；过量金属声、刺耳。因人耳差异大，建议小幅试听。'
  }
];


function normalizeBandType(t) {
  if (t == null) return 'PK';
  const up = String(t).toUpperCase();
  if (BAND_TYPE_MAP[up]) return up;
  if (TYPE_TO_SHORT[String(t).toLowerCase()]) return TYPE_TO_SHORT[String(t).toLowerCase()];
  return up;
}

function normalizeBand(b) {
  if (!b || typeof b !== 'object') return null;
  return {
    type: normalizeBandType(b.type || b.kind || 'PK'),
    freq: clamp(Number(b.freq ?? b.frequency ?? b.fc ?? 1000) || 1000, 20, 20000),
    gain: clamp(Number(b.gain ?? b.gain_db ?? b.db ?? 0) || 0, -15, 15),
    q: clamp(Number(b.q ?? b.Q ?? 1) || 1, 0.1, 10),
    enabled: b.enabled !== false
  };
}

function normalizeBands(bands) {
  if (!Array.isArray(bands)) return [];
  return bands.map(normalizeBand).filter(Boolean);
}

function normalizePoints(points) {
  if (!Array.isArray(points)) return [];
  return points.map((p) => {
    if (Array.isArray(p)) return { freq: Number(p[0]), db: Number(p[1]) };
    if (p && typeof p === 'object') {
      return { freq: Number(p.freq ?? p.frequency ?? p[0]), db: Number(p.db ?? p.dB ?? p.gain ?? p[1]) };
    }
    return null;
  }).filter(p => p && isFinite(p.freq) && isFinite(p.db));
}

function deviceId(d) {
  return typeof d === 'string' ? d : (d && (d.id || d.device_id)) || '';
}
function deviceName(d) {
  return typeof d === 'string' ? d : (d && (d.name || d.device_name)) || '';
}
function targetId(t) {
  return typeof t === 'string' ? t : (t && (t.id || t.name)) || '';
}
function targetName(t) {
  return typeof t === 'string' ? t : (t && (t.name || t.title || t.id)) || '';
}
function targetCategory(t) {
  if (!t) return 'common';
  if (t.category || t.target_category) return t.category || t.target_category;
  if (String(t.source || '').toLowerCase() === 'imported') return 'headphone';
  return 'common';
}

/* ---------- device variants 璺?measurement rig policy ----------
 * 閸氬奔绔撮崣鎷屾径鍥ф躬 curves/devices/ 娑撳褰查張澶婃稉澧楅張绱欐稉宥呮倱濞村鍣?rig閿涘绱?
 * 閸忓啯鏆熼幑鐡у▓纰夌窗variant閿涘牊鏆熼幑绨敍澶堚偓涔篿g / rig_family / rig_standard / rig_note / url / default閵?
 * 娑撳濯哄鍡涒偓澶愩€嶉敍姘虫径鍥ф倳 + 閺佺増宓佸┃?+ rig 閻垼缁涙拝绱眛itle 閹癁閺勫墽銇氱€瑰本鏆ｇ粵鏍殣鐠囧瓨妲戦妴?
 */
function deviceVariant(d) {
  return (d && (d.variant || d.source)) || '';
}
function deviceRig(d) {
  return (d && (d.rig || '')) || '';
}
function deviceIsDefault(d) {
  return !!(d && d.default);
}
function deviceOptionLabel(d) {
  const name = deviceName(d) || deviceId(d);
  const v = deviceVariant(d);
  const rig = deviceRig(d);
  let label = name;
  if (v || rig) label += ' · ' + [v, rig].filter(Boolean).join(' / ');
  if (deviceIsDefault(d)) label += ' ★默认';
  return label;
}
function deviceTooltip(d) {
  if (!d) return '';
  const lines = [];
  lines.push((deviceName(d) || deviceId(d)) + '版本: ' + (deviceVariant(d) || deviceId(d)));
  if (d.rig) lines.push(`Rig: ${d.rig}${d.rig_family ? ` (${d.rig_family})` : ''}`);
  if (d.rig_standard) lines.push('标准: ' + (d.rig_standard));
  if (d.rig_note) lines.push('说明: ' + (d.rig_note));
  if (d.url) lines.push('链接: ' + (d.url));
  if (deviceIsDefault(d)) lines.push('★ 默认版本（oratory1990/AutoEq 校准基准）');
    return lines.join('\n');
}
function groupDevices(devices) {
  // 閹稿婢跺洤鐔€绾偓閸氬秴鍨庣紒鍕剁礄閸氬奔绔撮悧鈺冩倞鐠佹儳閻ㄥ嫬娑撶ゴ闁插繒澧楅張鏂侀崥灞肩缂佸嫸绱氶敍宀€绮嶉崘鍛寸帛鐠併倗澧楅張婀崜?
  const map = new Map();
  for (const d of devices || []) {
    const base = deviceName(d) || deviceId(d);
    if (!map.has(base)) map.set(base, []);
    map.get(base).push(d);
  }
  for (const list of map.values()) {
    list.sort((a, b) => (deviceIsDefault(b) - deviceIsDefault(a)) || deviceId(a).localeCompare(deviceId(b)));
  }
  return Array.from(map.entries());
}
function rigFamilyKeyFrom(...values) {
  const low = values
    .filter((v) => v !== undefined && v !== null && String(v) !== '')
    .map((v) => String(v))
    .join(' ')
    .toLowerCase();
  if (!low) return '';
  if (low.includes('45bc') || low.includes('43ag') || low.includes('43ac')
      || low.includes('oratory1990') || low.includes('kearm')) return 'oratory';
  if (low.includes('5128')) return '5128';
  if (low.includes('hms') || low.includes('ii.3')) return 'hms';
  if (low.includes('711') || low.includes('60318')) return '711';
  if (low.includes('ears')) return 'ears';
  if (low.includes('diffuse')) return 'diffuse';
  // 目标曲线常只写 “Harman 2018” 而没有 rig 字段：Harman 基准与 oratory/GRAS 同源。
  if (low.includes('harman')) return 'oratory';
  return '';
}
function curveRig(c) {
  return (c && (c.rig || c.measurement_rig)) || '';
}
function deviceRigFamilyKey(d) {
  return rigFamilyKeyFrom(d && d.rig_family, d && d.rig, d && d.source, d && d.variant);
}
function targetRigFamilyKey(name) {
  return rigFamilyKeyFrom(name);
}
function curveRigFamilyKey(c) {
  return rigFamilyKeyFrom(
    c && c.rig_family, c && c.rig, c && c.measurement_rig,
    c && c.source, c && c.variant, c && c.measurement_source,
    c && c.name, c && c.id
  );
}
function currentFitCurves() {
  const p = currentPreset();
  const dev = state.deviceCurve
    || (p ? state.devices.find((x) => deviceId(x) === p.device_id) : null)
    || null;
  const tgt = state.targetCurve
    || state.targets.find((x) => targetId(x) === state.targetCurveId)
    || null;
  return { dev, tgt };
}
function isCrossRigFit() {
  const { dev, tgt } = currentFitCurves();
  const devFam = dev ? deviceRigFamilyKey(dev) : '';
  const tgtFam = tgt ? curveRigFamilyKey(tgt) : '';
  const known = !!(dev && curveRig(dev) && tgt && curveRig(tgt));
  return !!(known && devFam && tgtFam && devFam !== tgtFam);
}
function isTrust9kPlusVerified() {
  const { dev, tgt } = currentFitCurves();
  const devFam = dev ? deviceRigFamilyKey(dev) : '';
  const tgtFam = tgt ? curveRigFamilyKey(tgt) : '';
  return !!(dev && tgt && curveRig(dev) && curveRig(tgt) && devFam && tgtFam && devFam === tgtFam);
}
function updateRigWarning() {
  const el = $('#rig-warn');
  if (!el) return;
  const { dev, tgt } = currentFitCurves();
  const devRig = dev ? curveRig(dev) : '';
  const tgtRig = tgt ? curveRig(tgt) : '';
  const devFam = dev ? deviceRigFamilyKey(dev) : '';
  const tgtFam = tgt ? curveRigFamilyKey(tgt) : '';
  let text = '';
  if (dev && devRig) {
    if (tgt && tgtRig) {
      if (devFam && tgtFam && devFam !== tgtFam) {
        text = '跨 rig 拟合：设备 ' + devRig + '（' + devFam + '），目标 ' + tgtRig + '（' + tgtFam + '）。'
          + '9kHz 以上差异可能属测量系统而非耳机；拟合会自动把 fmax 收敛到 7000Hz'
          + '（可勾选“允许跨 rig 高频”覆盖）。';
      } else if (devFam && tgtFam) {
        text = '设备频响: ' + deviceOptionLabel(dev) + '（rig ' + devRig + '）；'
          + '目标 rig ' + tgtRig + '，属于同一测量系统，高频可参考。';
      } else if (devRig !== tgtRig) {
        text = '设备 rig ' + devRig + ' 与目标 rig ' + tgtRig + ' 不同且无法归类，'
          + '无法判断可比性，9kHz 以上结果不可验证；建议 fmax ≤ 7000Hz。';
      } else {
        text = '设备频响: ' + deviceOptionLabel(dev) + '（rig ' + devRig + '）';
      }
    } else if (tgt) {
      text = '目标 rig 未知；设备 rig ' + devRig + '。无法判断可比性，9kHz 以上结果不可验证。';
    } else {
      text = '设备频响: ' + deviceOptionLabel(dev) + '（rig ' + devRig + '）';
    }
  } else if (tgt && tgtRig) {
    text = '目标 rig ' + tgtRig + '；设备 rig 未知，无法判断可比性，9kHz 以上结果不可验证。';
  }
  el.textContent = text;
  el.classList.toggle('hidden', !text);
  updateDeRigAvailability();
}

function updateDeRigAvailability() {
  const cb = $('#de-rig');
  if (!cb) return;
  const label = $('#de-rig-label');
  const { dev, tgt } = currentFitCurves();
  let candidate = null;
  if (dev && tgt) {
    const baseName = deviceName(dev);
    const devFam = deviceRigFamilyKey(dev);
    const tgtFam = curveRigFamilyKey(tgt);
    if (baseName && devFam && tgtFam && devFam !== tgtFam) {
      candidate = state.devices.find((x) =>
        deviceName(x) === baseName && curveRig(x) && rigFamilyKeyFrom(x.rig, x.rig_family) === tgtFam
      ) || null;
    }
  }
  cb.disabled = !candidate;
  if (!candidate) cb.checked = false;
  if (label) {
    label.classList.toggle('muted', !candidate);
    label.title = candidate
      ? '可用：' + deviceName(candidate) + ' / ' + curveRig(candidate) + '；将把目标曲线换算到设备 rig 口径后再拟合'
      : '需要同型号耳机在两个 rig 下的实测数据（导入多测量版本后自动可用）';
  }
}

function renderDeviceCurveInfo() {
  const el = $('#device-curve-info');
  if (!el) return;
  const c = state.deviceCurve;
  if (!c) { el.textContent = ''; el.title = ''; return; }
  const v = c.variant || c.source || '';
  const rig = c.rig || '';
  const parts = [v, rig].filter(Boolean).join(' / ');
  el.textContent = (c.name || '') + (parts ? ` · ${parts}` : '');
  const lines = [];
  if (rig) lines.push(`Rig: ${rig}${c.rig_family ? ` (${c.rig_family})` : ''}`);
  if (c.rig_standard) lines.push('标准: ' + (c.rig_standard));
  if (c.rig_note) lines.push('说明: ' + (c.rig_note));
  if (c.url) lines.push('链接: ' + (c.url));
  if (c.alignment && c.alignment.enabled) {
    lines.push(`对齐: ${c.alignment.method} ${c.alignment.ref_low}-${c.alignment.ref_high}Hz offset ${c.alignment.offset_db}dB`);
  }
  el.title = lines.join('\n');
}

/* =========================================================================
 * State
 * ====================================================================== */
const state = {
  online: false,
  apoInfo: {},
  activeOriginal: false,
  presets: [],
  presetOrder: [],
  currentPresetId: null,
  appliedBands: [],
  draftBands: [],
  appliedPreamp: 0,
  draftPreamp: 0,
  devices: [],
  targets: [],
  deviceCurve: null,
  targetCurve: null,
  targetCurveId: '',
  previewBands: null,
  previewPreamp: 0,
  previewLabel: '',
  dirty: false,
  notes: '',
manualBandIndex: 0,
autoFitEnabled: false,
  draftFitSettings: null,
  previewFitSettings: null,
  deviceCurveCache: {},
  targetCurveCache: {},
  sseActive: false,
  activeBandZone: null,
};
let liveApplyTimer = null;
let presetOrderSaveSeq = 0;


/* ---------- dirty ---------- */
function isDirty() {
  return !deepEqual(state.draftBands, state.appliedBands) || Math.abs(state.draftPreamp - state.appliedPreamp) > 0.001;
}

function setDirty(dirty) {
  state.dirty = dirty;
  $('#dirty-indicator').classList.toggle('hidden', !dirty);
  updateControls();
}

function updateControls() {
  const on = state.online;
  const hasPreset = state.currentPresetId != null;
  const canEdit = on && hasPreset;
  $('#btn-apply').disabled = !canEdit || !state.dirty;
  $('#btn-discard').disabled = !canEdit || !state.dirty;
  $('#btn-revert').disabled = !canEdit;
  $('#device-select').disabled = !canEdit;
  $('#btn-import-curve').disabled = !on;
  $('#btn-add-band').disabled = !canEdit || state.draftBands.length >= 20;
  $('#btn-parse').disabled = !canEdit;
  $('#btn-adopt-import').disabled = !canEdit || !state.previewBands || state.previewBands.length === 0;
  $('#btn-autofit').disabled = !canEdit;
  $('#btn-adopt-autofit').disabled = !canEdit || !state.previewBands || state.previewBands.length === 0;
  $('#btn-preset-add').disabled = !on;
  const origSwitch = $('#original-switch');
  if (origSwitch) origSwitch.disabled = !canEdit;
  const notesText = $('#notes-text');
  if (notesText) notesText.disabled = !canEdit;
  const saveNotesBtn = $('#btn-save-notes');
  if (saveNotesBtn) saveNotesBtn.disabled = !canEdit;
  const exportConfigBtn = $('#btn-export-config');
  if (exportConfigBtn) exportConfigBtn.disabled = !canEdit;
  const restartBtn = $('#btn-service-restart');
  const stopBtn = $('#btn-service-stop');
  if (restartBtn) restartBtn.disabled = !on;
  if (stopBtn) stopBtn.disabled = !on;
}

/* =========================================================================
 * Loading data
 * ====================================================================== */
async function loadStatus() {
  try {
    const data = await api('/api/status');
    state.online = !!data.online;
    state.apoInfo = data.apo || {};
    state.activeOriginal = !!(state.apoInfo.active_original);
    const dot = $('#status-dot');
    $('#status-text').textContent = state.online ? '在线' : '离线';
    $('#status-text').textContent = state.online ? '在线' : '离线';
    renderApoBadges();
    updateControls();
  } catch (e) {
    state.online = false;
    state.apoInfo = {};
    state.activeOriginal = false;
    $('#status-text').textContent = '离线';
    $('#status-text').textContent = '离线';
    renderApoBadges();
    updateControls();
  }
}

function renderApoBadges() {
  const wrap = $('#apo-badges');
  const info = state.apoInfo || {};
  const parts = [];
  let cls = 'badge ' + (info.installed ? 'ok' : 'warn');
  parts.push('<span class="' + cls + '">APO ' + (info.installed ? '已安装' : '未安装') + '</span>');
  cls = 'badge ' + (info.managed ? 'ok' : 'warn');
  parts.push('<span class="' + cls + '">' + (info.managed ? '配置已托管' : '未接管') + '</span>');
  cls = 'badge ' + (info.mounted_fiio ? 'ok' : 'warn');
  parts.push('<span class="' + cls + '">FiiO ' + (info.mounted_fiio ? '已挂载' : '未检测到挂载') + '</span>');
  const isElevated = !!info.elevated;
  parts.push('<span class="badge ' + (isElevated ? 'ok' : 'warn') + '">' + (isElevated ? '管理员模式' : '普通模式') + '</span>');
  if (info.active_preset_id) {
    const origTag = info.active_original ? ' · 原声' : '';
    parts.push('<span class="badge ok">当前: ' + escapeHtml(info.active_preset_name || info.active_preset_id) + origTag + '</span>');
  } else {
    parts.push('<span class="badge">当前: 直通</span>');
  }
  const restartBtn = $('#btn-restart-admin');
  if (restartBtn) restartBtn.disabled = isElevated;
  wrap.innerHTML = parts.join('');
}

async function loadPresets(selectId = state.currentPresetId) {
  const data = await api('/api/presets');
  state.presets = Array.isArray(data.presets) ? data.presets : [];
  state.presetOrder = Array.isArray(data.order) ? data.order : state.presetOrder;
  if (data.active_preset_id) {
    const active = state.presets.find(p => p.id === data.active_preset_id);
    if (active) active.active = true;
  }
  renderPresets();
  if (selectId && state.presets.some(p => p.id === selectId)) {
    state.currentPresetId = selectId;
  } else if (data.active_preset_id && state.presets.some(p => p.id === data.active_preset_id)) {
    state.currentPresetId = data.active_preset_id;
  } else if (state.presets.length) {
    state.currentPresetId = state.presets[0].id;
  } else {
    state.currentPresetId = null;
  }
  updateControls();
}

async function loadDevices() {
  const data = await api('/api/devices');
  state.devices = Array.isArray(data) ? data : (data.devices || []);
  renderDeviceSelect();
  renderNewPresetDeviceSelect();
  updateRigWarning();
}

async function loadTargets() {
  const data = await api('/api/targets');
  state.targets = Array.isArray(data) ? data : (data.targets || []);
  renderTargetSelect();
  renderTargetSelectMain();
  updateRigWarning();
}

function currentPreset() {
  return state.presets.find(p => p.id === state.currentPresetId) || null;
}

async function loadPresetData(presetId, opts = {}) {
  if (presetId == null) {
    state.currentPresetId = null;
    state.appliedBands = [];
    state.draftBands = [];
    state.appliedPreamp = 0;
    state.draftPreamp = 0;
    state.previewBands = null;
    state.previewPreamp = 0;
    state.previewLabel = '';
    state.notes = '';
    const notesInput = $('#notes-text');
    if (notesInput) notesInput.value = '';
    const configPre = $('#config-text');
  if (configPre) configPre.textContent = '请选择预设后查看';
    setDirty(false);
    renderAllLocal();
    return;
  }
  try {
    const [bandsData, configData] = await Promise.all([
      api(`/api/eq/bands?preset=${encodeURIComponent(presetId)}`),
      api(`/api/preset/config?id=${encodeURIComponent(presetId)}`)
    ]);
    state.appliedBands = normalizeBands(bandsData.applied || bandsData.bands || []);
    state.appliedPreamp = Number(bandsData.preamp_db ?? bandsData.preamp ?? 0) || 0;
      applyFitSettings(bandsData.fit || {});
    state.draftFitSettings = bandsData.fit || null;
    if (!opts.keepDraft) {
      state.draftBands = clone(state.appliedBands);
      state.draftPreamp = state.appliedPreamp;
      state.previewBands = null;
      state.previewPreamp = 0;
      state.previewLabel = '';
    }
    state.notes = configData.notes || '';
    const notesInput = $('#notes-text');
    if (notesInput) notesInput.value = state.notes;
    $('#config-text').textContent = configData.config_text || '（空预设）';
      const preset = state.presets.find(p => p.id === presetId);
      const deviceIdVal = preset ? (preset.device_id || '') : (configData.device_id || '');
      await loadDeviceCurve(deviceIdVal);
      const presetTargetId = preset ? (preset.target_id || '') : (configData.target_id || '');
      await loadTargetCurve(presetTargetId || defaultTargetId(deviceIdVal));
    
    // 鎭㈠UI鐘舵€?
    const uiState = (preset && preset.ui_state) || configData.ui_state || {};
    if (uiState.legend) {
      const legend = uiState.legend;
      if ($('#legend-device')) $('#legend-device').checked = !!legend.device;
      if ($('#legend-target')) $('#legend-target').checked = !!legend.target;
      if ($('#legend-eq')) $('#legend-eq').checked = !!legend.eq;
      if ($('#legend-equalized')) $('#legend-equalized').checked = !!legend.equalized;
      if ($('#legend-applied')) $('#legend-applied').checked = !!legend.applied;
      if ($('#legend-draft')) $('#legend-draft').checked = !!legend.draft;
      if ($('#legend-preview')) $('#legend-preview').checked = !!legend.preview;
    }
    if ($('#auto-fit-switch')) {
      state.autoFitEnabled = !!uiState.auto_fit_enabled;
      $('#auto-fit-switch').checked = state.autoFitEnabled;
    }
    
    setDirty(isDirty());
    renderAllLocal();
    await refreshConfigPreview();
  } catch (e) {
    toast("读取预设失败: ${e.message}", 'error');
  }
}

async function onOriginalSwitch(checked) {
  if (!state.online || state.currentPresetId == null) return;
  try {
    await api('/api/preset/activate', {
      method: 'POST',
      body: { id: state.currentPresetId, original: !!checked }
    });
    await loadStatus();
    await loadPresets(state.currentPresetId);
    renderAllLocal();
    await refreshConfigPreview();
  toast(checked ? '已切换原声通道（无 EQ，Preamp 与 EQ 一致）' : '已切换 EQ 通道', 'success', 1500);
  } catch (e) {
    await loadStatus();
    renderAllLocal();
  toast("原声/EQ 切换失败: ${e.message}", 'error');
  }
}

async function saveNotes() {
  if (!state.online || state.currentPresetId == null) return;
  const statusEl = $('#notes-status');
  if (statusEl) statusEl.textContent = '保存中…';
  try {
    const notes = $('#notes-text').value || '';
    await api('/api/preset/notes', {
      method: 'PUT',
      body: { id: state.currentPresetId, notes }
    });
    state.notes = notes;
    if (statusEl) {
      statusEl.textContent = '已保存';
      setTimeout(() => { if (statusEl.textContent === '已保存') statusEl.textContent = ''; }, 2000);
    }
    toast('听感记录已保存到预设', 'success');
    } catch (e) {
    if (statusEl) statusEl.textContent = '保存失败';
    toast('听感记录保存失败: ' + e.message, 'error');
  }
}

async function syncExportConfig() {
  if (!state.online || state.currentPresetId == null) return;
  const showOriginal = !!(state.activeOriginal && state.apoInfo.active_preset_id === state.currentPresetId);
  try {
    const data = await api(`/api/preset/config?id=${encodeURIComponent(state.currentPresetId)}${showOriginal ? '&original=1' : ''}`);
    toast('已导出当前 APO 配置', 'success', 2000);
    toast('已导出当前 APO 配置', 'success', 2000);
  } catch (e) {
    toast('APO 配置已接管', 'success');
  }
}

function defaultTargetId(deviceIdVal) {
  const dev = state.devices.find(d => deviceId(d) === deviceIdVal);
  const kind = dev && dev.kind ? String(dev.kind).toLowerCase() : '';
  const name = dev ? String(dev.name || '').toLowerCase() : '';
  if (kind.includes('speaker') || name.includes('音箱') || name.includes('speaker')) return 'flat';
  if (kind.includes('iem') || kind.includes('earbud') || kind.includes('in-ear') || kind.includes('earphone') || name.includes('入耳') || name.includes('耳塞'))
  if (kind.includes('headphone') || name.includes('头戴') || name.includes('耳机')) return 'harman_overear_2018';
  const id = String(deviceIdVal || '').toLowerCase();
  if (id.includes('t100') || id.includes('音箱')) return 'flat';
  if (id.includes('fd02') || id.includes('e40') || id.includes('xlm')) return 'harman_in-ear_2019';
  return '';
}

async function loadDeviceCurve(deviceIdVal) {
  if (!deviceIdVal) {
    state.deviceCurve = null;
    $('#no-curve-tip').classList.add('hidden');
$('#legend-equalized').checked = false;
$('#legend-device').checked = false;
    renderDeviceCurveInfo();
    return;
  }
  if (state.deviceCurveCache[deviceIdVal]) {
    state.deviceCurve = state.deviceCurveCache[deviceIdVal];
  } else {
    try {
      const data = await api(`/api/curves/device/${encodeURIComponent(deviceIdVal)}`);
      state.deviceCurve = {
        id: deviceIdVal,
        name: data.name || deviceIdVal,
        kind: data.kind || '',
        source: data.source || '',
        variant: data.variant || '',
        rig: data.rig || data.measurement_rig || '',
        rig_family: data.rig_family || '',
        rig_standard: data.rig_standard || '',
        rig_note: data.rig_note || '',
        measurement_rig: data.measurement_rig || data.rig || '',
        measurement_url: data.measurement_url || data.url || '',
        url: data.url || '',
        default: !!data.default,
        points: normalizePoints(data.points)
      };
      state.deviceCurveCache[deviceIdVal] = state.deviceCurve;
    } catch (e) {
      state.deviceCurve = null;
      state.deviceCurveCache[deviceIdVal] = null;
    }
  }
  const noData = !state.deviceCurve || !state.deviceCurve.points || state.deviceCurve.points.length === 0;
  $('#no-curve-tip').classList.toggle('hidden', !noData);
$('#legend-equalized').checked = !noData;
$('#legend-device').checked = !noData;
  renderDeviceCurveInfo();
  updateRigWarning();
}

async function loadTargetCurve(targetIdVal) {
  state.targetCurveId = targetIdVal || '';
  if (!targetIdVal) {
    state.targetCurve = null;
    renderTargetSelect();
    return;
$('#legend-target').checked = false;
  }
  if (state.targetCurveCache[targetIdVal]) {
    state.targetCurve = state.targetCurveCache[targetIdVal];
  } else {
    try {
      const data = await api(`/api/curves/target/${encodeURIComponent(targetIdVal)}`);
      state.targetCurve = {
        id: targetIdVal,
        name: data.name || targetIdVal,
        kind: data.kind || '',
        category: data.category || '',
        source: data.source || '',
        variant: data.variant || '',
        measurement_source: data.measurement_source || '',
        measured_device: data.measured_device || '',
        rig: data.rig || data.measurement_rig || '',
        rig_family: data.rig_family || '',
        rig_standard: data.rig_standard || '',
        rig_note: data.rig_note || '',
        measurement_rig: data.measurement_rig || data.rig || '',
        measurement_url: data.measurement_url || data.url || '',
        url: data.url || '',
        points: normalizePoints(data.points)
      };
      state.targetCurveCache[targetIdVal] = state.targetCurve;
    } catch (e) {
      state.targetCurve = null;
      state.targetCurveCache[targetIdVal] = null;
    }
  }
$('#legend-target').checked = true;
renderTargetSelectMain();
  renderTargetSelect();
  updateRigWarning();
}

/* ---------- renderers ---------- */
function loadPresetOrder() {
  if (Array.isArray(state.presetOrder) && state.presetOrder.length) {
    return state.presetOrder.slice();
  }
  try {
    return JSON.parse(localStorage.getItem('peq_preset_order') || '[]');
  } catch (_) {
    return [];
  }
}

async function savePresetOrder(order) {
  const seq = ++presetOrderSaveSeq;
  const clean = (order || []).filter(id => state.presets.some(p => p.id === id));
  localStorage.setItem('peq_preset_order', JSON.stringify(clean));
  state.presetOrder = clean.slice();
  try {
    const data = await api('/api/preset/order', { method: 'POST', body: { order: clean } });
    if (seq === presetOrderSaveSeq && data && Array.isArray(data.order)) state.presetOrder = data.order;
  } catch (e) {
    toast('排序保存失败: ' + e.message, 'error');
  }
}

function sortPresets() {
  const order = loadPresetOrder();
  const byId = new Map(state.presets.map(p => [p.id, p]));
  const used = new Set();
  const result = [];
  if (byId.has('pure')) {
    result.push(byId.get('pure'));
    used.add('pure');
  }
  for (const id of order) {
    if (used.has(id) || !byId.has(id)) continue;
    result.push(byId.get(id));
    used.add(id);
  }
  const remaining = state.presets.filter(p => !used.has(p.id));
  remaining.sort((a, b) => {
    const da = String(a.device_id || '');
    const db = String(b.device_id || '');
    if (da !== db) return da.localeCompare(db);
    return String(a.id).localeCompare(String(b.id));
  });
  for (const p of remaining) {
    const dev = String(p.device_id || '');
    let insertAt = -1;
    for (let i = result.length - 1; i >= 0; i--) {
      if (result[i].id === 'pure') continue;
      if (String(result[i].device_id || '') === dev) {
        insertAt = i + 1;
        break;
      }
    }
    if (insertAt === -1) result.push(p);
    else result.splice(insertAt, 0, p);
  }
  return result;
}
function renderPresets() {
  const wrap = $('#preset-cards');
  wrap.innerHTML = '';
  if (!state.presets.length) {
    const div = document.createElement('div');
    div.textContent = '预设已删除';
    // [fixed] div.textContent = ''閺嗗倹妫ゆ０鍕敍宀冮弬鏉?;
    wrap.appendChild(div);
    return;
  }
    for (const p of sortPresets()) {
    const card = document.createElement('div');
    card.className = 'preset-card' + (p.active ? ' active' : '') + (p.id === state.currentPresetId ? ' current' : '');
    card.dataset.id = p.id;
card.draggable = p.id !== 'pure';
    card.addEventListener('dragstart', (e) => {
      if (p.id === 'pure') return;
      e.dataTransfer.setData('text/plain', p.id);
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => card.classList.remove('dragging'));
    card.addEventListener('dragover', (e) => {
      if (p.id !== 'pure' && state.presets.length > 1) {
        e.preventDefault();
        card.classList.add('drag-over');
      }
    });
    card.addEventListener('dragleave', () => card.classList.remove('drag-over'));
    card.addEventListener('drop', async (e) => {
      e.preventDefault();
      card.classList.remove('drag-over');
      const dragId = e.dataTransfer.getData('text/plain');
      if (!dragId || dragId === p.id || dragId === 'pure' || p.id === 'pure') return;
      const order = loadPresetOrder().filter(id => id !== dragId);
      const idx = order.indexOf(p.id);
      if (idx === -1) order.push(dragId);
      else order.splice(idx, 0, dragId);
      await savePresetOrder(order);
      renderPresets();
    });

    const name = document.createElement('div');
    name.className = 'preset-name';
    name.textContent = p.name || p.id;

    const dev = document.createElement('div');
    dev.className = 'preset-device';
      if (p.device_id) {
        const devObj = state.devices.find(x => deviceId(x) === p.device_id);
        if (devObj) {
          dev.textContent = '频响: ' + deviceOptionLabel(devObj);
          dev.title = deviceTooltip(devObj);
        } else {
          dev.textContent = '设备: ' + (p.device_name || p.device_id);
        }
      } else {
        dev.textContent = '无设备';
      }
const targetDiv = document.createElement('div');
    targetDiv.className = 'preset-target';
    const targetObj = state.targets.find(t => targetId(t) === p.target_id);
    targetDiv.textContent = targetObj ? '目标: ' + targetName(targetObj) : '无目标曲线';

    const meta = document.createElement('div');
    meta.className = 'preset-meta';
    meta.textContent = (p.band_count ?? 0) + ' 段' + (p.active ? ' · 激活' : '');
    // [fixed] meta.textContent = (p.band_count ?? 0) + ' 濞?璺?' + (p.active ? '濠碘偓濞茶鑵? + origActive 

    card.appendChild(name);
    card.appendChild(dev);
card.appendChild(targetDiv);
    card.appendChild(meta);
    const renameBtn = document.createElement('button');
    renameBtn.className = 'preset-rename';
    renameBtn.title = '重命名';
    renameBtn.textContent = '✎';
    renameBtn.addEventListener('click', (ev) => {
      ev.stopPropagation();
      onRenamePreset(p.id);
    });
    card.appendChild(renameBtn);

    const close = document.createElement('button');
    close.className = 'preset-close';
    close.title = '删除';
    close.textContent = '✕';
    close.addEventListener('click', (ev) => {
      ev.stopPropagation();
      onDeletePreset(p.id);
    });
    card.appendChild(close);

    card.addEventListener('click', (ev) => { if (ev.detail === 1) switchPreset(p.id, false); });
    card.addEventListener('dblclick', () => switchPreset(p.id, true));
    wrap.appendChild(card);
  }
}

function renderDeviceSelect() {
  const sel = $('#device-select');
  const p = currentPreset();
  const currentDevice = p ? (p.device_id || '') : '';
  sel.innerHTML = '';
  const emptyOpt = document.createElement('option');
    emptyOpt.textContent = '无设备';
  // [fixed] emptyOpt.textContent = ''閺堢拨鐎规俺婢?;
  sel.appendChild(emptyOpt);
  for (const [base, items] of groupDevices(state.devices)) {
    const og = document.createElement('optgroup');
    og.label = base;
    for (const d of items) {
      const opt = document.createElement('option');
      opt.value = deviceId(d);
      opt.textContent = deviceOptionLabel(d);
      opt.title = deviceTooltip(d);
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }
  sel.value = currentDevice;
}

function renderNewPresetDeviceSelect() {
  const sel = $('#new-preset-device');
  sel.innerHTML = '';
  const emptyOpt = document.createElement('option');
    emptyOpt.textContent = '无设备';
  // [fixed] emptyOpt.textContent = ''閺堢拨鐎规俺婢?;
  sel.appendChild(emptyOpt);
  for (const [base, items] of groupDevices(state.devices)) {
    const og = document.createElement('optgroup');
    og.label = base;
    for (const d of items) {
      const opt = document.createElement('option');
      opt.value = deviceId(d);
      opt.textContent = deviceOptionLabel(d);
      opt.title = deviceTooltip(d);
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }
}

function renderTargetSelect() {
  const sel = $('#target-select');
  const cur = state.targetCurveId || '';
  sel.innerHTML = '';
  const emptyOpt = document.createElement('option');
    emptyOpt.textContent = state.targets.length ? '请选择目标曲线' : '无目标曲线';
  // [fixed] emptyOpt.textContent = state.targets.length ? '閺堚偓澶嬪閻╃垼閺囪尙鍤? : '閺嗗倹妫ら惄鐖ｉ弴鑼殠'';
  sel.appendChild(emptyOpt);
  const common = state.targets.filter(t => targetCategory(t) !== 'headphone');
  const headphone = state.targets.filter(t => targetCategory(t) === 'headphone');
  const groups = [
    { label: '── 音频常用目标曲线 ──', items: common },
    { label: '── 耳机目标曲线 ──', items: headphone }
  ];
  for (const group of groups) {
    if (!group.items.length) continue;
    const og = document.createElement('optgroup');
    og.label = group.label;
    for (const t of group.items) {
      const opt = document.createElement('option');
      opt.value = targetId(t);
      opt.textContent = targetOptionLabel(t);
      opt.title = targetTooltip(t) || targetHint(t);
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }
  if (cur && state.targets.some(t => targetId(t) === cur)) {
    sel.value = cur;
  } else {
    state.targetCurveId = '';
    sel.value = '';
  }
}
function renderTargetSelectMain() {
  const sel = $('#target-select-main');
  if (!sel) return;
  const cur = state.targetCurveId || '';
  sel.innerHTML = '';
  const emptyOpt = document.createElement('option');
    emptyOpt.textContent = state.targets.length ? '请选择目标曲线' : '无目标曲线';
  // [fixed] emptyOpt.textContent = state.targets.length ? '閺堚偓澶嬪閻╃垼閺囪尙鍤? : '閺嗗倹妫ら惄鐖ｉ弴鑼殠'';
  sel.appendChild(emptyOpt);
  const common = state.targets.filter(t => targetCategory(t) !== 'headphone');
  const headphone = state.targets.filter(t => targetCategory(t) === 'headphone');
  const groups = [
    { label: '── 音频常用目标曲线 ──', items: common },
    { label: '── 耳机目标曲线 ──', items: headphone }
  ];
  for (const group of groups) {
    if (!group.items.length) continue;
    const og = document.createElement('optgroup');
    og.label = group.label;
    for (const t of group.items) {
      const opt = document.createElement('option');
      opt.value = targetId(t);
      opt.textContent = targetOptionLabel(t);
      opt.title = targetTooltip(t) || targetHint(t);
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }
  sel.value = cur;
}

function targetHint(t) {
  const n = targetName(t);
  const low = String(n || '').toLowerCase();
  let hint = n;
  if (targetCategory(t) === 'headphone') hint += '（耳机目标曲线）';
  if (low.includes('5128')) hint += '\nRig: B&K 5128 HATS';
  if (low.includes('hms') || low.includes('ii.3')) hint += '\nRig: HEAD acoustics HMS II.3 HATS';
  if (low.includes('711')) hint += '\nRig: IEC 60318-4 (711)';
  if (low.includes('harman') && !low.includes('5128') && !low.includes('hms')) hint += '\n目标 rig: oratory1990/GRAS Harman 校准';
  return hint;
}

/* AutoEq 鐎电厧鍙嗛惃鍕锤缁惧尅绱欑拋鎯?閻╃垼閿涘鎯＄敮锔界ゴ闁插繗缂冧繆閹窗measured_device / measurement_source /
 * variant / rig / rig_family / rig_standard / rig_note / url閵嗗倻娲伴弽鍥ㄦ锤缁惧じ绗呴幏澶嬮幑鐏炴洜銇氬ù瀣槸鐠佹儳娣団剝浼呴妴?*/
function targetOptionLabel(t) {
  if (!t) return '';
  const base = targetName(t) || targetId(t);
  const meta = [t.variant || t.measurement_source || '', t.rig || ''].filter(Boolean).join(' / ');
  return meta ? (base + ' · ' + meta) : base;
}
function targetTooltip(t) {
  if (!t) return '';
  const lines = [];
  lines.push((targetName(t) || targetId(t)) + '（' + (targetCategory(t) === 'headphone' ? '耳机目标曲线' : '音频常用目标') + '）');
  if (t.measured_device) lines.push('被测设备: ' + t.measured_device);
  const src = t.measurement_source || t.variant || t.source || '';
  if (src) lines.push('测量来源: ' + src);
  const rig = t.rig || t.measurement_rig || '';
  if (rig) lines.push('Rig: ' + rig + (t.rig_family ? '（' + t.rig_family + '）' : ''));
  if (t.rig_standard) lines.push('标准: ' + (t.rig_standard));
  if (t.rig_note) lines.push('说明: ' + (t.rig_note));
  const url = t.measurement_url || t.url || '';
  if (url) lines.push('链接: ' + url);
  return lines.join('\n');
}

function renderBands() {
  const tbody = $('#band-tbody');
  tbody.innerHTML = '';
  if (!state.draftBands.length) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.textContent = '无频段（点击表格可添加）';
    // [fixed] td.textContent = ''閺嗗倹妫ゆ０鎴為敍灞藉讲閹锋牗瀚?濞ｈ濮?鐎电厧鍙?閹风喎鎮?;
    tr.appendChild(td);
    tbody.appendChild(tr);
  } else {
    state.draftBands.forEach((band, idx) => {
      const tr = document.createElement('tr');

      const tdEnable = document.createElement('td');
      const chk = document.createElement('input');
      chk.type = 'checkbox';
      chk.checked = band.enabled;
      chk.dataset.idx = idx;
      chk.addEventListener('change', () => onBandInput(idx, 'enabled', chk.checked));
      tdEnable.appendChild(chk);

      const tdType = document.createElement('td');
      const sel = document.createElement('select');
      for (const t of TYPE_OPTIONS) {
        const opt = document.createElement('option');
        opt.value = t;
        opt.textContent = t;
        sel.appendChild(opt);
      }
      sel.value = band.type;
      sel.addEventListener('change', () => onBandInput(idx, 'type', sel.value));
      tdType.appendChild(sel);

      const tdFreq = document.createElement('td');
      const freqInput = document.createElement('input');
      freqInput.type = 'number';
      freqInput.min = 20;
      freqInput.max = 20000;
      freqInput.step = 1;
      freqInput.value = Math.round(band.freq);
      freqInput.addEventListener('change', () => onBandInput(idx, 'freq', Number(freqInput.value)));
      tdFreq.appendChild(freqInput);

      const tdGain = document.createElement('td');
      const gainInput = document.createElement('input');
      gainInput.type = 'number';
      gainInput.min = -12;
      gainInput.max = 12;
      gainInput.step = 0.1;
      gainInput.value = band.gain;
      gainInput.addEventListener('change', () => onBandInput(idx, 'gain', Number(gainInput.value)));
      tdGain.appendChild(gainInput);

      const tdQ = document.createElement('td');
      const qInput = document.createElement('input');
      qInput.type = 'number';
      qInput.min = 0.1;
      qInput.max = 10;
      qInput.step = 0.01;
      qInput.value = band.q;
      qInput.addEventListener('change', () => onBandInput(idx, 'q', Number(qInput.value)));
      tdQ.appendChild(qInput);

      const tdDel = document.createElement('td');
      const delBtn = document.createElement('button');
      delBtn.className = 'del-band';
      delBtn.textContent = '×';
      delBtn.title = '删除频段';
      // [fixed] delBtn.title = ''閸掔娀娅庢０鎴?;
      delBtn.addEventListener('click', () => onDeleteBand(idx));
      tdDel.appendChild(delBtn);

      tr.appendChild(tdEnable);
      tr.appendChild(tdType);
      tr.appendChild(tdFreq);
      tr.appendChild(tdGain);
      tr.appendChild(tdQ);
      tr.appendChild(tdDel);
      tbody.appendChild(tr);
    });
  }
  $('#preamp-input').value = state.draftPreamp;
    renderManualEq();
updateEqRisk();
}

function renderManualEq() {
  const bandSelect = $('#manual-band-select');
  const typeSelect = $('#manual-type-select');
  const freqSlider = $('#manual-freq-slider');
  const freqInput = $('#manual-freq-input');
  const gainSlider = $('#manual-gain-slider');
  const gainInput = $('#manual-gain-input');
  const qSlider = $('#manual-q-slider');
  const qInput = $('#manual-q-input');

  if (!bandSelect || !typeSelect || !freqSlider) return;

  bandSelect.innerHTML = '';
  if (!state.draftBands.length) {
    bandSelect.innerHTML = '<option value="-1">暂无频段</option>';
    typeSelect.disabled = true;
    freqSlider.disabled = true;
    freqInput.disabled = true;
    gainSlider.disabled = true;
    gainInput.disabled = true;
    qSlider.disabled = true;
    qInput.disabled = true;
    return;
  }

  if (state.manualBandIndex == null || state.manualBandIndex < 0 || state.manualBandIndex >= state.draftBands.length) {
    state.manualBandIndex = 0;
  }
  const idx = state.manualBandIndex;
  const band = state.draftBands[idx];

  state.draftBands.forEach((b, i) => {
    const opt = document.createElement('option');
    opt.value = String(i);
    opt.textContent = `${i + 1}. ${b.type} ${Math.round(b.freq)}Hz ${b.gain >= 0 ? '+' : ''}${b.gain.toFixed(1)}dB Q${b.q.toFixed(2)}";`
    bandSelect.appendChild(opt);
  });
  bandSelect.value = String(idx);

  typeSelect.disabled = false;
  typeSelect.innerHTML = '';
  for (const t of TYPE_OPTIONS) {
    const opt = document.createElement('option');
    opt.value = t;
    opt.textContent = t;
    typeSelect.appendChild(opt);
  }
  typeSelect.value = band.type;

  freqSlider.disabled = false;
  freqInput.disabled = false;
  qSlider.disabled = false;
  qInput.disabled = false;

  // 妫版垹宸奸悽銊ラ弫鐗堢拨閸ф绱?~100 閺勭姴鐨犻崚?20~20000 Hz
  freqSlider.value = freqToSlider(band.freq);
  freqInput.value = Math.round(band.freq);
  qSlider.value = band.q;
  qInput.value = band.q.toFixed(2);

  // APO 閻?LP/HP 濞屸剝婀?Gain 鐎涙閿涘瞼閻劌閻╁﹥绮﹂崸?閺佹澘鐡ф潏鎾冲弳
  const noGain = band.type === 'LP' || band.type === 'HP';
  gainSlider.disabled = noGain;
  gainInput.disabled = noGain;
  if (noGain) {
    gainSlider.value = 0;
    gainInput.value = '0';
  } else {
    gainSlider.value = band.gain;
    gainInput.value = band.gain.toFixed(1);
  }
}

function freqToSlider(freq) {
  const f = clamp(Number(freq) || 1000, 20, 20000);
  return ((Math.log10(f) - Math.log10(20)) / (Math.log10(20000) - Math.log10(20)) * 100).toFixed(1);
}

function sliderToFreq(val) {
  const v = clamp(Number(val) || 0, 0, 100);
  return Math.round(20 * Math.pow(1000, v / 100));
}
function updateEqRisk() {
  const el = $('#eq-risk');
  if (!el) return;
  const bands = state.draftBands || [];
  let maxPositive = 0;
  let weightedBoost = 0;
  for (const b of bands) {
    if (!b.enabled) continue;
    const g = Number(b.gain) || 0;
    if (g <= 0) continue;
    maxPositive = Math.max(maxPositive, g);
    const f = Number(b.freq) || 1000;
    const weight = f <= 200 ? 2 : f <= 1000 ? 1.5 : 1;
    weightedBoost += g * weight;
  }
  const preamp = Number(state.draftPreamp) || 0;
  const clipRisk = Math.max(0, maxPositive + preamp); // 濮濓絽鈧壈銆冪粈鐑樻殶鐎涙鍢查崐鐓庡讲閼冲€熺Т鏉?0dBFS
  const score = weightedBoost + clipRisk * 2;

  let cls = 'low';
  let text = 'EQ 风险: 暂无建议';
  if (maxPositive > 6 || score > 12 || clipRisk > 0) {
    cls = 'high';
    const advice = [];
  if (clipRisk > 0) advice.push('降低 Preamp 至 -' + maxPositive.toFixed(1) + ' dB');
    // [fixed] if (maxPositive > 6) advice.push('閸楁洘閹绘劕宕?' + (maxPositive.toFixed(1)) + ' dB 鏉堝啫銇嘸);
  text = advice.join(' / ') || '暂无建议';
    // [fixed] text = '閳?' + (advice.join('閿?) || '婢х偟娉潏鍐ㄣ亣'');
  } else if (score > 6 || maxPositive > 3) {
    cls = 'mid';
    text = '中频增益较高: +' + (weightedBoost.toFixed(1)) + ' dB，建议 Preamp -' + (maxPositive.toFixed(1)) + ' dB';
  }
  el.className = 'eq-risk ' + cls;
  el.textContent = text;
}
function renderAllLocal() {
  renderPresets();
  renderDeviceSelect();
  renderTargetSelect();
renderTargetSelectMain();
  renderBands();
  renderChart();
  updateControls();
  updateRigWarning();
  const p = currentPreset();
  $('#eq-current-preset').textContent = p ? (p.name || p.id) : '未选择预设';
  const origSwitch = $('#original-switch');
  if (origSwitch) {
    origSwitch.checked = !!(state.activeOriginal && state.apoInfo.active_preset_id === state.currentPresetId);
  }
}

async function refreshConfigPreview() {
  const el = $('#config-text');
  if (!el) return;
  if (!state.currentPresetId) {
    if (configPre) configPre.textContent = '请选择预设后查看';
    return;
  }
  const showOriginal = !!(state.activeOriginal && state.apoInfo.active_preset_id === state.currentPresetId);
  try {
  const data = await api(`/api/preset/config?id=${encodeURIComponent(state.currentPresetId)}${showOriginal ? '&original=1' : ''}`);
  $('#config-text').textContent = configData.config_text || '（空预设）';
  } catch (e) {
    // 娣囨繄鏆€瀹稿弶婀佹０鍕敍灞肩瑝閹垫挻鏌囨禍銈勭鞍
  }
}

/* =========================================================================
 * Biquad / curve math / canvas
 * ====================================================================== */
const FS = 48000;
const F_MIN = 20;
const F_MAX = 20000;
const Y_MAX = 15;
const GRID_N = 240;

function generateFreqGrid(fmin = F_MIN, fmax = F_MAX, n = GRID_N) {
  const arr = [];
  const logMin = Math.log10(fmin);
  const logMax = Math.log10(fmax);
  for (let i = 0; i < n; i++) {
    const t = n <= 1 ? 0 : i / (n - 1);
    arr.push(Math.pow(10, logMin + (logMax - logMin) * t));
  }
  return arr;
}

function logInterp(points, freq) {
  if (!points || !points.length) return 0;
  const pts = points.filter(p => isFinite(p.freq) && isFinite(p.db)).sort((a, b) => a.freq - b.freq);
  if (!pts.length) return 0;
  if (pts.length === 1) return pts[0].db;
  if (freq <= pts[0].freq) return pts[0].db;
  if (freq >= pts[pts.length - 1].freq) return pts[pts.length - 1].db;
  let lo = 0, hi = pts.length - 1;
  while (lo + 1 < hi) {
    const mid = (lo + hi) >> 1;
    if (pts[mid].freq <= freq) lo = mid;
    else hi = mid;
  }
  const x1 = pts[lo].freq, x2 = pts[hi].freq;
  const y1 = pts[lo].db, y2 = pts[hi].db;
  if (x1 === x2) return y1;
  const t = Math.log(freq / x1) / Math.log(x2 / x1);
  return y1 + (y2 - y1) * t;
}

function biquadCoeffs(band, fs = FS) {
  const type = BAND_TYPE_MAP[band.type] || band.type;
  const f = clamp(band.freq, 1, fs / 2);
  const g = band.gain;
  const Q = clamp(band.q || 1, 0.1, 10);
  const A = Math.pow(10, g / 40);
  const w0 = 2 * Math.PI * f / fs;
  const cosw = Math.cos(w0);
  const sinw = Math.sin(w0);
  let b0 = 1, b1 = 0, b2 = 0, a0 = 1, a1 = 0, a2 = 0;
  switch (type) {
    case 'peaking': {
      const alpha = sinw / (2 * Q);
      b0 = 1 + alpha * A;
      b1 = -2 * cosw;
      b2 = 1 - alpha * A;
      a0 = 1 + alpha / A;
      a1 = -2 * cosw;
      a2 = 1 - alpha / A;
      break;
    }
    case 'low_shelf': {
      const S = Q;
      const alpha = sinw / 2 * Math.sqrt(Math.max(0, (A + 1 / A) * (1 / S - 1) + 2));
      b0 = A * ((A + 1) - (A - 1) * cosw + 2 * Math.sqrt(A) * alpha);
      b1 = 2 * A * ((A - 1) - (A + 1) * cosw);
      b2 = A * ((A + 1) - (A - 1) * cosw - 2 * Math.sqrt(A) * alpha);
      a0 = (A + 1) + (A - 1) * cosw + 2 * Math.sqrt(A) * alpha;
      a1 = -2 * ((A - 1) + (A + 1) * cosw);
      a2 = (A + 1) + (A - 1) * cosw - 2 * Math.sqrt(A) * alpha;
      break;
    }
    case 'high_shelf': {
      const S = Q;
      const alpha = sinw / 2 * Math.sqrt(Math.max(0, (A + 1 / A) * (1 / S - 1) + 2));
      b0 = A * ((A + 1) + (A - 1) * cosw + 2 * Math.sqrt(A) * alpha);
      b1 = -2 * A * ((A - 1) + (A + 1) * cosw);
      b2 = A * ((A + 1) + (A - 1) * cosw - 2 * Math.sqrt(A) * alpha);
      a0 = (A + 1) - (A - 1) * cosw + 2 * Math.sqrt(A) * alpha;
      a1 = 2 * ((A - 1) - (A + 1) * cosw);
      a2 = (A + 1) - (A - 1) * cosw - 2 * Math.sqrt(A) * alpha;
      break;
    }
    case 'low_pass': {
      const alpha = sinw / (2 * Q);
      b0 = (1 - cosw) / 2;
      b1 = 1 - cosw;
      b2 = (1 - cosw) / 2;
      a0 = 1 + alpha;
      a1 = -2 * cosw;
      a2 = 1 - alpha;
      break;
    }
    case 'high_pass': {
      const alpha = sinw / (2 * Q);
      b0 = (1 + cosw) / 2;
      b1 = -(1 + cosw);
      b2 = (1 + cosw) / 2;
      a0 = 1 + alpha;
      a1 = -2 * cosw;
      a2 = 1 - alpha;
      break;
    }
    default: break;
  }
  return { b0, b1, b2, a0, a1, a2 };
}

function magnitudeDb(band, freq, fs = FS) {
  const c = biquadCoeffs(band, fs);
  const w = 2 * Math.PI * freq / fs;
  const z1r = Math.cos(-w), z1i = Math.sin(-w);
  const z2r = Math.cos(-2 * w), z2i = Math.sin(-2 * w);
  const numRe = c.b0 + c.b1 * z1r + c.b2 * z2r;
  const numIm = c.b1 * z1i + c.b2 * z2i;
  const denRe = c.a0 + c.a1 * z1r + c.a2 * z2r;
  const denIm = c.a1 * z1i + c.a2 * z2i;
  const mag = Math.hypot(numRe, numIm) / Math.hypot(denRe, denIm);
  return 20 * Math.log10(mag || 1e-9);
}

function sumBandsDb(freq, bands) {
  let db = 0;
  for (const b of bands || []) {
    if (!b.enabled) continue;
    db += magnitudeDb(b, freq);
  }
  return db;
}

function curveLine(points) {
  if (!points || !points.length) return null;
  const sorted = points.slice().sort((a, b) => a.freq - b.freq);
  return sorted.map(p => ({ freq: p.freq, db: p.db }));
}

function compositeLine(bands, basePoints) {
  const grid = generateFreqGrid();
  return grid.map(f => ({
    freq: f,
    db: clamp(logInterp(basePoints || [], f) + sumBandsDb(f, bands), -15, 15)
  }));
}

function normalizeForDisplay(points, mode) {
  if (!points || !points.length || mode === 'none') return (points || []).map(p => ({ freq: p.freq, db: p.db }));
  const arr = (points || []).map(p => ({ freq: p.freq, db: p.db }));
  let refDb = 0;
  if (mode === '1k') {
    refDb = logInterp(arr, 1000);
  } else if (mode === 'ref_band_mean') {
    const refs = arr.filter(p => p.freq >= 500 && p.freq <= 2000);
    refDb = refs.length ? refs.reduce((s, p) => s + p.db, 0) / refs.length : logInterp(arr, 1000);
  } else if (mode === 'min_mean') {
    const refs = arr.filter(p => p.freq >= 100 && p.freq <= 10000);
    refDb = refs.length ? refs.reduce((s, p) => s + p.db, 0) / refs.length : logInterp(arr, 1000);
  }
  return arr.map(p => ({ freq: p.freq, db: p.db - refDb }));
}

function smoothPointsForDisplay(points, oct) {
  if (!points || !points.length || !oct || oct <= 0) return (points || []).map(p => ({ freq: p.freq, db: p.db }));
  const n = 256;
  const grid = [];
  for (let i = 0; i < n; i++) {
    grid.push(F_MIN * Math.pow(F_MAX / F_MIN, i / (n - 1)));
  }
  const dbs = grid.map(f => logInterp(points, f));
  const fStep = grid[1] / grid[0];
  const indicesPerOct = 1 / Math.log2(fStep);
  const sigma = oct * indicesPerOct;
  const radius = Math.max(1, Math.min(n, Math.ceil(sigma * 4)));
  const kernel = [];
  let sum = 0;
  for (let i = -radius; i <= radius; i++) {
    const w = Math.exp(-0.5 * Math.pow(i / sigma, 2));
    kernel.push(w);
    sum += w;
  }
  for (let i = 0; i < kernel.length; i++) kernel[i] /= sum;
  const padded = [];
  for (let i = 0; i < radius; i++) padded.push(dbs[0]);
  for (let i = 0; i < n; i++) padded.push(dbs[i]);
  for (let i = 0; i < radius; i++) padded.push(dbs[n - 1]);
  const smoothed = [];
  for (let i = 0; i < n; i++) {
    let acc = 0;
    for (let j = 0; j < kernel.length; j++) {
      acc += padded[i + j] * kernel[j];
    }
    smoothed.push(acc);
  }
  return grid.map((f, i) => ({ freq: f, db: smoothed[i] }));
}

function residualLine(eqBands, basePoints, targetPoints, mode, normMode, smoothOct) {
  const grid = generateFreqGrid();
  const baseNorm = normalizeForDisplay(basePoints, normMode);
  const tgtNorm = normalizeForDisplay(targetPoints, normMode);
  if (mode === 'raw') {
    const tgtSmooth = smoothPointsForDisplay(tgtNorm, smoothOct);
    return grid.map(f => ({ freq: f, db: logInterp(baseNorm, f) - logInterp(tgtSmooth, f) }));
  }
  const eqLine = grid.map(f => ({ freq: f, db: logInterp(baseNorm, f) + sumBandsDb(f, eqBands || []) }));
  const eqSmooth = smoothPointsForDisplay(eqLine, smoothOct);
  const tgtSmooth = smoothPointsForDisplay(tgtNorm, smoothOct);
  return grid.map((f, i) => ({ freq: f, db: eqSmooth[i].db - logInterp(tgtSmooth, f) }));
}

function toDisplayPoints(points, normMode, smoothOct) {
  return smoothPointsForDisplay(normalizeForDisplay(points, normMode), smoothOct);
}

const chart = {
  margin: { left: 42, right: 14, top: 14, bottom: 28 },
  dragIndex: null,
  hoverBand: null,
  mouseX: 0,
  mouseY: 0,
};

function canvasCtx() {
  const canvas = $('#eq-canvas');
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const w = Math.max(100, Math.floor(rect.width * dpr));
  const h = Math.max(200, Math.floor(rect.height * dpr));
  if (canvas.width !== w || canvas.height !== h) {
    canvas.width = w;
    canvas.height = h;
  }
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const cssW = canvas.width / dpr;
  const cssH = canvas.height / dpr;
  return { ctx, cssW, cssH };
}

function chartArea(cssW, cssH) {
  const m = chart.margin;
  return {
    left: m.left,
    top: m.top,
    width: Math.max(10, cssW - m.left - m.right),
    height: Math.max(10, cssH - m.top - m.bottom)
  };
}

function freqToX(f, area) {
  const t = (Math.log10(f) - Math.log10(F_MIN)) / (Math.log10(F_MAX) - Math.log10(F_MIN));
  return area.left + clamp(t, 0, 1) * area.width;
}

function xToFreq(x, area) {
  const t = clamp((x - area.left) / area.width, 0, 1);
  return F_MIN * Math.pow(10, t * (Math.log10(F_MAX) - Math.log10(F_MIN)));
}

function dbToY(db, area) {
  return area.top + (Y_MAX - clamp(db, -Y_MAX, Y_MAX)) / (2 * Y_MAX) * area.height;
}

function yToDb(y, area) {
  return Y_MAX - (y - area.top) / area.height * (2 * Y_MAX);
}

function drawGrid(ctx, area) {
  ctx.save();
  ctx.strokeStyle = '#2a3342';
  ctx.fillStyle = '#728096';
  ctx.font = '10px sans-serif';
  ctx.lineWidth = 1;
  const freqs = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000];
  for (const f of freqs) {
    const x = freqToX(f, area);
    ctx.beginPath();
    ctx.moveTo(x, area.top);
    ctx.lineTo(x, area.top + area.height);
    ctx.stroke();
      ctx.fillText(f >= 1000 ? (f / 1000) + 'k' : String(f), x - 10, area.top + area.height + 13);

  }

    // 频段范围参考标注（半透明背景 + 名称）
    ctx.save();
    ctx.textAlign = 'center';
    for (const zone of BAND_ZONES) {
      const x1 = freqToX(zone.min, area);
      const x2 = freqToX(zone.max, area);
      // 范围背景
      ctx.fillStyle = zone.bg;
      ctx.fillRect(x1, area.top + area.height + 15, x2 - x1, 13);
      // 范围分隔线
      ctx.strokeStyle = 'rgba(123,135,152,0.4)';
      ctx.beginPath();
      ctx.moveTo(x1, area.top + area.height + 14);
      ctx.lineTo(x1, area.top + area.height + 30);
      ctx.stroke();
      // 频段名称
      ctx.fillStyle = 'rgba(255,255,255,0.95)';
      ctx.font = 'bold 10px sans-serif';
      ctx.fillText(zone.en, (x1 + x2) / 2, area.top + area.height + 25);
    }
    ctx.restore();

  for (let db = -15; db <= 15; db += 5) {
    const y = dbToY(db, area);
    ctx.beginPath();
    ctx.moveTo(area.left, y);
    ctx.lineTo(area.left + area.width, y);
    ctx.stroke();
    ctx.fillText(`${db > 0 ? '+' : ''}${db}`, 4, y + 3);
  }
  ctx.restore();
}

function formatBandRange(min, max) {
  const fmt = (v) => {
    if (v >= 1000) {
      const k = v / 1000;
      return (Number.isInteger(k) ? k.toFixed(0) : k.toFixed(1)) + 'k';
    }
    return String(v);
  };
  return `${fmt(min)}-${fmt(max)}Hz`;
}

function isInBandStrip(clientX, clientY) {
  const canvas = $('#eq-canvas');
  if (!canvas) return false;
  const rect = canvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  const { cssW, cssH } = canvasCtx();
  const area = chartArea(cssW, cssH);
  return y >= area.top + area.height + 14 && y <= area.top + area.height + 30;
}

function setActiveBandZone(zoneId) {
  const next = zoneId && BAND_ZONES.some((z) => z.id === zoneId) ? zoneId : null;
  state.activeBandZone = next;

  const pop = $('#band-popover');
  if (!pop) {
    renderChart();
    return;
  }

  const zone = BAND_ZONES.find((z) => z.id === next);
  if (!zone) {
    pop.classList.add('hidden');
    pop.innerHTML = '';
    renderChart();
    return;
  }

  pop.classList.remove('hidden');
  pop.innerHTML = `
    <div class="band-popover-title">
      <span>${zone.en} · ${zone.cn}</span>
      <span class="band-popover-range">${formatBandRange(zone.min, zone.max)}</span>
      <span class="muted">再次点击取消</span>
    </div>
    <div class="band-popover-instruments"><strong>影响乐器：</strong>${zone.instruments}</div>
    <div class="band-popover-tip"><strong>调整建议：</strong>${zone.tip}</div>
  `;
  positionBandPopover(zone);
  renderChart();
}

function positionBandPopover(zone) {
  const canvas = $('#eq-canvas');
  const pop = $('#band-popover');
  if (!canvas || !pop) return;
  const rect = canvas.getBoundingClientRect();
  const { cssW, cssH } = canvasCtx();
  const area = chartArea(cssW, cssH);
  const midX = freqToX((zone.min + zone.max) / 2, area);
  const popWidth = pop.offsetWidth || 280;
  const left = clamp(midX - popWidth / 2, 8, Math.max(8, rect.width - popWidth - 8));
  const top = clamp(area.top + area.height - 148, 8, Math.max(8, rect.height - 160));
  pop.style.left = left + 'px';
  pop.style.top = top + 'px';
}

function onCanvasClick(ev) {
  const canvas = $('#eq-canvas');
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  const { cssW, cssH } = canvasCtx();
  const area = chartArea(cssW, cssH);

  // 只响应频响图下方频段条区域；点击图表其他位置关闭弹层
  const stripTop = area.top + area.height + 14;
  const stripBottom = area.top + area.height + 30;
  if (y < stripTop || y > stripBottom) {
    if (state.activeBandZone) setActiveBandZone(null);
    return;
  }

  for (const zone of BAND_ZONES) {
    const x1 = freqToX(zone.min, area);
    const x2 = freqToX(zone.max, area);
    if (x >= x1 && x <= x2) {
      setActiveBandZone(state.activeBandZone === zone.id ? null : zone.id);
      return;
    }
  }
}

function drawBandZoneHighlight(ctx, area) {
  const zone = BAND_ZONES.find((z) => z.id === state.activeBandZone);
  if (!zone) return;
  const x1 = freqToX(zone.min, area);
  const x2 = freqToX(zone.max, area);

  ctx.save();
  // 频响区域高亮：浅色底 + 两侧边界虚线
  ctx.fillStyle = zone.bg;
  ctx.fillRect(x1, area.top, x2 - x1, area.height);

  ctx.strokeStyle = zone.color;
  ctx.lineWidth = 1.5;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  ctx.moveTo(x1, area.top);
  ctx.lineTo(x1, area.top + area.height);
  ctx.moveTo(x2, area.top);
  ctx.lineTo(x2, area.top + area.height);
  ctx.stroke();

  // 下方频段条同步加亮
  ctx.globalAlpha = 0.55;
  ctx.fillStyle = zone.color;
  ctx.fillRect(x1, area.top + area.height + 15, x2 - x1, 13);
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#fff';
  ctx.font = 'bold 10px sans-serif';
  ctx.fillText(zone.en, (x1 + x2) / 2, area.top + area.height + 25);
  ctx.restore();
}


function drawTrustBands(ctx, area) {
  // 残差/误差展示时的频段可信度色带（需求 R5）。
  const verified9k = isTrust9kPlusVerified();
  const zones = [
    { min: 20, max: 3000, fill: 'rgba(67,209,124,0.06)' },
    { min: 3000, max: 6000, fill: 'rgba(230,196,60,0.07)' },
    { min: 6000, max: 9000, fill: 'rgba(255,164,61,0.08)' },
    { min: 9000, max: 20000, fill: verified9k ? 'rgba(67,209,124,0.10)' : 'rgba(255,107,107,0.14)' },
  ];
  ctx.save();
  for (const zone of zones) {
    const x1 = freqToX(zone.min, area);
    const x2 = freqToX(zone.max, area);
    ctx.fillStyle = zone.fill;
    ctx.fillRect(x1, area.top, x2 - x1, area.height);
  }
  const x9 = freqToX(9000, area);
  ctx.strokeStyle = verified9k ? 'rgba(67,209,124,0.55)' : 'rgba(255,107,107,0.7)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(x9, area.top);
  ctx.lineTo(x9, area.top + area.height);
  ctx.stroke();
  ctx.restore();
}

function drawLine(ctx, line, area, color, dash = false, width = 2) {
  if (!line || !line.length) return;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.setLineDash(dash ? [6, 4] : []);
  ctx.beginPath();
  let started = false;
  for (const p of line) {
    const x = freqToX(p.freq, area);
    const y = dbToY(p.db, area);
    if (!started) { ctx.moveTo(x, y); started = true; }
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.restore();
}

function renderChart() {
  const { ctx, cssW, cssH } = canvasCtx();
  const area = chartArea(cssW, cssH);
  ctx.clearRect(0, 0, cssW, cssH);
  ctx.fillStyle = '#141821';
  ctx.fillRect(0, 0, cssW, cssH);
  drawGrid(ctx, area);
  drawBandZoneHighlight(ctx, area);

  const legendDevice = $('#legend-device').checked;
  const legendEq = $('#legend-eq').checked;
  const legendEqualized = $('#legend-equalized').checked;
  const legendApplied = $('#legend-applied').checked;
  const legendDraft = $('#legend-draft').checked;
  const legendTarget = $('#legend-target').checked;
  const legendPreview = $('#legend-preview').checked;
  const legendResidual = $('#legend-residual') ? $('#legend-residual').checked : false;
  const normMode = $('#display-normalization') ? $('#display-normalization').value : 'none';
  const smoothOct = parseFloat($('#display-smoothing') ? $('#display-smoothing').value : '0') || 0;
  const residualMode = $('#residual-mode') ? $('#residual-mode').value : 'eq';

  const basePoints = (state.deviceCurve && state.deviceCurve.points) || [];
  const targetPoints = (state.targetCurve && state.targetCurve.points) || [];
  const targetLine = toDisplayPoints(targetPoints, normMode, smoothOct);
  const deviceLine = toDisplayPoints(basePoints, normMode, smoothOct);
  const eqLine = toDisplayPoints(compositeLine(state.draftBands, []), normMode, smoothOct);
  const equalizedLine = toDisplayPoints(compositeLine(state.draftBands, basePoints), normMode, smoothOct);

  if (legendResidual) {
    drawTrustBands(ctx, area);
  }
  if (legendResidual && targetPoints.length && basePoints.length) {
    drawLine(ctx, residualLine(state.draftBands, basePoints, targetPoints, residualMode, normMode, smoothOct), area, '#ff6b6b', false, 1.6);
  }
  if (legendTarget && targetLine.length) {
    drawLine(ctx, targetLine, area, '#5aa9ff', true, 1.8);
  }
  if (legendDevice) {
    if (deviceLine.length) {
      drawLine(ctx, deviceLine, area, '#8a94a3', false, 2);
    } else {
      drawLine(ctx, [{freq: F_MIN, db: 0}, {freq: F_MAX, db: 0}], area, '#8a94a3', false, 1);
    }
  }
  if (legendEq) {
    drawLine(ctx, eqLine, area, '#ffa43d', false, 2.5);
  }
  if (legendApplied) {
    drawLine(ctx, toDisplayPoints(compositeLine(state.appliedBands, basePoints), normMode, smoothOct), area, '#43d17c', false, 2);
  }
  if (legendEqualized) {
    drawLine(ctx, equalizedLine, area, '#00e5ff', false, 2.5);
  }
  if (legendDraft) {
    drawLine(ctx, toDisplayPoints(compositeLine(state.draftBands, basePoints), normMode, smoothOct), area, '#ffa43d', false, 2);
  }
  if (legendPreview && state.previewBands) {
    drawLine(ctx, toDisplayPoints(compositeLine(state.previewBands, basePoints), normMode, smoothOct), area, '#b57bff', true, 2.2);
  }

  if (legendDraft && state.draftBands.length) {
    state.draftBands.forEach((band, idx) => {
      if (!band.enabled) return;
      const x = freqToX(band.freq, area);
      const y = dbToY(band.gain, area);
      ctx.save();
      ctx.beginPath();
      ctx.arc(x, y, 6, 0, Math.PI * 2);
      ctx.fillStyle = band.type === 'LP' || band.type === 'HP' ? '#8a94a3' : '#ffa43d';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      // (说明已移除)
      ctx.textAlign = 'center';
      ctx.fillText(String(idx + 1), x, y - 9);
      ctx.restore();
    });
  }

  if (state.previewLabel && state.previewBands) {
    ctx.save();
    ctx.fillStyle = '#b57bff';
    ctx.font = '12px sans-serif';
    ctx.fillText('预览: ' + (state.previewLabel), area.left, area.top - 4);
    ctx.restore();
  }

  if (chart.hoverBand != null && state.draftBands[chart.hoverBand]) {
    const band = state.draftBands[chart.hoverBand];
    const text = `#${chart.hoverBand + 1} ${band.type} ${Math.round(band.freq)} Hz ${band.gain > 0 ? '+' : ''}${band.gain.toFixed(1)} dB  Q ${band.q.toFixed(2)}";`
    showTooltip(text, chart.mouseX, chart.mouseY);
  } else {
    hideTooltip();
  }
}

function showTooltip(text, x, y) {
  const el = $('#canvas-tooltip');
  el.textContent = text;
  el.style.left = (x + 12) + 'px';
  el.style.top = (y + 12) + 'px';
  el.classList.remove('hidden');
}
function hideTooltip() {
  $('#canvas-tooltip').classList.add('hidden');
}

function getNodeAt(clientX, clientY) {
  const canvas = $('#eq-canvas');
  const rect = canvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  const { cssW, cssH } = canvasCtx();
  const area = chartArea(cssW, cssH);
  for (let i = state.draftBands.length - 1; i >= 0; i--) {
    const band = state.draftBands[i];
    if (!band.enabled) continue;
    const nx = freqToX(band.freq, area);
    const ny = dbToY(band.gain, area);
    if (Math.hypot(x - nx, y - ny) <= 10) return { index: i, x, y };
  }
  return null;
}

function onCanvasDblClick(ev) {
  if (!state.online || state.currentPresetId == null) return;
  if (isInBandStrip(ev.clientX, ev.clientY)) return;
  if (state.draftBands.length >= 20) {
    toast('频段已达上限 20', 'warning');
    return;
  }
  const canvas = $('#eq-canvas');
  const rect = canvas.getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  const { cssW, cssH } = canvasCtx();
  const area = chartArea(cssW, cssH);
  const freq = clamp(Math.round(xToFreq(x, area)), 20, 20000);
  const gain = clamp(parseFloat(yToDb(y, area).toFixed(1)), -12, 12);
  const idx = state.draftBands.length;
  state.draftBands.push({ type: 'PK', freq, gain, q: 1, enabled: true });
  state.manualBandIndex = idx;
  renderBands();
  renderChart();
  setDirty(isDirty());
  
  toast('已添加 Band ' + (idx + 1) + ' @ ' + freq + ' Hz', 'success', 1200);
}

function onCanvasMouseDown(ev) {
  if (!state.online || state.currentPresetId == null) return;
  if (isInBandStrip(ev.clientX, ev.clientY)) {
    chart.dragIndex = null;
    return;
  }
  const hit = getNodeAt(ev.clientX, ev.clientY);
  if (hit) {
    chart.dragIndex = hit.index;
    ev.preventDefault();
    return;
  }
  chart.dragIndex = null;
}

function onCanvasMouseMove(ev) {
  const canvas = $('#eq-canvas');
  const rect = canvas.getBoundingClientRect();
  const x = ev.clientX - rect.left;
  const y = ev.clientY - rect.top;
  chart.mouseX = x;
  chart.mouseY = y;
  const hit = getNodeAt(ev.clientX, ev.clientY);
  chart.hoverBand = hit ? hit.index : null;

  const cursorInfo = canvasCtx();
  const cursorArea = chartArea(cursorInfo.cssW, cursorInfo.cssH);
  const inBandStrip = y >= cursorArea.top + cursorArea.height + 14 && y <= cursorArea.top + cursorArea.height + 30;
  canvas.style.cursor = inBandStrip ? 'pointer' : 'crosshair';
  if (inBandStrip) chart.hoverBand = null;

  if (chart.dragIndex != null && state.draftBands[chart.dragIndex]) {
    const { cssW, cssH } = canvasCtx();
    const area = chartArea(cssW, cssH);
    const band = state.draftBands[chart.dragIndex];
    const freq = clamp(Math.round(xToFreq(x, area)), 20, 20000);
    if (band.type !== 'LP' && band.type !== 'HP') {
      const gain = clamp(parseFloat(yToDb(y, area).toFixed(1)), -12, 12);
      band.freq = freq;
      band.gain = gain;
    } else {
      band.freq = freq;
    }
    renderBands();
    renderChart();
    markDirtyFromEdit();
    ev.preventDefault();
  }
  renderChart();
}

function onCanvasMouseUp() {
  if (chart.dragIndex != null) {
    chart.dragIndex = null;
    markDirtyFromEdit();
  }
}

function onCanvasLeave() {
  chart.dragIndex = null;
  chart.hoverBand = null;
  hideTooltip();
}

function onCanvasWheel(ev) {
  if (!state.online || state.currentPresetId == null) return;
  if (isInBandStrip(ev.clientX, ev.clientY)) return;
  const hit = getNodeAt(ev.clientX, ev.clientY);
  if (!hit) return;
  ev.preventDefault();
  const band = state.draftBands[hit.index];
  if (!band) return;
  const delta = ev.deltaY < 0 ? 0.1 : -0.1;
  band.q = clamp(parseFloat((band.q + delta).toFixed(2)), 0.1, 10);
  renderBands();
  renderChart();
  markDirtyFromEdit();
}

function markDirtyFromEdit() {
  setDirty(isDirty());
}

/* =========================================================================
 * Band table / preset actions
 * ====================================================================== */
function onBandInput(idx, field, value) {
  if (idx < 0 || idx >= state.draftBands.length) return;
  const band = state.draftBands[idx];
  switch (field) {
    case 'type':
      band.type = normalizeBandType(value);
      break;
    case 'freq':
      band.freq = clamp(Number(value) || 1000, 20, 20000);
      break;
    case 'gain':
      band.gain = clamp(Number(value) || 0, -12, 12);
      break;
    case 'q':
      band.q = clamp(Number(value) || 1, 0.1, 10);
      break;
    case 'enabled':
      band.enabled = !!value;
      break;
  }
  renderChart();
  renderManualEq();
  setDirty(isDirty());
}

function addBand() {
  if (!state.online || state.currentPresetId == null) return;
  if (state.draftBands.length >= 20) {
    toast('频段已达上限 20', 'warning');
    return;
  }
  const idx = state.draftBands.length;
  state.draftBands.push({ type: 'PK', freq: 1000, gain: 0, q: 1, enabled: true });
  state.manualBandIndex = idx;
  renderBands();
  renderChart();
  setDirty(isDirty());
  
}

function onDeleteBand(idx) {
  if (idx < 0 || idx >= state.draftBands.length) return;
  state.draftBands.splice(idx, 1);
  if (state.manualBandIndex >= state.draftBands.length) {
    state.manualBandIndex = Math.max(0, state.draftBands.length - 1);
  }
  renderBands();
  renderChart();
  setDirty(isDirty());
  
}

function promptSaveBeforeSwitch() {
  return new Promise((resolve) => {
      $('#modal-save-switch').classList.remove('hidden');
    const done = (action) => {
        $('#btn-save-switch').onclick = null;
        $('#btn-discard-switch').onclick = null;
        $('#btn-cancel-switch').onclick = null;
        $('#modal-save-switch').classList.add('hidden');
      resolve(action);
    };
      $('#btn-save-switch').onclick = () => done('save');
      $('#btn-discard-switch').onclick = () => done('discard');
      $('#btn-cancel-switch').onclick = () => done('cancel');
  });
}

async function switchPreset(id, shouldActivate) {
  if (id == null) return;
  if (!state.online) { toast('离线状态，请先启动服务', 'warning', 1800); return; }
  if (state.dirty) {
    const action = await promptSaveBeforeSwitch();
    if (action === 'cancel') return;
    if (action === 'save') {
      await onApply();
      if (state.dirty) {
        toast('保存失败，无法切换预设', 'error');
        return;
      }
    }
  }
  state.currentPresetId = id;
  await loadPresetData(id, { keepDraft: false });
  if (shouldActivate) {
    try {
      await api('/api/preset/activate', { method: 'POST', body: { id } });
      await loadStatus();
      await loadPresets(id);
      await loadPresetData(id, { keepDraft: false });
    } catch (e) {
        toast("激活失败: ${e.message}", 'error');
    }
  }
}

async function onDeletePreset(id) {
  if (!state.online) { toast('离线状态，请先启动服务', 'warning', 1800); return; }
  const ok = await confirmDialog('删除预设', '确定删除预设"' + id + '"吗？此操作不可恢复。');
  if (!ok) return;
  try {
    await api('/api/preset/del', { method: 'POST', body: { id } });
    await loadStatus();
    await loadPresets(null);
    if (state.currentPresetId === id) {
      state.currentPresetId = null;
    }
    toast('预设已删除', 'success');
    // 已删除
  } catch (e) {
    toast('删除失败: ' + e.message, 'error');
  }
}

function onAddPreset() {
  $('#new-preset-name').value = '';
  $('#new-preset-device').value = '';
  openModal('#modal-add-preset');
  setTimeout(() => $('#new-preset-name').focus(), 50);
}

async function confirmAddPreset() {
  const name = $('#new-preset-name').value.trim();
  if (!name) { toast('请输入预设名称', 'warning'); return; }
  try {
    const data = await api('/api/preset/add', { method: 'POST', body: { name, device_id: $('#new-preset-device').value } });
    closeModal('#modal-add-preset');
    await loadPresets(data.preset.id);
    await loadPresetData(data.preset.id, { keepDraft: false });
    toast('已创建预设 ' + name, 'success');
  } catch (e) {
    toast('创建预设失败: ' + e.message, 'error');
  }
}
let renamingPresetId = null;

function onRenamePreset(id) {
  renamingPresetId = id;
  const p = state.presets.find(x => x.id === id);
  $('#rename-preset-name').value = p ? (p.name || '') : '';
  openModal('#modal-rename-preset');
  setTimeout(() => $('#rename-preset-name').focus(), 50);
}

async function confirmRenamePreset() {
  const name = $('#rename-preset-name').value.trim();
  if (!renamingPresetId || !name) { toast('请输入预设名称', 'warning'); return; }
  try {
    await api('/api/preset/rename', { method: 'POST', body: { id: renamingPresetId, name } });
    closeModal('#modal-rename-preset');
await loadStatus();
    await loadPresets(renamingPresetId);
    await loadPresetData(renamingPresetId, { keepDraft: true });
    toast('重命名成功', 'success', 1500);
  } catch (e) {
    toast('重命名失败: ' + e.message, 'error');
  }
}

async function onDeviceChange(deviceIdVal) {
  if (!state.online || state.currentPresetId == null) return;
  try {
    await api('/api/preset/device', { method: 'PUT', body: { id: state.currentPresetId, device_id: deviceIdVal } });
    await loadPresets(state.currentPresetId);
    await loadPresetData(state.currentPresetId, { keepDraft: true });
    toast('设备已保存到预设', 'success', 1500);
  } catch (e) {
    toast('设备保存失败: ' + (e.message), 'error');
  }
}
async function onTargetChange(targetIdVal) {
  if (!state.online) return;
  state.targetCurveId = targetIdVal || '';
  await loadTargetCurve(state.targetCurveId);
  if (state.autoFitEnabled) await runAutoFitAndAdopt();
  if (state.currentPresetId == null) return;
  try {
    await api('/api/preset/target', { method: 'PUT', body: { id: state.currentPresetId, target_id: targetIdVal } });
    await loadPresets(state.currentPresetId);
    await loadPresetData(state.currentPresetId, { keepDraft: true });
    toast('目标曲线已保存到预设', 'success', 1500);
  } catch (e) {
    toast('目标曲线保存失败: ' + (e.message), 'error');
  }
}

async function onActivatePreset(id) {
  if (!state.online) return;
  try {
    await api('/api/preset/activate', { method: 'POST', body: { id } });
    await loadStatus();
    await loadPresets(state.currentPresetId);
    renderAllLocal();
  parts.push('<span class="badge">当前: 直通</span>');
  } catch (e) {
    toast('激活失败: ' + (e.message), 'error');
  }
}

/* =========================================================================
 * Apply / revert / discard
 * ====================================================================== */
  function scheduleLiveApply() {
    if (!state.online || state.currentPresetId == null) return;
    const preset = currentPreset();
    if (!preset || !preset.active) return;
    if (liveApplyTimer) clearTimeout(liveApplyTimer);
    liveApplyTimer = setTimeout(() => {
      liveApplyTimer = null;
      liveApply().catch(() => {});
    }, 600);
  }

  async function liveApply() {
    if (!state.online || state.currentPresetId == null) return;
    const preset = currentPreset();
    if (!preset || !preset.active) return;
  // 收集UI状态（下拉框、开关等）
  const uiState = {
    device_id: $('#device-select').value || '',
    auto_fit_enabled: $('#auto-fit-switch').checked || false,
    legend: {
      device: $('#legend-device').checked,
      target: $('#legend-target').checked,
      eq: $('#legend-eq').checked,
      equalized: $('#legend-equalized').checked,
      applied: $('#legend-applied').checked,
      draft: $('#legend-draft').checked,
      preview: $('#legend-preview').checked
    }
  };
    try {
      await api('/api/eq/apply', {
        method: 'POST',
        body: {
          preset: state.currentPresetId,
          bands: clone(state.draftBands),
          preamp_db: state.draftPreamp || 0,
            target_id: state.targetCurveId || '',
          activate: true,
          fit: state.draftFitSettings || {},
          ui_state: uiState
        }
      });
      await loadStatus();
      await loadPresets(state.currentPresetId);
      await loadPresetData(state.currentPresetId, { keepDraft: true });
    } catch (e) {
      toast('实时应用失败: ' + e.message, 'error');
    }
  }

async function onApply() {
  if (!state.online || state.currentPresetId == null) return;
  if (state.previewBands && state.previewBands.length > 0 && !state.dirty) {
    state.draftBands = clone(state.previewBands);
    state.draftPreamp = state.previewPreamp || 0;
    state.previewBands = null;
    state.previewPreamp = 0;
    state.previewLabel = '';
    setDirty(isDirty());
    renderBands();
    renderChart();
  }
  if (!state.dirty) {
    toast('没有需要保存的修改', 'info', 1500);
    return;
  }
  const activate = $('#apply-activate-checkbox').checked;
  $('#btn-apply').disabled = true;
  
  // 收集UI状态（下拉框、开关等）
  const uiState = {
    device_id: $('#device-select').value || '',
    auto_fit_enabled: $('#auto-fit-switch').checked || false,
    legend: {
      device: $('#legend-device').checked,
      target: $('#legend-target').checked,
      eq: $('#legend-eq').checked,
      equalized: $('#legend-equalized').checked,
      applied: $('#legend-applied').checked,
      draft: $('#legend-draft').checked,
      preview: $('#legend-preview').checked
    }
  };
  
  try {
    const resp = await api('/api/eq/apply', {
      method: 'POST',
      body: {
        preset: state.currentPresetId,
        bands: clone(state.draftBands),
        preamp_db: state.draftPreamp || 0,
        target_id: state.targetCurveId || '',
        activate,
        fit: state.draftFitSettings || {},
        ui_state: uiState
      }
    });
    await loadStatus();
    await loadPresets(state.currentPresetId);
    await loadPresetData(state.currentPresetId, { keepDraft: false });
    if (resp && resp.config_text) $('#config-text').textContent = resp.config_text;
    toast(resp && resp.deployed ? '已保存并部署到 EqualizerAPO' : '已保存到预设（未激活）', 'success', 3000);
  } catch (e) {
    toast('保存失败: ' + e.message, 'error', 5000);
  } finally {
    updateControls();
  }
}

async function onRevert() {
  if (!state.online || state.currentPresetId == null) return;
  const p = currentPreset();
  const presetLabel = p && p.name ? p.name : (state.currentPresetId || '');
  const ok = await confirmDialog('撤销上次保存', '确定撤销预设"' + presetLabel + '"的上次保存吗？');
  if (!ok) return;
  try {
    await api('/api/eq/revert', { method: 'POST', body: { preset: state.currentPresetId } });
    await loadStatus();
    await loadPresets(state.currentPresetId);
    await loadPresetData(state.currentPresetId, { keepDraft: false });
    toast('已撤销上次保存', 'success');
  } catch (e) {
    toast('撤销失败: ' + e.message, 'error');
  }
}

function onDiscard() {
  state.draftBands = clone(state.appliedBands);
  state.draftPreamp = state.appliedPreamp;
  state.previewBands = null;
  state.previewPreamp = 0;
  state.previewLabel = '';
  setDirty(false);
  renderBands();
  renderChart();
}

/* =========================================================================
 * Import / autofit
 * ====================================================================== */
async function onParse() {
  const text = $('#import-text').value.trim();
  if (!text) { toast('请粘贴 EQ 文本', 'warning'); return; }
  try {
    const data = await api('/api/eq/parse', { method: 'POST', body: { text } });
    const bands = normalizeBands(data.bands || []);
    const warnings = Array.isArray(data.warnings) ? data.warnings : (data.warnings ? [String(data.warnings)] : []);
    state.previewBands = bands;
    state.previewPreamp = Number(data.preamp_db ?? data.preamp ?? 0) || 0;
    state.previewLabel = '解析 EQ';
    renderChart();
    renderImportResult(bands, warnings);
    updateControls();
  } catch (e) {
    toast('解析失败: ' + e.message, 'error');
  }
}

function renderImportResult(bands, warnings) {
  const box = $('#import-result');
  box.classList.remove('hidden');
  box.classList.toggle('warn', !!(warnings && warnings.length));
  let html = '<div class="res-title">解析结果</div>';
  if (warnings && warnings.length) {
    html += '<div style="color:#e6c35c">' + warnings.map(escapeHtml).join('<br>') + '</div>';
  }
  if (!bands.length) {
    html += '<div class="muted">未解析到频段</div>';
  } else {
    html += '<ul class="result-list">' + bands.map((b, i) => {
      return '<li>' + (i + 1) + '. ' + b.type + ' ' + Math.round(b.freq) + 'Hz ' + (b.gain >= 0 ? '+' : '') + b.gain.toFixed(1) + 'dB Q' + b.q.toFixed(2) + '</li>';
    }).join('') + '</ul>';
  }
  box.innerHTML = html;
}
function collectFitSettings() {

  let targetAmount = 1;
  if ($('#target-amount')) {
    const v = parseFloat($('#target-amount').value);
    targetAmount = isNaN(v) ? 1 : clamp(v, 0, 1);
  }
  const targetAdjust = {
    amount: targetAmount,
    bass_db: $('#target-bass') ? Number($('#target-bass').value) || 0 : 0,
    treble_db: $('#target-treble') ? Number($('#target-treble').value) || 0 : 0,
    tilt_db: $('#target-tilt') ? Number($('#target-tilt').value) || 0 : 0
  };
  const hasTargetAdjust = Math.abs(targetAdjust.amount - 1) > 0.001 || Math.abs(targetAdjust.bass_db) > 0.001 || Math.abs(targetAdjust.treble_db) > 0.001 || Math.abs(targetAdjust.tilt_db) > 0.001;
  return {
    filters: Number($('#filters-count').value) || 10,
    fmin: Number($('#fmin').value) || 100,
    fmax: Number($('#fmax').value) || 10000,
    max_gain_db: Number($('#max-gain').value) || 6,
    max_q: Number($('#max-q').value) || 3,
    engine: $('#fit-engine') ? $('#fit-engine').value : 'quick',
    auto_shelf: $('#auto-shelf') ? $('#auto-shelf').checked : false,
    hi_fidelity: $('#hi-fidelity') ? $('#hi-fidelity').checked : false,
    smooth: $('#smooth') ? $('#smooth').checked : true,
    sharpness_penalty: $('#sharpness-penalty') ? $('#sharpness-penalty').checked : true,
    sanitize_bands: $('#sanitize-bands') ? $('#sanitize-bands').checked : true,
    weight_profile: $('#weight-profile') ? $('#weight-profile').value : 'none',
    auto_filters: $('#auto-filters') ? $('#auto-filters').checked : false,
    target_rms: Number($('#target-rms').value) || 0.5,
    allow_cross_rig_hf: $('#allow-cross-rig-hf') ? $('#allow-cross-rig-hf').checked : false,
    de_rig: ($('#de-rig') && !$('#de-rig').disabled) ? $('#de-rig').checked : false,
    target_adjust: hasTargetAdjust ? targetAdjust : null
  };
}

function applyFitSettings(fit) {
  if (!fit) return;
  const setVal = (id, val) => { const el = $(id); if (el && val !== undefined) el.value = val; };
  const setCheck = (id, val) => { const el = $(id); if (el) el.checked = !!val; };
  setVal('#filters-count', fit.filters);
  setVal('#fmin', fit.fmin);
  setVal('#fmax', fit.fmax);
  setVal('#max-gain', fit.max_gain_db);
  setVal('#max-q', fit.max_q);
  setVal('#fit-engine', fit.engine);
  if (typeof updateFitEngineControls === 'function') updateFitEngineControls();
  setCheck('#auto-shelf', fit.auto_shelf);
  setCheck('#hi-fidelity', fit.hi_fidelity);
  setCheck('#smooth', fit.smooth !== undefined ? fit.smooth : true);
  setCheck('#sharpness-penalty', fit.sharpness_penalty !== undefined ? fit.sharpness_penalty : true);
  setCheck('#sanitize-bands', fit.sanitize_bands !== undefined ? fit.sanitize_bands : true);
  setVal('#weight-profile', fit.weight_profile || 'none');
  setCheck('#auto-filters', fit.auto_filters);
  setVal('#target-rms', fit.target_rms !== undefined ? fit.target_rms : 0.5);
  setCheck('#allow-cross-rig-hf', fit.allow_cross_rig_hf);
  const deRig = $('#de-rig');
  if (deRig && !deRig.disabled) setCheck('#de-rig', fit.de_rig);
  if (fit.target_adjust) {
    setVal('#target-amount', fit.target_adjust.amount !== undefined ? fit.target_adjust.amount : 1);
    setVal('#target-bass', fit.target_adjust.bass_db || 0);
    setVal('#target-treble', fit.target_adjust.treble_db || 0);
    setVal('#target-tilt', fit.target_adjust.tilt_db || 0);
  }
  if (typeof updateHfWarning === 'function') updateHfWarning();
}

async function runAutoFitAndAdopt() {
  if (!state.online || state.currentPresetId == null) return;
  const target = state.targetCurveId || $('#target-select-main').value || $('#target-select').value;
  if (!target) {
    toast('请先选择目标曲线', 'warning', 2000);
    return;
  }
  const fitSettings = collectFitSettings();
  const body = {
    preset: state.currentPresetId,
    target,
    ...fitSettings,
    filters: clamp(Number($('#filters-count').value) || 10, 1, 20),
    fmin: clamp(Number($('#fmin').value) || 100, 20, 20000),
    fmax: clamp(Number($('#fmax').value) || 10000, 20, 20000),
    max_gain_db: clamp(Number($('#max-gain').value) || 6, 0, 15),
    max_q: clamp(Number($('#max-q').value) || 3, 0.1, 10)
  };
  try {
    const data = await api('/api/eq/autofit', { method: 'POST', body });
    state.draftBands = normalizeBands(data.bands || []);
    state.draftPreamp = Number(data.preamp_db ?? data.preamp ?? 0) || 0;
    state.previewBands = null;
    state.previewPreamp = 0;
    state.previewLabel = '';
      state.draftFitSettings = {
        filters: body.filters,
        fmin: body.fmin,
        fmax: body.fmax,
        max_gain_db: body.max_gain_db,
        max_q: body.max_q,
        engine: body.engine || 'quick',
        auto_shelf: !!body.auto_shelf,
        hi_fidelity: !!body.hi_fidelity,
        smooth: !!body.smooth,
        sharpness_penalty: !!body.sharpness_penalty,
        sanitize_bands: !!body.sanitize_bands,
        weight_profile: body.weight_profile || 'none',
        auto_filters: !!body.auto_filters,
        target_rms: body.target_rms,
        allow_cross_rig_hf: !!body.allow_cross_rig_hf,
        de_rig: !!body.de_rig,
        target_adjust: body.target_adjust
      };
    renderBands();
    renderChart();
    setDirty(isDirty());
    toast('自动拟合已采用', 'success', 2000);
  } catch (e) {
    toast('自动拟合失败: ' + e.message, 'error');
  }
}
async function onAutoEqSearch() {
  const q = $('#autoeq-search-input').value.trim();
  const box = $('#autoeq-results');
  if (!box) return;
  try {
  const data = await api(`/api/autoeq/search?q=${encodeURIComponent(q)}`);
    const devices = data.devices || [];
    if (!devices.length) {
      box.innerHTML = '<div class="muted">未找到可导入的数据</div>';
      return;
    }
    box.innerHTML = '<div class="res-title">搜索结果</div><ul class="result-list">' +
      devices.map((d, i) => '<li>' + (i + 1) + '. ' + escapeHtml(d.name) + ' <span class="muted">(' + escapeHtml(d.source) + ' / ' + escapeHtml(d.form) + ')</span> <button class="btn btn-small" data-autoeq-target="' + escapeHtml(d.id) + '">导入目标</button> <button class="btn btn-small" data-autoeq-id="' + escapeHtml(d.id) + '">导入频响+PEQ</button></li>').join('') +
      '</ul>';
    box.querySelectorAll('[data-autoeq-target]').forEach(btn => {
      btn.addEventListener('click', () => onAutoEqImportTarget(btn.dataset.autoeqTarget));
    });
    box.querySelectorAll('[data-autoeq-id]').forEach(btn => {
      btn.addEventListener('click', () => onAutoEqImport(btn.dataset.autoeqId));
    });
  } catch (e) {
    box.innerHTML = '<div class="muted">搜索失败: ' + (escapeHtml(e.message)) + '</div>';
  }
}

async function onAutoEqImportTarget(deviceId) {
  // [fixed] if (!state.online) { toast('瑜版挸澧犳稉宥呮躬缁?, 'warning'); return; }
  try {
    const data = await api('/api/autoeq/import_target', {
      method: 'POST',
      body: { device_id: deviceId }
    });
    state.targetCurveCache = {};
    await loadTargets();
    await onTargetChange(data.target_id);
    renderChart();
    if (state.autoFitEnabled) await runAutoFitAndAdopt();
    const c = data.curve || {};
    const rigTag = c.rig ? '（' + (c.variant || c.measurement_source || '') + ' / ' + c.rig + '）' : '';
    toast('已导入 ' + (c.measured_device || c.name || 'AutoEq 曲线') + ' ' + rigTag, 'success', 3000);
  } catch (e) {
    toast('导入目标曲线失败: ' + (e.message), 'error');
  }
}

async function onAutoEqImport(deviceId) {
  // [fixed] if (!state.online) { toast('瑜版挸澧犳稉宥呮躬缁?, 'warning'); return; }
  try {
    const data = await api('/api/autoeq/import', {
      method: 'POST',
      body: {
        device_id: deviceId,
        preset: state.currentPresetId || '',
        activate: false
      }
    });
    await loadPresets(data.preset);
    await loadPresetData(data.preset, { keepDraft: false });
    if (data.target_id) {
      state.targetCurveId = data.target_id;
      await loadTargetCurve(data.target_id);
      renderChart();
    }
    const c = data.curve || {};
    const rigTag = c.rig ? '（' + (c.variant || c.measurement_source || '') + ' / ' + c.rig + '）' : '';
    toast('已导入 ' + (c.measured_device || c.name || 'AutoEq 曲线') + ' 的频响和 PEQ', 'success', 3000);
  } catch (e) {
    toast('导入失败: ' + (e.message), 'error');
  }
}
function updateHfWarning() {
  const el = $('#hf-warning');
  if (!el) return;
  const fmax = clamp(Number($('#fmax').value) || 0, 0, 20000);
  el.classList.toggle('hidden', fmax <= 15000);
}
function updateFitEngineControls() {
  const engine = $('#fit-engine') ? $('#fit-engine').value : 'quick';
  const hi = $('#hi-fidelity');
  const sharp = $('#sharpness-penalty');
  if (hi) {
    hi.disabled = engine !== 'precise';
    const label = hi.closest('label');
    if (label) label.classList.toggle('muted', engine !== 'precise');
  }
  if (sharp) {
    sharp.disabled = engine !== 'quick';
    const label = sharp.closest('label');
    if (label) label.classList.toggle('muted', engine !== 'quick');
  }
}

async function onAutofit() {
  if (!state.online || state.currentPresetId == null) return;
  updateHfWarning();
  const target = $('#target-select').value;
  if (!target) { toast('请选择目标曲线', 'warning'); return; }
  const fitSettings = collectFitSettings();
  const body = {
    preset: state.currentPresetId,
    target,
    ...fitSettings,
    filters: clamp(Number($('#filters-count').value) || 10, 1, 20),
    fmin: clamp(Number($('#fmin').value) || 100, 20, 20000),
    fmax: clamp(Number($('#fmax').value) || 10000, 20, 20000),
    max_gain_db: clamp(Number($('#max-gain').value) || 6, 0, 15),
    max_q: clamp(Number($('#max-q').value) || 3, 0.1, 10)
  };
  if (body.fmin >= body.fmax) { toast('频带上限必须大于下限', 'warning'); return; }
  $('#btn-autofit').disabled = true;
  try {
    const data = await api('/api/eq/autofit', { method: 'POST', body });
    const bands = normalizeBands(data.bands || []);
    const warnings = Array.isArray(data.warnings) ? data.warnings : (data.warnings ? [String(data.warnings)] : []);
      state.draftBands = normalizeBands(data.bands || []);
      state.draftPreamp = Number(data.preamp_db ?? data.preamp ?? 0) || 0;
      state.previewBands = clone(state.draftBands);
      state.previewPreamp = state.draftPreamp;
      state.previewLabel = '自动拟合结果';
      state.previewFitSettings = {
        filters: body.filters,
        fmin: body.fmin,
        fmax: body.fmax,
        max_gain_db: body.max_gain_db,
        max_q: body.max_q,
        engine: body.engine || 'quick',
        auto_shelf: !!body.auto_shelf,
        hi_fidelity: !!body.hi_fidelity,
        smooth: !!body.smooth,
        sharpness_penalty: !!body.sharpness_penalty,
        sanitize_bands: !!body.sanitize_bands,
        weight_profile: body.weight_profile || 'none',
        auto_filters: !!body.auto_filters,
        target_rms: body.target_rms,
        allow_cross_rig_hf: !!body.allow_cross_rig_hf,
        de_rig: !!body.de_rig,
        target_adjust: body.target_adjust
      };
      renderChart();
      renderBands();
      setDirty(isDirty());
      const box = $('#autofit-result');
      box.classList.remove('hidden');
      let html = '';
      const rigInfo = data.rig || {};
      if (data.fmax_used != null && (data.fmax_clamped || data.fmax_reason)) {
        let reasonText = '';
        if (data.fmax_clamped) reasonText = '已收敛 · 跨 rig';
        else if (data.fmax_reason === 'cross-rig') reasonText = '跨 rig（用户 fmax 本就不超过 7000）';
        else if (data.fmax_reason === 'cross-rig-allowed') reasonText = '跨 rig · 用户已允许高频';
        else reasonText = String(data.fmax_reason || '');
        html += '<div class="muted">fmax_used: ' + Number(data.fmax_used).toFixed(0) + ' Hz'
          + (reasonText ? '（' + escapeHtml(reasonText) + '）' : '')
          + (rigInfo.device_rig ? ' · 设备 rig ' + escapeHtml(rigInfo.device_rig) : '')
          + (rigInfo.target_rig ? ' · 目标 rig ' + escapeHtml(rigInfo.target_rig) : '')
          + '</div>';
      }
      html += (warnings.length ? '<div class="warn">' + warnings.map(escapeHtml).join('<br>') + '</div>' : '');
      if (Array.isArray(data.auto_filter_suggestions) && data.auto_filter_suggestions.length) {
        html += '<div class="res-title">自动段数建议</div><ul class="suggestion-list">' + data.auto_filter_suggestions.map((s, idx) => {
          return '<li><button class="btn btn-small" data-suggestion-index="' + idx + '">' + s.filters + ' 段</button> RMS ' + Number(s.rms_db || 0).toFixed(2) + ' dB' + (s.weighted_rms_db != null ? ' / 加权 ' + Number(s.weighted_rms_db || 0).toFixed(2) : '') + ' Preamp ' + Number(s.preamp_db || 0).toFixed(1) + ' dB</li>';
        }).join('') + '</ul>';
      }
      html += (bands.length ? '<ul class="result-list">' + bands.map((b, i) => {
        return '<li>' + (i + 1) + '. ' + b.type + ' ' + Math.round(b.freq) + 'Hz ' + (b.gain >= 0 ? '+' : '') + b.gain.toFixed(1) + 'dB Q' + b.q.toFixed(2) + '</li>';
      }).join('') + '</ul>' : '<div class="muted">无拟合结果</div>');
      box.innerHTML = html;
      box.querySelectorAll('[data-suggestion-index]').forEach(btn => {
        btn.addEventListener('click', () => {
          const sug = data.auto_filter_suggestions[Number(btn.dataset.suggestionIndex)];
          if (!sug || !sug.bands) return;
          state.draftBands = normalizeBands(sug.bands || []);
          state.draftPreamp = Number(sug.preamp_db ?? 0) || 0;
          state.previewBands = clone(state.draftBands);
          state.previewPreamp = state.draftPreamp;
          state.previewLabel = '自动拟合结果 (' + sug.filters + ' 段)';
          state.previewFitSettings = Object.assign({}, state.previewFitSettings, { filters: sug.filters });
          renderBands();
          renderChart();
          setDirty(isDirty());
          toast('已采用 ' + sug.filters + ' 段结果', 'success', 1500);
        });
      });
      updateControls();
    } catch (e) {
      toast('自动拟合失败: ' + e.message, 'error');
    } finally {
      $('#btn-autofit').disabled = !state.online || state.currentPresetId == null;
    }
  }

function adoptPreview() {
  if (!state.previewBands || state.previewBands.length === 0) return;
  state.draftBands = clone(state.previewBands);
  state.draftPreamp = state.previewPreamp || 0;
  state.previewBands = null;
  state.previewPreamp = 0;
  state.previewLabel = '';
  state.draftFitSettings = state.previewFitSettings || null;
  state.previewFitSettings = null;
  renderBands();
  renderChart();
  setDirty(isDirty());
  
  toast('预览已采用为草稿', 'success', 1500);
}

/* =========================================================================
 * Install / uninstall / modals / SSE
 * ====================================================================== */
async function onRestartAdmin() {
  if (state.apoInfo.elevated) {
    toast('当前已是管理员模式', 'success', 2000);
    return;
  }
  const ok = await confirmDialog(
    '管理员模式重启',
    '将尝试以管理员权限重启后端服务。继续？'
  );
  if (!ok) return;
  try {
    await api('/api/admin/restart-elevated', { method: 'POST', body: {} });
  } catch (_) {
    // 页面自动重连
  }
}

/* =========================================================================
 * 閺堝秴濮熼悽鐔锋嚒閸涖劍婀￠敍姘粻濮?/ 闁插秴鎯庨敍鍫ャ€婇柈銊﹀瘻闁界礆
 * ====================================================================== */
async function onServiceStop() {
  if (!state.online) { toast('服务未运行', 'warning', 1800); return; }
  const ok = await confirmDialog(
    '停止服务',
    '停止当前后端进程。页面将会断开，需在本机手动启动（start-webui.ps1）'
  );
  if (!ok) return;
  try {
    await api('/api/admin/stop', { method: 'POST', body: {} });
  } catch (_) {
    // 閸氬海閸欏厴瀹告彃婀崫宥呯安閸氬海鐝涢崚濠氣偓鈧崙鐚寸礉閹舵盯鏁婄憴鍡曡礋瀹告彃浠犲?
  }
  state.online = false;
  updateControls();
  $('#overlay-stopped').classList.remove('hidden');
}

async function onServiceRestart() {
  if (!state.online) { toast('服务未运行', 'warning', 1800); return; }
  const ok = await confirmDialog(
    '重启服务',
    '重启当前后端进程，页面会自动重连，约 3~5 秒'
  );
  if (!ok) return;
  try {
    await api('/api/admin/restart', { method: 'POST', body: {} });
  } catch (_) {
    // 閺冄嗙箻缁嬪褰查懗钘夊嚒閸忓牊鏌囧鈧敍灞界潣濮濓絽鐖?
  }
  $('#overlay-restarting').classList.remove('hidden');
  // 鏉?/api/status閿涙碍婀囬崝鈩冧划婢跺秴鎮楅懛濮╅崚閿嬫煀妞ょ敻娼?
  const deadline = Date.now() + 25000;
  const tick = async () => {
    if (Date.now() > deadline) {
    toast('服务重启失败', 'error', 6000);
      toast('重启服务失败', 'error', 6000);
      return;
    }
    try {
      const resp = await fetch('/api/status', { method: 'GET', cache: 'no-store' });
      if (resp && resp.ok) {
        window.location.reload();
        return;
      }
    } catch (_) { /* 閺堝秴濮熼張姘ㄧ紒绱濈紒褏鐢绘潪 */ }
    setTimeout(tick, 1200);
  };
  setTimeout(tick, 1500);
}
async function onInstall() {
  if (!state.online) return;
    '重启当前后端进程，页面会自动重连，约 3~5 秒'
  if (!ok) return;
  try {
    const data = await api('/api/admin/install', { method: 'POST', body: {} });
    state.apoInfo = data;
    toast('APO 配置已接管', 'success');
    toast('APO 配置已接管', 'success');
  } catch (e) {
    toast('安装失败: ' + e.message, 'error');
  }
}

async function onUninstall() {
  if (!state.online) return;
  const ok = await confirmDialog('卸载 APO', '将回退 APO 配置接管，恢复 config.txt.bak-headphonelab');
  if (!ok) return;
  try {
    const data = await api('/api/admin/uninstall', { method: 'POST', body: {} });
    state.apoInfo = data;
    toast('已卸载 APO 配置', 'success');
    toast('APO 配置已接管', 'success');
  } catch (e) {
    toast("回退失败: ${e.message}", 'error');
  }
}

function updateCurveImportCategoryVisibility() {
  const field = $('#target-category-field');
  if (!field) return;
  const isTarget = $('#curve-type').value === 'target';
  field.classList.toggle('hidden', !isTarget);
}

function openCurveImportModal() {
  $('#curve-name').value = '';
  $('#curve-text').value = '';
  $('#curve-kind').value = '';
  const catSel = $('#curve-target-category');
  if (catSel) catSel.value = 'headphone';
  updateCurveImportCategoryVisibility();
  openModal('#modal-import-curve');
}

async function confirmCurveImport() {
  const curve_type = $('#curve-type').value;
  const name = $('#curve-name').value.trim();
  const text = $('#curve-text').value.trim();
  if (!name || !text) { toast('请填写名称和曲线数据', 'warning'); return; }
  try {
    await api('/api/curves/import', { method: 'POST', body: {
      curve_type,
      name,
      text,
      kind: $('#curve-kind').value,
      category: curve_type === 'target' ? $('#curve-target-category').value : undefined,
      align: $('#curve-align').checked,
    } });
    closeModal('#modal-import-curve');
    await loadDevices();
    await loadTargets();
state.deviceCurveCache = {};
    state.targetCurveCache = {};
    if (curve_type === 'device') {
      const p = currentPreset();
      if (p) await loadDeviceCurve(p.device_id);
    }
    if (curve_type === 'target') {
      await loadTargetCurve(state.targetCurveId);
    }
    toast('曲线导入成功', 'success');
    toast('曲线导入成功', 'success');
  } catch (e) {
    toast("导入失败: ${e.message}", 'error');
  }
}

function openModal(sel) {
  $(sel).classList.remove('hidden');
}
function closeModal(sel) {
  $(sel).classList.add('hidden');
}

function confirmDialog(title, text) {
  return new Promise((resolve) => {
    $('#confirm-title').textContent = title;
    $('#confirm-text').textContent = text;
    $('#modal-confirm').classList.remove('hidden');
    const yesBtn = $('#btn-confirm-yes');
    const done = (result) => {
      yesBtn.onclick = null;
      $$('#modal-confirm [data-close-modal]').forEach(b => b.onclick = null);
      $('#modal-confirm').classList.add('hidden');
      resolve(result);
    };
    yesBtn.onclick = () => done(true);
    $$('#modal-confirm [data-close-modal]').forEach(b => b.onclick = () => done(false));
  });
}

async function fullReload() {
  await Promise.all([
    loadStatus(),
    loadDevices(),
    loadTargets(),
  ]);
  await loadPresets(state.currentPresetId);
  await loadPresetData(state.currentPresetId, { keepDraft: false });
}

function initSSE() {
  try {
    const es = new EventSource('/api/events');
    es.onopen = () => { state.sseActive = true; };
    es.onerror = () => { state.sseActive = false; };
    es.addEventListener('preset_activated', () => {
      loadStatus().catch(() => {});
      loadPresets(state.currentPresetId).catch(() => {});
    });
    es.addEventListener('preset_changed', () => {
      loadStatus().catch(() => {});
      loadPresets(state.currentPresetId).catch(() => {});
    });
    es.addEventListener('eq_applied', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.preset && data.preset !== state.currentPresetId) return;
        loadPresetData(state.currentPresetId, { keepDraft: true }).catch(() => {});
      } catch (_) {}
    });
    es.addEventListener('apo_state', () => {
      loadStatus().catch(() => {});
    });
  } catch (_) {
    state.sseActive = false;
  }
}

/* =========================================================================
 * Event wiring
 * ====================================================================== */
function wireEvents() {
  $('#btn-preset-add').addEventListener('click', onAddPreset);
  $('#btn-confirm-add-preset').addEventListener('click', confirmAddPreset);
$('#btn-confirm-rename-preset').addEventListener('click', confirmRenamePreset);

  const serviceRestartBtn = $('#btn-service-restart');
  if (serviceRestartBtn) serviceRestartBtn.addEventListener('click', onServiceRestart);
  const serviceStopBtn = $('#btn-service-stop');
  if (serviceStopBtn) serviceStopBtn.addEventListener('click', onServiceStop);
  const stoppedCloseBtn = $('#btn-stopped-close');
  if (stoppedCloseBtn) stoppedCloseBtn.addEventListener('click', () => $('#overlay-stopped').classList.add('hidden'));
  const helpBtn = $('#btn-help');
  if (helpBtn) helpBtn.addEventListener('click', openHelpManual);

  $('#device-select').addEventListener('change', (e) => onDeviceChange(e.target.value));
    $('#target-select').addEventListener('change', (e) => onTargetChange(e.target.value));
    $('#target-select-main').addEventListener('change', (e) => onTargetChange(e.target.value));
    const fitEngineSel = $('#fit-engine');
    if (fitEngineSel) {
      fitEngineSel.addEventListener('change', updateFitEngineControls);
      updateFitEngineControls();
    }
  const autoFitSwitch = $('#auto-fit-switch');
  if (autoFitSwitch) {
    autoFitSwitch.addEventListener('change', async (e) => {
      state.autoFitEnabled = e.target.checked;
      if (state.autoFitEnabled) await runAutoFitAndAdopt();
    });
  }
  $('#btn-import-curve').addEventListener('click', openCurveImportModal);
    $('#curve-type').addEventListener('change', updateCurveImportCategoryVisibility);
$('#btn-autoeq-search').addEventListener('click', onAutoEqSearch);
  const autoeqInput = $('#autoeq-search-input');
  if (autoeqInput) {
    autoeqInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') onAutoEqSearch();
    });
  }


  

  const canvas = $('#eq-canvas');
  canvas.addEventListener('mousedown', onCanvasMouseDown);
  canvas.addEventListener('mousemove', onCanvasMouseMove);
  canvas.addEventListener('mouseup', onCanvasMouseUp);
  canvas.addEventListener('mouseleave', onCanvasLeave);
  canvas.addEventListener('wheel', onCanvasWheel, { passive: false });
    canvas.addEventListener('dblclick', onCanvasDblClick);
    canvas.addEventListener('click', onCanvasClick);

  $$('.legend-toggle input').forEach(input => {
    input.addEventListener('change', renderChart);
  });
  ['display-normalization', 'display-smoothing', 'residual-mode'].forEach(id => {
    const el = $(id);
    if (el) el.addEventListener('change', renderChart);
  });

  $('#btn-add-band').addEventListener('click', addBand);
  $('#preamp-input').addEventListener('change', (e) => {
    state.draftPreamp = clamp(Number(e.target.value) || 0, -30, 30);
    setDirty(isDirty());
        
    renderChart();
updateEqRisk();
  });

  // manual EQ sliders
  const manualBandSelect = $('#manual-band-select');
  if (manualBandSelect) {
    manualBandSelect.addEventListener('change', (e) => {
      state.manualBandIndex = Number(e.target.value) || 0;
      renderManualEq();
    });
    $('#manual-type-select').addEventListener('change', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.type = normalizeBandType(e.target.value);
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
    $('#manual-freq-slider').addEventListener('input', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.freq = sliderToFreq(e.target.value);
      $('#manual-freq-input').value = Math.round(b.freq);
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
    $('#manual-freq-input').addEventListener('change', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.freq = clamp(Number(e.target.value) || 1000, 20, 20000);
      $('#manual-freq-slider').value = freqToSlider(b.freq);
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
    $('#manual-gain-slider').addEventListener('input', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.gain = clamp(Number(e.target.value) || 0, -15, 15);
      $('#manual-gain-input').value = b.gain.toFixed(1);
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
    $('#manual-gain-input').addEventListener('change', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.gain = clamp(Number(e.target.value) || 0, -15, 15);
      $('#manual-gain-slider').value = b.gain;
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
    $('#manual-q-slider').addEventListener('input', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.q = clamp(Number(e.target.value) || 1, 0.1, 10);
      $('#manual-q-input').value = b.q.toFixed(2);
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
    $('#manual-q-input').addEventListener('change', (e) => {
      const b = state.draftBands[state.manualBandIndex];
      if (!b) return;
      b.q = clamp(Number(e.target.value) || 1, 0.1, 10);
      $('#manual-q-slider').value = b.q;
      renderBands();
      renderChart();
      setDirty(isDirty());
        
    });
  }

  const origToggle = $('#original-switch');
  if (origToggle) origToggle.addEventListener('change', (e) => onOriginalSwitch(e.target.checked));
  const saveNotesBtn = $('#btn-save-notes');
  if (saveNotesBtn) saveNotesBtn.addEventListener('click', saveNotes);
  const exportConfigBtn = $('#btn-export-config');
  if (exportConfigBtn) exportConfigBtn.addEventListener('click', syncExportConfig);

  $('#btn-parse').addEventListener('click', onParse);
  $('#btn-adopt-import').addEventListener('click', adoptPreview);
  $('#btn-autofit').addEventListener('click', onAutofit);
  $('#fmax').addEventListener('input', updateHfWarning);
  $('#btn-adopt-autofit').addEventListener('click', adoptPreview);

  $('#btn-apply').addEventListener('click', onApply);
  $('#btn-discard').addEventListener('click', onDiscard);
  $('#btn-revert').addEventListener('click', onRevert);

  $('#btn-confirm-import-curve').addEventListener('click', confirmCurveImport);

  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.tab-btn').forEach(b => b.classList.remove('active'));
      $$('.tab-panel').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      $('#tab-' + tab).classList.add('active');
    });
  });

  $$('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal');
      if (modal) modal.classList.add('hidden');
    });
  });

  window.addEventListener('resize', renderChart);
}

async function init() {
  wireEvents();
  await Promise.all([
    loadStatus(),
    loadDevices(),
    loadTargets(),
  ]);
  await loadPresets(null);
  await loadPresetData(state.currentPresetId, { keepDraft: false });
  initSSE();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

