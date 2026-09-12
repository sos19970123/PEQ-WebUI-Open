/* tools/test_manual_render.js — 手册渲染器冒烟测试（Node 直跑）
 * 用法: py 无关，直接 node tools/test_manual_render.js
 * 校验 webui/manual.js 对真实《用户操作手册.md》的渲染结果
 */
'use strict';
const fs = require('fs');
const path = require('path');
const Manual = require('../webui/manual.js');

const md = fs.readFileSync(path.join(__dirname, '..', '用户操作手册.md'), 'utf8');
const html = Manual.renderMarkdown(md);

let fails = 0;
function check(name, cond) {
  console.log((cond ? 'PASS' : 'FAIL') + '  ' + name);
  if (!cond) fails++;
}
const count = (s, re) => (s.match(re) || []).length;

/* 章节结构：H1 大标题 + H2~H4 折叠卡片，数量与源文档一致 */
const srcH2 = count(md, /^##\s/gm);
const srcH3 = count(md, /^###\s/gm);
const srcH4 = count(md, /^####\s/gm);
check(`H1 大标题渲染 (1)`, html.includes('mn-doc-title') && html.includes('PEQ WebUI 用户操作手册'));
check(`H2 章节数量一致 (${srcH2})`, count(html, /class="mn-h mn-h2"/g) === srcH2);
check(`H3 小节数量一致 (${srcH3})`, count(html, /class="mn-h mn-h3"/g) === srcH3);
check(`H4 小节数量一致 (${srcH4})`, count(html, /class="mn-h mn-h4"/g) === srcH4);

/* 默认折叠：任何 details 都不带 open 属性 */
check('全部章节默认折叠（无 open 属性）', !/<details[^>]*\sopen/.test(html));

/* 占位符/转义健全性 */
check('无残留围栏占位符', !html.includes('\u0000'));
check('无双重转义', !html.includes('&amp;lt;') && !html.includes('&amp;gt;'));

/* 标签配平 */
check('details 标签配平', count(html, /<details/g) === count(html, /<\/details>/g));
check('列表标签配平', count(html, /<ul>/g) + count(html, /<ol>/g) === count(html, /<\/ul>/g) + count(html, /<\/ol>/g));
check('段落标签配平', count(html, /<p>/g) === count(html, /<\/p>/g));
check('表格标签配平', count(html, /<table>/g) === count(html, /<\/table>/g));

/* 内容类型渲染 */
check('围栏代码块存在', html.includes('<pre><code>'));
check('引用块存在', html.includes('<blockquote>'));
check('表格表头存在', html.includes('<th>'));
check('行内代码存在', html.includes('<code>'));
check('粗体存在', html.includes('<strong>'));

/* 关键难例：列表项内嵌围栏代码（§2 页面说明的三条按钮项） */
check('列表项内嵌代码块', /<li>(?:(?!<\/li>)[\s\S])*<pre><code>cd F:\\Hermes-Deepseek/.test(html));
/* 关键难例：行尾粘连水平线 “…管理员权限。---”（§10 结尾）应渲染为 段落+hr，而非列表 */
check('粘连 --- 渲染为段落+分隔线', /不再需要管理员权限。<\/p><hr>/.test(html));
/* 关键难例：嵌套无序列表（§11.9 “10k 后的峰”表在列表内） */
check('列表项内嵌表格', /<li>(?:(?!<\/li>)[\s\S])*<div class="mn-tbl-wrap">/.test(html));
/* 常用路径表格（§9）渲染 */
check('§9 路径表渲染', html.includes('WebUI 项目') && html.includes('apo-presets'));

console.log(fails === 0 ? '\n全部通过 ✅' : `\n${fails} 项失败 ❌`);
process.exit(fails === 0 ? 0 : 1);
