/* =========================================================================
 * PEQ WebUI · 帮助手册模块（全新实现，自包含）
 * ---------------------------------------------------------------------
 * 功能：
 *   - 点击顶栏「❓ 帮助」→ 拉取 /api/manual → 章节化渲染到弹窗
 *   - H1 = 手册大标题（不折叠）；H2 = 章（默认折叠，点击展开）
 *   - H3~H6 = 章内小节，嵌套折叠卡片，同样默认折叠
 *   - 轻量 Markdown 渲染：标题 / 列表（含嵌套续行）/ 表格 / 围栏代码 /
 *     引用 / 行内代码与粗斜体；无第三方依赖
 * 依赖：仅原生 DOM；openModal 存在则复用，否则直接切换 .hidden
 * ====================================================================== */
(function () {
  'use strict';

  const API_PATH = '/api/manual';
  let cache = null; // { name, text }

  /* ---------- 基础工具 ---------- */
  function esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /* 行内 Markdown：先整体转义，再做行内标记替换 */
  function inlineMd(text) {
    let t = esc(text);
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
    return t;
  }

  /* ---------- 围栏代码块：去公共缩进（列表项内代码块常带继承缩进） ---------- */
  function dedent(code) {
    const ls = String(code).split('\n');
    let min = Infinity;
    for (const l of ls) {
      if (!l.trim()) continue;
      const ind = l.match(/^[ \t]*/)[0].length;
      if (ind < min) min = ind;
    }
    if (!isFinite(min) || min === 0) return String(code);
    return ls.map(l => l.slice(min)).join('\n');
  }

  /* ---------- 表格 ---------- */
  function parseCells(line) {
    return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
  }
  function isDividerRow(cells) {
    return cells.length > 0 && cells.every(c => /^:?-{2,}:?$/.test(c));
  }
  function renderTable(rows) {
    let h = '<div class="mn-tbl-wrap"><table>';
    rows.forEach((cells, ri) => {
      if (isDividerRow(cells)) return;
      const tag = ri === 0 ? 'th' : 'td';
      h += '<tr>' + cells.map(c => `<${tag}>${inlineMd(c)}</${tag}>`).join('') + '</tr>';
    });
    return h + '</table></div>';
  }

  /* ---------- 列表（项内可含文本/代码块/表格分段） ---------- */
  function renderList(list) {
    const tag = list.ordered ? 'ol' : 'ul';
    let h = `<${tag}>`;
    for (const item of list.items) {
      h += '<li>' + item.segs.map(seg => {
        if (seg.t === 'text') return seg.parts.map(inlineMd).join('<br>');
        if (seg.t === 'fence') return `<pre><code>${esc(seg.code)}</code></pre>`;
        if (seg.t === 'table') return renderTable(seg.rows);
        return '';
      }).join('') + '</li>';
    }
    return h + `</${tag}>`;
  }

  /* ---------- 主渲染器 ----------
   * 策略：先整体提取围栏代码块为占位符，再逐行扫描：
   *   - H1 首个 → 文档大标题；H2~H6 → details.mn-sec 折叠卡片（按层级嵌套）
   *   - 列表项支持懒续行 / 缩进续行 / 项内围栏代码 / 项内表格
   *   - 空行延迟裁决（peek 下一非空行），避免切断列表续行
   */
  function renderMarkdown(src) {
    const fences = [];
    const withFences = String(src ?? '').replace(/```[^\n]*?\n([\s\S]*?)```/g, (m, code) => {
      fences.push(dedent(code.replace(/\n$/, '')));
      return `\u0000F${fences.length - 1}\u0000`;
    });
    const lines = withFences.split(/\r?\n/);
    const fenceIdxOf = (l) => {
      const m = l.match(/^\s*\u0000F(\d+)\u0000\s*$/);
      return m ? Number(m[1]) : -1;
    };
    const peekNonBlank = (idx) => {
      for (let j = idx; j < lines.length; j++) if (lines[j].trim()) return j;
      return null;
    };

    let html = '';
    const openLevels = [];   // 已打开 details 的标题层级栈
    let para = [];           // 段落/列表项文本行缓冲（原始行）
    let paraInItem = false;  // para 是否归属列表项
    let quote = [];
    let list = null;         // { ordered, items:[{ segs:[] }] }
    let curItem = null;
    let itemTable = null;    // 列表项内表格行缓冲
    let topTable = null;     // 顶层表格行缓冲
    let blankPending = false;

    const flushPara = () => {
      if (!para.length) return;
      if (paraInItem && curItem) {
        const last = curItem.segs[curItem.segs.length - 1];
        if (last && last.t === 'text') last.parts.push(...para);
        else curItem.segs.push({ t: 'text', parts: para.slice() });
      } else {
        html += `<p>${para.map(inlineMd).join('<br>')}</p>`;
      }
      para = [];
    };
    const flushQuote = () => {
      if (!quote.length) return;
      html += `<blockquote>${quote.map(inlineMd).join('<br>')}</blockquote>`;
      quote = [];
    };
    const flushTopTable = () => {
      if (!topTable) return;
      html += renderTable(topTable);
      topTable = null;
    };
    const flushItemTable = () => {
      if (!itemTable) return;
      if (curItem) curItem.segs.push({ t: 'table', rows: itemTable });
      itemTable = null;
    };
    const closeItem = () => { flushItemTable(); flushPara(); curItem = null; };
    const closeList = () => {
      if (!list) return;
      closeItem();
      html += renderList(list);
      list = null;
      paraInItem = false;
    };
    const flushAll = () => { flushQuote(); closeList(); flushTopTable(); flushPara(); };

    /* 空行裁决：遇到空行后的第一个非空行时调用 */
    function applyBlank(idx) {
      if (!blankPending) return;
      blankPending = false;
      if (itemTable) flushItemTable();
      if (topTable) flushTopTable();
      if (quote.length) { flushQuote(); return; }
      if (list && curItem) {
        const nxt = peekNonBlank(idx);
        if (nxt != null) {
          const nl = lines[nxt];
          const nt = nl.trim();
          const cont = /^\s{2,}/.test(nl)
            || fenceIdxOf(nl) >= 0
            || /^\s*\|/.test(nt)
            || /^[-*]\s+/.test(nt)
            || /^\d+\.\s+/.test(nt);
          if (cont) return; // 列表保持打开
        }
        closeList();
        return;
      }
      flushPara();
    }

    const closeDetailsTo = (level) => {
      while (openLevels.length && openLevels[openLevels.length - 1] >= level) {
        html += '</details>';
        openLevels.pop();
      }
    };
    const openDetails = (level, title) => {
      html += `<details class="mn-sec"><summary><span class="mn-h mn-h${level}">${inlineMd(title)}</span></summary>`;
      openLevels.push(level);
    };

    for (let i = 0; i < lines.length; i++) {
      const raw = lines[i];
      const t = raw.trim();

      /* 空行：延迟处理 */
      if (!t) {
        blankPending = true;
        continue;
      }

      /* 围栏代码块（占位符行） */
      const fIdx = fenceIdxOf(raw);
      if (fIdx >= 0) {
        if (itemTable) flushItemTable();
        if (topTable) flushTopTable();
        if (quote.length) flushQuote();
        const code = fences[fIdx] ?? '';
        if (list && curItem) {
          flushPara();
          curItem.segs.push({ t: 'fence', code });
          paraInItem = true;
        } else {
          flushPara();
          html += `<pre><code>${esc(code)}</code></pre>`;
        }
        blankPending = false;
        continue;
      }

      /* 标题 */
      const heading = t.match(/^(#{1,6})\s+(.+)$/);
      if (heading) {
        flushAll();
        blankPending = false;
        const level = heading[1].length;
        closeDetailsTo(level);
        if (level === 1 && openLevels.length === 0) {
          html += `<h1 class="mn-doc-title">${inlineMd(heading[2])}</h1>`;
        } else {
          openDetails(level, heading[2]);
        }
        continue;
      }

      /* 水平线 */
      if (/^(-{3,}|\*{3,})$/.test(t)) {
        flushAll();
        blankPending = false;
        html += '<hr>';
        continue;
      }

      /* 引用 */
      const quoteM = t.match(/^>\s?(.*)$/);
      if (quoteM) {
        if (itemTable) flushItemTable();
        if (topTable) flushTopTable();
        flushPara();
        closeList();
        quote.push(quoteM[1]);
        blankPending = false;
        continue;
      }

      /* 表格行 */
      if (t.startsWith('|')) {
        applyBlank(i);
        if (list && curItem) {
          flushPara();
          if (!itemTable) itemTable = [];
          itemTable.push(parseCells(t));
        } else {
          flushPara();
          flushQuote();
          if (!topTable) topTable = [];
          topTable.push(parseCells(t));
        }
        blankPending = false;
        continue;
      }

      /* 列表项 */
      const bulletM = t.match(/^[-*]\s+(.*)$/);
      const orderedM = t.match(/^(\d+)\.\s+(.*)$/);
      if (bulletM || orderedM) {
        applyBlank(i);
        if (itemTable) flushItemTable();
        if (topTable) flushTopTable();
        if (quote.length) flushQuote();
        flushPara();
        const ordered = !!orderedM;
        const text = ordered ? orderedM[2] : bulletM[1];
        if (!list) {
          list = { ordered, items: [] };
        } else if (list.ordered !== ordered) {
          closeList();
          list = { ordered, items: [] };
        }
        paraInItem = true;
        curItem = { segs: [] };
        list.items.push(curItem);
        curItem.segs.push({ t: 'text', parts: [text] });
        blankPending = false;
        continue;
      }

      /* 行尾粘连的水平线（如 “…权限。---”）：文本 + hr */
      const tailHr = t.match(/^(.+?)\s*-{3,}$/);
      if (tailHr) {
        applyBlank(i);
        para.push(tailHr[1]);
        flushAll();
        blankPending = false;
        html += '<hr>';
        continue;
      }

      /* 普通文本行（懒续行 / 项内续行） */
      applyBlank(i);
      if (list && curItem) {
        para.push(t);
        paraInItem = true;
      } else if (quote.length) {
        quote.push(t);
      } else {
        para.push(t);
        paraInItem = false;
      }
    }

    applyBlank(lines.length);
    flushAll();
    while (openLevels.length) {
      html += '</details>';
      openLevels.pop();
    }
    return html;
  }

  /* ---------- 数据获取 ---------- */
  async function fetchManual(force) {
    if (cache && !force) return cache;
    const resp = await fetch(API_PATH, { cache: 'no-store' });
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const data = await resp.json();
    if (!data || data.ok === false) throw new Error((data && data.error) || '接口返回失败');
    cache = { name: data.name || '', text: data.text || '' };
    return cache;
  }

  /* ---------- 打开手册弹窗 ---------- */
  async function open() {
    const body = document.querySelector('#manual-modal-body');
    const meta = document.querySelector('#manual-modal-meta');
    if (!body) return;
    if (typeof window.openModal === 'function') window.openModal('#modal-help');
    else {
      const modal = document.querySelector('#modal-help');
      if (modal) modal.classList.remove('hidden');
    }
    body.innerHTML = '<div class="mn-loading">正在加载手册…</div>';
    if (meta) meta.textContent = '';
    try {
      const data = await fetchManual();
      body.innerHTML = renderMarkdown(data.text);
      const chapters = (data.text.match(/^##\s/gm) || []).length;
      if (meta) meta.textContent = (data.name ? data.name + ' · ' : '') + chapters + ' 章（点击章节标题展开）';
    } catch (e) {
      body.innerHTML = '<div class="mn-error">手册加载失败: ' + esc(e && e.message ? e.message : e) + '</div>';
    }
  }

  if (typeof window !== 'undefined') {
    window.PeqManual = {
      open,
      render: renderMarkdown,
      reload: () => { cache = null; return fetchManual(true); },
    };
  }

  /* Node 环境导出（供自动化测试使用，浏览器中无副作用） */
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderMarkdown, fetchManual, _resetCache: () => { cache = null; } };
  }
})();
