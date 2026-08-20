#!/usr/bin/env python3
"""Собирает локальный сайт-отчёт по ревью вакансий из report.json.

Результат — самодостаточный site/index.html (данные зашиты внутрь),
открывается двойным кликом, сервер не нужен.

Использование:
    python3 build_site.py [-r report.json] [-o site/index.html]
"""

import argparse
import json
import pathlib

# Страница собрана из двух кусков без внешнего <html>-каркаса: из них строится
# и локальный site/index.html, и версия для публикации по ссылке (--artifact),
# где каркас документа добавляет платформа хостинга.
HEAD_CORE = """<title>Ревью вакансий Авито по гайду</title>
<style>
:root {
  --bg: #f7f5f2; --card: #ffffff; --card-2: #fbfaf8; --ink: #21201d; --ink-2: #6e6b64;
  --ink-3: #8b887f; --line: #eae7e1; --accent: #0e7cf4; --accent-soft: #e8f2fe;
  --good: #0b8a0b; --good-bg: #e9f7e9; --warn: #8a6206; --warn-bg: #fdf3d9;
  --crit: #c92f2f; --crit-bg: #fbe9e9;
  --t1-bg: #fbe9e9; --t1-txt: #b02f2f; --t2-bg: #fdf3d9; --t2-txt: #8a6206;
  --t3-bg: #e9f7e9; --t3-txt: #0b8a0b;
  --shadow: 0 1px 2px rgba(40, 35, 25, .05), 0 4px 16px rgba(40, 35, 25, .06);
  --shadow-up: 0 2px 4px rgba(40, 35, 25, .07), 0 10px 28px rgba(40, 35, 25, .1);
}
:root[data-theme="dark"] {
  --bg: #171716; --card: #1f1f1e; --card-2: #242423; --ink: #f0efec; --ink-2: #a8a59e;
  --ink-3: #85827b; --line: #34332f; --accent: #4da3ff; --accent-soft: #14304d;
  --good: #4fc36a; --good-bg: #15321c; --warn: #e8b93e; --warn-bg: #38300f;
  --crit: #ff7369; --crit-bg: #421a17;
  --t1-bg: #421a17; --t1-txt: #ff8a80; --t2-bg: #38300f; --t2-txt: #e8b93e;
  --t3-bg: #15321c; --t3-txt: #4fc36a;
  --shadow: 0 1px 2px rgba(0,0,0,.3), 0 4px 16px rgba(0,0,0,.25);
  --shadow-up: 0 2px 4px rgba(0,0,0,.35), 0 10px 28px rgba(0,0,0,.35);
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 14px/1.5 -apple-system, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
  transition: background .2s, color .2s; }
.wrap { max-width: 1440px; margin: 0 auto; padding: 32px 28px 60px; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 6px; }

header.top { margin-bottom: 26px; display: flex; align-items: flex-start; gap: 16px; }
header.top .head { flex: 1; }
.brandline { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.dots { display: inline-flex; gap: 4px; }
.dots i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.dots i:nth-child(1) { background: #965eeb; } .dots i:nth-child(2) { background: #00aaff; }
.dots i:nth-child(3) { background: #04e061; } .dots i:nth-child(4) { background: #ff4053; }
.eyebrow { color: var(--ink-3); font-size: 12px; font-weight: 700; letter-spacing: .09em;
  text-transform: uppercase; }
h1 { font-size: 34px; line-height: 1.15; margin: 0 0 10px; font-weight: 800;
  letter-spacing: -.025em; text-wrap: balance; }
h1 .hl { background: linear-gradient(transparent 62%, rgba(4, 224, 97, .35) 62%, rgba(4, 224, 97, .35) 94%, transparent 94%); }
.sub { color: var(--ink-2); max-width: 720px; }
.upd { color: var(--ink-3); font-size: 12.5px; margin-top: 8px; }
.upd b { color: var(--ink-2); font-weight: 650; }
.head-btns { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
dialog.tiers { border: 1px solid var(--line); border-radius: 20px; background: var(--card);
  color: var(--ink); padding: 24px 28px; max-width: 520px; box-shadow: var(--shadow-up); }
dialog.tiers::backdrop { background: rgba(20, 18, 14, .45); }
dialog.tiers h3 { margin: 0 0 10px; font-size: 17px; }
dialog.tiers ul { margin: 10px 0; padding-left: 0; list-style: none; }
dialog.tiers li { margin-bottom: 8px; color: var(--ink-2); }
dialog.tiers li .tierpill { margin-right: 8px; }
dialog.tiers p { color: var(--ink-2); margin: 10px 0 0; }
dialog.tiers .close { background: var(--accent); color: #fff; border: none; border-radius: 30px;
  padding: 9px 20px; font: inherit; font-weight: 700; cursor: pointer; margin-top: 16px; }
.criteria-dlg { width: min(780px, 92vw); max-height: 80vh; overflow: auto; }
.criteria-dlg .criteria-list { display: grid; gap: 10px; margin-top: 14px; }
.criteria-dlg .criterion-def { border: 1px solid var(--line); border-radius: 12px; padding: 11px 13px; }
.criteria-dlg .criterion-def h4 { margin: 0 0 5px; font-size: 13px; }
.criteria-dlg .criterion-def p { margin: 0; font-size: 12.5px; line-height: 1.45; }
.criteria-dlg .badge { margin-right: 5px; }
.whatis { background: none; border: none; padding: 0; font: inherit; font-size: 12px;
  color: var(--accent); cursor: pointer; text-decoration: underline; }
dialog.upddlg { width: min(680px, 92vw); }
.updlog { background: var(--bg); border: 1px solid var(--line); border-radius: 12px;
  padding: 12px 14px; height: 280px; overflow: auto; margin: 12px 0 0; white-space: pre-wrap;
  overflow-wrap: anywhere; color: var(--ink-2);
  font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.updlog .okline { color: var(--good); font-weight: 700; }
@keyframes pulse { 50% { opacity: .45; } }
.upd-running { animation: pulse 1.2s ease-in-out infinite; }
.theme-btn { background: var(--card); border: 1px solid var(--line); border-radius: 30px;
  padding: 8px 14px; font: inherit; font-weight: 650; color: var(--ink-2); cursor: pointer;
  box-shadow: var(--shadow); white-space: nowrap; }
.theme-btn:hover { color: var(--ink); box-shadow: var(--shadow-up); }

.status-wrap { margin: 26px 0 18px; }
.status-hero { margin-top: 12px; padding: 30px 34px; min-height: 294px; border-radius: 24px;
  color: var(--ink); box-shadow: var(--shadow); border: 1px solid var(--line); }
.status-hero.red { background: linear-gradient(135deg, #fce9e7, #f8dedd); border-color: #f2c9c5; }
.status-hero.yellow { background: linear-gradient(135deg, #fff5df, #fceed1); border-color: #f2dfb6; }
.status-hero.green { background: linear-gradient(135deg, #eaf7ef, #e2f2e9); border-color: #cde7d7; }
.status-hero.red .status-kicker, .status-hero.red .status-frequent li b { color: #b53636; }
.status-hero.yellow .status-kicker, .status-hero.yellow .status-frequent li b { color: #8a6206; }
.status-hero.green .status-kicker, .status-hero.green .status-frequent li b { color: #16734c; }
:root[data-theme="dark"] .status-hero { color: #f0efec; border-color: rgba(255,255,255,.12); }
:root[data-theme="dark"] .status-hero.red { background: linear-gradient(135deg, #3b2222, #30201f); }
:root[data-theme="dark"] .status-hero.yellow { background: linear-gradient(135deg, #393015, #302914); }
:root[data-theme="dark"] .status-hero.green { background: linear-gradient(135deg, #17352a, #152f28); }
:root[data-theme="dark"] .status-hero.red .status-kicker, :root[data-theme="dark"] .status-hero.red .status-frequent li b { color: #ff9b92; }
:root[data-theme="dark"] .status-hero.yellow .status-kicker, :root[data-theme="dark"] .status-hero.yellow .status-frequent li b { color: #f2c65f; }
:root[data-theme="dark"] .status-hero.green .status-kicker, :root[data-theme="dark"] .status-hero.green .status-frequent li b { color: #76db98; }
:root[data-theme="dark"] .status-hero .status-meta, :root[data-theme="dark"] .status-hero .status-frequent .label { color: #c4c1ba; }
:root[data-theme="dark"] .status-hero .status-secondary { color: #f0efec; background: rgba(255,255,255,.06); border-color: rgba(255,255,255,.22); }
:root[data-theme="dark"] .status-hero .status-frequent { border-color: rgba(255,255,255,.16); }
.status-kicker { font-weight: 800; font-size: 12px; letter-spacing: .13em; text-transform: uppercase; opacity: .9; }
.status-hero h2 { font-size: clamp(26px, 4vw, 42px); line-height: 1.13; letter-spacing: -.03em;
  margin: 12px 0 10px; max-width: 900px; }
.status-meta { font-size: 15px; color: var(--ink-2); max-width: 880px; }
.status-actions { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 24px; }
.status-actions button { border-radius: 14px; padding: 13px 18px; font: inherit; font-weight: 800; cursor: pointer; }
.status-primary { color: var(--ink); background: #fff; border: 1px solid #fff; }
.status-secondary { color: var(--ink); background: rgba(255,255,255,.55); border: 1px solid rgba(70,60,40,.15); }
.status-frequent { border-top: 1px solid rgba(70,60,40,.13); margin-top: 26px; padding-top: 17px; }
.status-frequent .label { display: block; color: var(--ink-2); font-size: 13px; margin-bottom: 7px; }
.status-frequent ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }
.status-frequent li b { display: inline-block; min-width: 38px; font-size: 22px; }
@media (max-width: 680px) { .status-hero { padding: 24px 20px; } }

.panel { background: var(--card); border: 1px solid var(--line); border-radius: 20px;
  box-shadow: var(--shadow); padding: 14px 18px; margin-bottom: 16px; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.filters input[type=search], .filters select { background: var(--bg); color: var(--ink);
  border: 1px solid var(--line); border-radius: 30px; padding: 9px 14px; font: inherit;
  outline: none; transition: border-color .15s, box-shadow .15s; max-width: 100%; }
.filters input[type=search] { min-width: 180px; flex: 1 1 180px; }
.filters :is(input, select):focus { border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft); }
.filters label.chk { display: flex; gap: 7px; align-items: center; color: var(--ink-2);
  cursor: pointer; padding: 6px 2px; }
.filters .spacer { flex: 1; }
.legend { display: flex; gap: 16px; flex-wrap: wrap; color: var(--ink-2); font-size: 12.5px;
  align-items: center; }

.toolbar { display: flex; align-items: center; gap: 14px; margin: 0 4px 10px; flex-wrap: wrap; }
.table-title { margin: 0; font-size: 22px; letter-spacing: -.02em; }
.count { color: var(--ink-2); font-size: 12.5px; }
.toolbar .grow { flex: 1; }
.tbtn { background: var(--card); color: var(--ink-2); border: 1px solid var(--line);
  border-radius: 30px; padding: 6px 14px; font: inherit; font-size: 12.5px; font-weight: 650;
  cursor: pointer; }
.tbtn:hover { color: var(--ink); box-shadow: var(--shadow); }

.tablebox { overflow: visible; background: var(--card); border: 1px solid var(--line);
  border-radius: 20px; box-shadow: var(--shadow); }
table { border-collapse: collapse; width: 100%; }
th, td { padding: 10px 10px; border-bottom: 1px solid var(--line); text-align: left;
  white-space: nowrap; }
tbody tr:last-child td { border-bottom: none; }
th { position: sticky; top: 0; z-index: 2; background: var(--card); font-weight: 650;
  font-size: 13px; letter-spacing: .01em; color: var(--ink-2);
  cursor: pointer; user-select: none; border-bottom: 1px solid var(--line);
  vertical-align: bottom; box-shadow: 0 1px 0 var(--line); }
th:hover { color: var(--ink); }
th.crit-col, td.crit-col { text-align: center; }
td.crit-col { padding: 8px 4px; }
th.crit-col { height: 350px; padding: 10px 4px 8px; font-size: 13px; }
th.crit-col .vh { writing-mode: vertical-rl; transform: rotate(180deg);
  display: inline-block; }
th .arrow { font-size: 9px; color: var(--accent); }
td.vac { white-space: normal; min-width: 260px; }
td.vac .chev { color: var(--ink-3); font-size: 10px; margin-right: 6px; }
td.vac a { color: var(--ink); font-weight: 650; text-decoration: none; }
td.vac a:hover { color: var(--accent); }
td.vac .meta { color: var(--ink-2); font-size: 12px; margin-top: 2px; }
th.recruiter-col, td.recruiter-col { min-width: 150px; white-space: normal; }
.recruiter-pill { display: inline-flex; align-items: center; padding: 4px 9px; border-radius: 20px;
  background: var(--accent-soft); color: var(--accent); font-size: 11.5px; font-weight: 700;
  white-space: nowrap; }
.recruiter-pill.empty { background: var(--card-2); color: var(--ink-3); font-weight: 600; }
.badges { display: inline-flex; gap: 6px; margin-left: 6px; vertical-align: 1px; }
.badge { font-size: 10.5px; font-weight: 700; border-radius: 20px; padding: 1px 8px; }
.badge.crit { background: var(--crit-bg); color: var(--crit); }
.badge.warn { background: var(--warn-bg); color: var(--warn); }
.badge.missing { background: var(--crit-bg); color: var(--crit); }
.badge.closed { background: var(--line); color: var(--ink-2); }
tr.row.closed td.vac a { color: var(--ink-2); }
.closednote { color: var(--crit); font-weight: 650; }
.tbtn.danger:hover { color: var(--crit); border-color: var(--crit); }
tr.row { transition: background .12s; }
tr.row:hover td { background: var(--card-2); cursor: pointer; }
tr.row.open td { background: var(--accent-soft); border-bottom-color: transparent; }

.chip { display: inline-flex; align-items: center; justify-content: center;
  width: 24px; height: 24px; border-radius: 50%; font-size: 12px; font-weight: 800; }
.chip.green { background: var(--good-bg); color: var(--good); }
.chip.yellow { background: var(--warn-bg); color: var(--warn); }
.chip.red { background: var(--crit-bg); color: var(--crit); }

tr.details td { white-space: normal; background: var(--card-2); padding: 14px; }
.detail-inner { position: sticky; left: 14px; max-width: calc(100vw - 110px); }
.detail-head { display: flex; align-items: center; gap: 12px; margin: 2px 2px 12px;
  color: var(--ink-2); font-size: 12.5px; flex-wrap: wrap; }
.detail-head a { color: var(--accent); }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 12px; }
.dcard { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
  padding: 12px 14px; }
.dcard h4 { margin: 0 0 8px; font-size: 13px; display: flex; gap: 8px; align-items: center; }
.dcard ul { margin: 0; padding-left: 18px; }
.dcard li { margin-bottom: 6px; color: var(--ink-2); }
.dcard li.red::marker { color: var(--crit); }
.dcard li.yellow::marker { color: var(--warn); }
.dcard li .badge { margin-right: 5px; vertical-align: 1px; }
.dcard .group-title { color: var(--ink); font-weight: 650; }
.dcard .group-details { margin: 6px 0 2px; padding-left: 18px; }
.dcard .group-details li { margin-bottom: 4px; font-size: 12.5px; }
.jump { display: inline-block; margin-left: 6px; color: var(--accent); font-size: 11.5px;
  font-weight: 650; text-decoration: none; white-space: nowrap; border: 1px solid var(--line);
  border-radius: 20px; padding: 0 8px; }
.jump:hover { border-color: var(--accent); background: var(--accent-soft); }
.dcard.empty { color: var(--ink-2); display: flex; align-items: center; gap: 8px; }
.empty-state { text-align: center; padding: 42px 20px !important; color: var(--ink-2);
  white-space: normal; }
.empty-state button { background: var(--accent); color: #fff; border: none;
  border-radius: 30px; padding: 9px 18px; font: inherit; font-weight: 700;
  cursor: pointer; margin-top: 10px; }
footer { color: var(--ink-2); font-size: 12px; margin-top: 22px; max-width: 860px; }
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; animation: none !important; }
}
@media (max-width: 760px) {
  /* На узком экране важнее горизонтальная прокрутка; закрепление работает на desktop. */
  .tablebox { overflow-x: auto; }
}
</style>
"""

BODY_CORE = """<div class="wrap">
<header class="top">
  <div class="head">
    <div class="brandline"><span class="dots"><i></i><i></i><i></i><i></i></span>
      <span class="eyebrow">career.avito.com</span></div>
    <h1>Ревью вакансий <span class="hl">по гайду</span></h1>
    <div class="sub">Проверка описаний вакансий на соответствие гайду</div>
    <div class="upd" id="updline"></div>
  </div>
  <div class="head-btns">
    <button class="theme-btn" id="updBtn" type="button" hidden aria-haspopup="dialog">⟳ Обновить данные</button>
    <button class="theme-btn" id="criteriaBtn" type="button" aria-haspopup="dialog">ⓘ Критерии</button>
    <button class="theme-btn" id="themeBtn" type="button" aria-label="Переключить тему">◐ Тема</button>
  </div>
</header>

<dialog class="tiers upddlg" id="updDlg" aria-labelledby="updDlgTitle">
  <h3 id="updDlgTitle">Обновление данных</h3>
  <p id="updDlgDesc"></p>
  <pre class="updlog" id="updLog"></pre>
  <button class="close" type="button" id="updDlgClose">Закрыть</button>
</dialog>

<dialog class="tiers criteria-dlg" id="criteriaDlg" aria-labelledby="criteriaDlgTitle">
  <h3 id="criteriaDlgTitle">Критерии и критичность ошибок</h3>
  <p>Красный — критичная, жёлтый — некритичная ошибка.</p>
  <div class="criteria-list">
    <div class="criterion-def"><h4>Требования к кандидатам</h4><p><span class="badge crit">Критичная</span>Запрещённые слова; требования, нарушающие законодательство; дискриминирующие требования.<br><span class="badge warn">Некритичная</span>Нет конкретных требований, по которым можно корректно отказать кандидату.</p></div>
    <div class="criterion-def"><h4>Бенефиты и преимущества работы</h4><p><span class="badge crit">Критичная</span>Нет или изменена формулировка хотя бы одного из пяти фиксированных пунктов гайда.</p></div>
    <div class="criterion-def"><h4>Орфография и типографика</h4><p><span class="badge crit">Критичная</span>Название бренда или продукта не соответствует редполитике, например «Avito» вместо «Авито».<br><span class="badge warn">Некритичная</span>Написание терминов и другие ошибки из блока типографики.</p></div>
    <div class="criterion-def"><h4>Структура и оформление</h4><p><span class="badge crit">Критичная</span>Пропущен обязательный блок; дополнительные требования («желательно» и подобные) остались в обязательных требованиях, а не вынесены отдельно.<br><span class="badge warn">Некритичная</span>Ошибки оформления списков; нарушена логика названия; в Product &amp; Tech нет примеров будущих задач.</p></div>
  </div>
  <button class="close" type="button" id="criteriaDlgClose">Понятно</button>
</dialog>

<section class="status-wrap" id="statusPanel" aria-label="Статус проверки вакансий"></section>

<div class="panel">
  <div class="filters">
    <input id="q" type="search" placeholder="Поиск по названию…" aria-label="Поиск по названию">
    <select id="fRecruitmentLead" aria-label="Фильтр по тимлиду рекрутмента"><option value="">Все тимлиды рекрутмента</option></select>
    <select id="fDir" aria-label="Фильтр по направлению"><option value="">Все направления</option></select>
    <select id="fTeam" aria-label="Фильтр по команде"><option value="">Все команды</option></select>
    <select id="fRecruiter" aria-label="Фильтр по рекрутеру"><option value="">Все рекрутеры</option></select>
    <select id="fCritical" aria-label="Фильтр по числу критических ошибок">
      <option value="">Критические ошибки: все</option><option value="1">1</option>
      <option value="2">2</option><option value="3">3</option><option value="5">5+</option>
    </select>
    <select id="fCriticalCriterion" aria-label="Фильтр критических ошибок по критерию">
      <option value="">Критические: все критерии</option>
    </select>
    <label class="chk" id="fClosedLbl" hidden><input type="checkbox" id="fClosed"> <span>скрыть закрытые</span></label>
    <div class="spacer"></div>
    <div class="legend">
      <span><span class="chip green">✓</span> чисто</span>
      <span><span class="chip yellow">!</span> посмотреть</span>
      <span><span class="chip red">✕</span> нарушение</span>
    </div>
  </div>
</div>

<div class="toolbar">
  <h2 class="table-title" id="tableTitle">Проверенные вакансии</h2>
  <span class="count" id="count"></span>
  <span class="grow"></span>
  <button class="tbtn danger" id="delClosedBtn" type="button" hidden
    title="Удалить из отчёта вакансии, которых уже нет на career.avito.com">🗑 Удалить закрытые</button>
  <button class="tbtn" id="expandBtn" type="button">Развернуть все</button>
  <button class="tbtn" id="csvBtn" type="button"
    title="Сводная таблица: строка на вакансию, статусы по критериям">⤓ Сводка (CSV)</button>
  <button class="tbtn" id="xlsBtn" type="button"
    title="Все проблемы: строка на каждое замечание — открывается в Excel">⤓ Все проблемы (Excel)</button>
</div>
<div class="tablebox">
<table id="tbl"><thead><tr id="headrow"></tr></thead><tbody id="tbody"></tbody></table>
</div>
<footer>Сортировка — клик по заголовку столбца; по умолчанию самые проблемные сверху.
Фильтры сохраняются в адресе страницы — ссылку можно шарить. Определения критериев —
в кнопке «ⓘ Критерии» наверху страницы.</footer>
</div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const ICONS = { green: '✓', yellow: '!', red: '✕' };
const ORDER = { red: 0, yellow: 1, green: 2 };
const LOCAL = location.protocol === 'file:';

let sortKey = '_severity', sortAsc = false, open = new Set(), problemsOnly = false;

const countSev = (v, sev) => Object.values(v.criteria)
  .reduce((s, c) => s + c.comments.filter(x => x.severity === sev).length, 0);
DATA.vacancies.forEach(v => {
  v._reds = countSev(v, 'red');       // критические ошибки (красные замечания)
  v._yellows = countSev(v, 'yellow');
});

// ---------- обновление данных ----------
// кнопка «Обновить» работает только через локальный serve.py — на файле,
// открытом двойным кликом, и на опубликованной ссылке бэкенда нет
const SERVED = ['localhost', '127.0.0.1'].includes(location.hostname);
const updateInfo = [];
if (DATA.refresh_schedule) updateInfo.push(`<b>${DATA.refresh_schedule}</b>`);
if (DATA.generated_at) updateInfo.push(`последнее обновление: <b>${DATA.generated_at}</b>`);
if (SERVED) updateInfo.push('обновить можно кнопкой «⟳ Обновить данные» в правом верхнем углу');
document.getElementById('updline').innerHTML = updateInfo.join(' · ');

const updBtn = document.getElementById('updBtn');
const updDlg = document.getElementById('updDlg');
const updLog = document.getElementById('updLog');
const updClose = document.getElementById('updDlgClose');
if (SERVED) updBtn.hidden = false;
updClose.onclick = () => updDlg.close();
// после успешного обновления страницу перезагружаем не сами, а когда
// пользователь закроет окно с логом (кнопкой или Esc)
let reloadOnClose = false;
updDlg.addEventListener('close', () => { if (reloadOnClose) location.reload(); });

// стримит текстовый ответ сервера в лог диалога; перезагружает страницу при «✓ Готово»
async function streamAction(title, desc, request) {
  document.getElementById('updDlgTitle').textContent = title;
  document.getElementById('updDlgDesc').textContent = desc;
  updBtn.disabled = true; updClose.disabled = true;
  updBtn.classList.add('upd-running');
  updLog.textContent = 'Подключаюсь к серверу…\\n';
  updDlg.showModal();
  let ok = false;
  try {
    const resp = await request();
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    updLog.textContent = '';
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      updLog.textContent += dec.decode(value, { stream: true });
      updLog.scrollTop = updLog.scrollHeight;
    }
    ok = updLog.textContent.includes('✓ Готово');
  } catch (e) {
    updLog.textContent += `\\n✗ Не получилось связаться с сервером: ${e.message}\\n` +
      'Проверьте, что окно терминала с serve.py ещё открыто, и попробуйте снова.';
  }
  updBtn.disabled = false; updClose.disabled = false;
  updBtn.classList.remove('upd-running');
  if (ok) {
    reloadOnClose = true;
    updLog.textContent += '\\nЗакройте это окно — страница перезагрузится с новыми данными.';
  }
  updLog.scrollTop = updLog.scrollHeight;
}

updBtn.onclick = () => streamAction('Обновление данных',
  'Сервер качает свежие вакансии с career.avito.com, проверяет их по гайду и ' +
  'пересобирает отчёт. Обычно это занимает меньше минуты.',
  () => fetch('/update', { cache: 'no-store' }));

// ---------- закрытые вакансии: пометка и удаление ----------
const closedFiles = DATA.vacancies.filter(v => v.closed).map(v => v.file);
const delBtn = document.getElementById('delClosedBtn');
if (closedFiles.length) {
  const lbl = document.getElementById('fClosedLbl');
  lbl.hidden = false;
  lbl.querySelector('span').textContent = `скрыть закрытые (${closedFiles.length})`;
  if (SERVED) {
    delBtn.hidden = false;
    delBtn.textContent = `🗑 Удалить закрытые (${closedFiles.length})`;
  }
}
function deleteVacancies(files) {
  const what = files.length === 1 ? 'эту вакансию' : `${files.length} закрытых вакансий`;
  if (!confirm(`Удалить ${what} из отчёта?\\nФайлы удалятся из папки vacancies/, отчёт пересоберётся.`)) return;
  streamAction('Удаление закрытых вакансий',
    'Сервер удаляет md-файлы вакансий, которых уже нет на career.avito.com, ' +
    'и пересобирает отчёт. Активные вакансии он не тронет.',
    () => fetch('/delete', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files }) }));
}
delBtn.onclick = () => deleteVacancies(closedFiles);

// ---------- поп-ап с определениями критериев ----------
const criteriaDlg = document.getElementById('criteriaDlg');
document.getElementById('criteriaBtn').onclick = () => criteriaDlg.showModal();
document.getElementById('criteriaDlgClose').onclick = () => criteriaDlg.close();
criteriaDlg.onclick = e => { if (e.target === criteriaDlg) criteriaDlg.close(); };

// ---------- тема ----------
const themeBtn = document.getElementById('themeBtn');
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem('vac-theme', t);
}
applyTheme(localStorage.getItem('vac-theme') ||
  (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
themeBtn.onclick = () =>
  applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');

// ---------- фильтры ----------
const dirs = [...new Set(DATA.vacancies.map(v => v.direction).filter(Boolean))].sort();
const teams = [...new Set(DATA.vacancies.map(v => v.team).filter(Boolean))].sort();
const recruiters = [...new Set(DATA.vacancies.map(v => v.recruiter).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru'));
const RECRUITER_TO_LEAD = {
  'Абузярова Ирина': 'Людмила Бодрова', 'Базарова Аюна': 'Лидия Муравьёва',
  'Барбашова Екатерина': 'Валерия Ильницкая', 'Баркова Ирина': 'Екатерина Миронова',
  'Башкирова Анастасия': 'Екатерина Разгон', 'Гальчун Александра': 'Софья Присич',
  'Ганюшкина Наталья': 'Лидия Муравьёва', 'Голева Ксения': 'Лидия Муравьёва',
  'Домрачева Олеся': 'Светлана Валикова', 'Дюдькин Алексей': 'Светлана Валикова',
  'Евелева Анна': 'Екатерина Миронова', 'Захарова Юлия': 'Людмила Бодрова',
  'Калинина Яна': 'Софья Присич', 'Калуцкая Татьяна': 'Валерия Ильницкая',
  'Камина Виолетта': 'Людмила Бодрова', 'Карпенко Полина': 'Валерия Ильницкая',
  'Кононова Вера': 'Валерия Ильницкая', 'Куликова Дарья': 'Лидия Муравьёва',
  'Лукашева Анна': 'Екатерина Миронова', 'Маринина Анна': 'Екатерина Разгон',
  'Митрейкина Анастасия': 'Екатерина Миронова', 'Мыкольникова Кристина': 'Софья Присич',
  'Неверова Алина': 'Людмила Бодрова', 'Новохатько Мария': 'Екатерина Миронова',
  'Пасынкова Полина': 'Лидия Муравьёва', 'Рахимова Индира': 'Валерия Ильницкая',
  'Савина Рената': 'Екатерина Разгон', 'Самойлова Мария': 'Лидия Муравьёва',
  'Севастьянова Екатерина': 'Софья Присич', 'Скорых Екатерина': 'Лидия Муравьёва',
  'Стригачева Дарья': 'Софья Присич', 'Терехова Анна': 'Софья Присич',
  'Титова Виктория': 'Людмила Бодрова', 'Трусова Элина': 'Софья Присич',
  'Ульмаскулова Эльвира': 'Светлана Валикова', 'Фазлыева Ирина': 'Светлана Валикова',
  'Феоктистова Анна': 'Екатерина Разгон', 'Филиппова Мария': 'Екатерина Миронова',
  'Черникова Ольга': 'Валерия Ильницкая', 'Шепталина Анастасия': 'Людмила Бодрова',
  'Шмелева Анастасия': 'Софья Присич', 'Ярох Айгуль': 'Светлана Валикова',
};
const recruitmentLeads = [...new Set(recruiters.map(r => RECRUITER_TO_LEAD[r]).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru'));
for (const [id, list] of [['fDir', dirs], ['fTeam', teams], ['fRecruitmentLead', recruitmentLeads]]) {
  const sel = document.getElementById(id);
  list.forEach(x => sel.append(new Option(x, x)));
}
function updateRecruiterOptions() {
  const sel = document.getElementById('fRecruiter');
  const selected = sel.value;
  const lead = document.getElementById('fRecruitmentLead').value;
  const list = lead ? recruiters.filter(r => RECRUITER_TO_LEAD[r] === lead) : recruiters;
  sel.replaceChildren(new Option('Все рекрутеры', ''));
  list.forEach(x => sel.append(new Option(x, x)));
  if (list.includes(selected)) sel.value = selected;
}
function updateOptionsForLead(id, allValues, getValue, emptyLabel) {
  const sel = document.getElementById(id);
  const selected = sel.value;
  const lead = document.getElementById('fRecruitmentLead').value;
  const values = lead ? [...new Set(DATA.vacancies
    .filter(v => RECRUITER_TO_LEAD[v.recruiter] === lead)
    .map(getValue).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ru')) : allValues;
  sel.replaceChildren(new Option(emptyLabel, ''));
  values.forEach(x => sel.append(new Option(x, x)));
  if (values.includes(selected)) sel.value = selected;
}
function updateLeadDependentOptions() {
  updateRecruiterOptions();
  updateOptionsForLead('fDir', dirs, v => v.direction, 'Все направления');
  updateOptionsForLead('fTeam', teams, v => v.team, 'Все команды');
}
updateLeadDependentOptions();
{
  const sel = document.getElementById('fCriticalCriterion');
  DATA.criteria.forEach(c => sel.append(new Option(c.label, c.key)));
}

// состояние фильтров в URL-хеше
const FIELDS = ['q', 'fDir', 'fTeam', 'fRecruitmentLead', 'fRecruiter', 'fCritical', 'fCriticalCriterion', 'fClosed'];
function saveHash() {
  const p = new URLSearchParams();
  for (const id of FIELDS) {
    const el = document.getElementById(id);
    const val = el.type === 'checkbox' ? (el.checked ? '1' : '') : el.value;
    if (val) p.set(id, val);
  }
  if (sortKey !== '_severity' || sortAsc) { p.set('sort', sortKey); if (sortAsc) p.set('asc', '1'); }
  history.replaceState(null, '', p.size ? '#' + p : location.pathname);
}
function loadHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  for (const id of FIELDS) {
    const el = document.getElementById(id);
    if (!p.has(id)) continue;
    if (el.type === 'checkbox') el.checked = true; else el.value = p.get(id);
  }
  if (p.has('sort')) sortKey = p.get('sort');
  if (p.has('asc')) sortAsc = true;
}

function frequent(mode) {
  const severity = mode === 'critical' ? 'red' : 'yellow';
  return DATA.criteria.map(c => ({ label: c.label, n: DATA.vacancies.filter(v =>
    (v.criteria[c.key]?.comments ?? []).some(x => x.severity === severity)).length,
  })).filter(x => x.n).sort((a, b) => b.n - a.n).slice(0, 2);
}

function statusPanel() {
  const n = DATA.vacancies.length;
  const critical = DATA.vacancies.filter(v => v._reds).length;
  const warning = DATA.vacancies.filter(v => !v._reds && v._yellows).length;
  const clean = n - critical - warning;
  const mode = critical ? 'critical' : warning ? 'warning' : 'clean';
  const configs = {
    critical: { cls: 'red', tab: 'Есть критические', kicker: 'Требуется внимание',
      headline: `Критические ошибки найдены в ${critical} вакансиях`, count: critical,
      detail: warning ? `В ${warning} вакансиях — только некритичные замечания` : 'Некритичных замечаний без критичных нет',
      table: 'Вакансии с критическими ошибками', frequent: 'Главные критические ошибки' },
    warning: { cls: 'yellow', tab: 'Только некритические', kicker: 'Только некритичные замечания',
      headline: `В ${warning} вакансиях — только некритичные замечания`, count: warning,
      detail: critical ? `В остальных ${critical} вакансиях есть критичные ошибки` : 'Критичных ошибок не найдено',
      table: 'Вакансии с некритичными ошибками', frequent: 'Частые некритичные ошибки' },
    clean: { cls: 'green', tab: 'Ошибок нет', kicker: 'Всё в порядке',
      headline: clean === n ? `Все ${n} вакансий соответствуют гайду` : `${clean} вакансий соответствуют гайду`, count: clean,
      detail: 'Критичных и некритичных ошибок не найдено',
      table: 'Вакансии без замечаний', frequent: 'Результат проверки' },
  };
  const c = configs[mode];
  const items = mode === 'clean'
    ? `<ul><li><b>${clean}</b> вакансий прошли все проверки</li><li><b>0</b> ошибок найдено</li></ul>`
    : `<ul>${frequent(mode).map(x => `<li><b>${x.n}</b> ${esc(x.label)}</li>`).join('') || '<li>Замечаний этого типа нет</li>'}</ul>`;
  document.getElementById('statusPanel').innerHTML = `<div class="status-hero ${c.cls}"><div class="status-kicker">${c.kicker}</div>
      <h2>${c.headline}</h2><div class="status-meta">Проверено ${n} из ${n} вакансий · ${c.detail} · обновлено ${DATA.generated_at || 'недавно'}</div>
      <div class="status-actions"><button class="status-primary" id="showStatus" type="button">${mode === 'critical' ? 'Показать вакансии с ошибками' : mode === 'clean' ? 'Посмотреть все вакансии' : `Показать ${c.count} вакансий`}</button>
      <button class="status-secondary" id="showCriteria" type="button">${mode === 'clean' ? 'Критерии проверки' : 'Как исправлять ошибки'}</button></div>
      <div class="status-frequent"><span class="label">${c.frequent}</span>${items}</div></div>`;
  document.getElementById('showStatus').onclick = () => {
    if (mode === 'critical') { problemsOnly = true; document.getElementById('fCritical').value = ''; }
    render();
    requestAnimationFrame(() => document.getElementById('tbl').scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };
  document.getElementById('showCriteria').onclick = () => criteriaDlg.showModal();
}

function header() {
  const tr = document.getElementById('headrow');
  tr.innerHTML = '';
  const mk = (key, text, cls, titleAttr) => {
    const th = document.createElement('th');
    th.className = cls || '';
    if (titleAttr) th.title = titleAttr;
    const arrow = sortKey === key ? ` <span class="arrow">${sortAsc ? '▲' : '▼'}</span>` : '';
    th.innerHTML = cls === 'crit-col' ? `<span class="vh">${text}${arrow}</span>` : text + arrow;
    th.tabIndex = 0;
    const act = () => { sortAsc = sortKey === key ? !sortAsc : false; sortKey = key; render(); };
    th.onclick = act;
    th.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); act(); } };
    tr.append(th);
  };
  mk('title', 'Вакансия');
  mk('recruiter', 'Рекрутер', 'recruiter-col', 'Рекрутер, указанный в сотруднической версии карьерного сайта');
  DATA.criteria.forEach(c => mk(c.key, c.label, 'crit-col'));
}

function visible() {
  const q = document.getElementById('q').value.toLowerCase();
  const d = document.getElementById('fDir').value;
  const t = document.getElementById('fTeam').value;
  const recruitmentLead = document.getElementById('fRecruitmentLead').value;
  const recruiter = document.getElementById('fRecruiter').value;
  const criticalFilter = document.getElementById('fCritical').value;
  const criticalCriterion = document.getElementById('fCriticalCriterion').value;
  const hc = document.getElementById('fClosed').checked;
  let rows = DATA.vacancies.filter(v =>
    (!q || v.title.toLowerCase().includes(q)) &&
    (!problemsOnly || v._reds > 0 || v._yellows > 0) &&
    (!d || v.direction === d) && (!t || v.team === t) && (!recruitmentLead || RECRUITER_TO_LEAD[v.recruiter] === recruitmentLead) && (!recruiter || v.recruiter === recruiter) &&
    (!criticalFilter || (criticalFilter === '5' ? v._reds >= 5 : v._reds === +criticalFilter)) &&
    (!criticalCriterion || (v.criteria[criticalCriterion]?.comments ?? []).some(x => x.severity === 'red')) &&
    (!hc || !v.closed));
  rows.sort((a, b) => {
    let x, y;
    if (sortKey === 'title') { x = a.title; y = b.title; }
    else if (sortKey === 'recruiter') { x = a.recruiter || 'яяя'; y = b.recruiter || 'яяя'; }
    else if (sortKey === '_severity') { x = -(a._reds * 1e6 + a._yellows); y = -(b._reds * 1e6 + b._yellows); }
    else { x = ORDER[a.criteria[sortKey]?.status ?? 'green']; y = ORDER[b.criteria[sortKey]?.status ?? 'green']; }
    const cmp = typeof x === 'string' ? x.localeCompare(y, 'ru') : x - y;
    return sortAsc ? -cmp : cmp;
  });
  return rows;
}

function resetFilters() {
  problemsOnly = false;
  for (const id of ['q', 'fDir', 'fTeam', 'fRecruitmentLead', 'fRecruiter']) document.getElementById(id).value = '';
  updateLeadDependentOptions();
  document.getElementById('fCritical').value = '';
  document.getElementById('fCriticalCriterion').value = '';
  document.getElementById('fClosed').checked = false;
  render();
}

const csvCell = s => `"${String(s ?? '').replaceAll('"', '""')}"`;
function downloadCsv(lines, name) {
  const blob = new Blob(['\\ufeff' + lines.join('\\r\\n')], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function exportCsv() {
  const rows = visible();
  const head = ['Вакансия', 'URL', 'Направление', 'Команда', 'Локация', 'Рекрутер', 'Опубликована',
    'Критических ошибок', 'Некритичных ошибок', ...DATA.criteria.map(c => c.label)];
  const lines = [head.map(csvCell).join(';')];
  rows.forEach(v => lines.push([
    v.title, v.url, v.direction, v.team, v.location, v.recruiter, v.published,
    v._reds, v._yellows,
    ...DATA.criteria.map(c => v.criteria[c.key]?.status ?? 'green'),
  ].map(csvCell).join(';')));
  downloadCsv(lines, 'vacancy-review.csv');
}

function exportProblems() {
  const rows = visible();
  const label = {};
  DATA.criteria.forEach(c => label[c.key] = c.label);
  const lines = [['Вакансия', 'URL', 'Направление', 'Команда', 'Критерий', 'Статус',
    'Ошибка', 'Цитата', 'Ссылка с подсветкой'].map(csvCell).join(';')];
  rows.forEach(v => Object.entries(v.criteria).forEach(([k, c]) =>
    c.comments.forEach(x => (x.details ?? [x]).forEach(d => lines.push([
      v.title, v.url, v.direction, v.team, label[k],
      x.severity === 'red' ? 'критичная' : 'некритичная',
      x.details ? `${x.text}: ${d.text}` : x.text, d.quote ?? '',
      d.quote ? highlightUrl(v, d) : '',
    ].map(csvCell).join(';'))))));
  downloadCsv(lines, 'vacancy-problems.csv');
}

// ссылка на вакансию с подсветкой цитаты (scroll-to-text fragment)
const highlightUrl = (v, x) =>
  `${v.url}#:~:text=${encodeURIComponent(x.quote).replaceAll('-', '%2D')}`;

function render() {
  header();
  saveHash();
  statusPanel();
  const rows = visible();
  document.getElementById('tableTitle').textContent = problemsOnly ? 'Вакансии с ошибками' :
    document.getElementById('fCritical').value ? 'Вакансии с критическими ошибками' : 'Все проверенные вакансии';
  document.getElementById('count').textContent =
    `Показано ${rows.length} из ${DATA.vacancies.length}`;
  const allOpen = rows.length && rows.every(v => open.has(v.file));
  document.getElementById('expandBtn').textContent = allOpen ? 'Свернуть все' : 'Развернуть все';
  const tb = document.getElementById('tbody');
  tb.innerHTML = '';
  if (!rows.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td class="empty-state" colspan="${DATA.criteria.length + 2}">
      По этим фильтрам ничего не нашлось.<br><button type="button">Сбросить фильтры</button></td>`;
    tr.querySelector('button').onclick = resetFilters;
    tb.append(tr);
    return;
  }
  rows.forEach(v => {
    const tr = document.createElement('tr');
    tr.className = 'row' + (open.has(v.file) ? ' open' : '') + (v.closed ? ' closed' : '');
    tr.tabIndex = 0;
    tr.setAttribute('aria-expanded', open.has(v.file));
    const cells = DATA.criteria.map(c => {
      const comments = v.criteria[c.key]?.comments ?? [];
      const hasRed = comments.some(x => x.severity === 'red');
      const hasYellow = comments.some(x => x.severity === 'yellow');
      const statuses = `${hasRed ? '<span class="badge crit" title="Есть критичное нарушение">✕</span>' : ''}` +
        `${hasYellow ? '<span class="badge warn" title="Есть некритичное замечание">!</span>' : ''}`;
      return `<td class="crit-col">${statuses || '<span class="chip green">✓</span>'}</td>`;
    }).join('');
    const badges =
      (v.closed ? `<span class="badge closed" title="Вакансии уже нет на career.avito.com">не на сайте</span>` : '') +
      (v._reds ? '<span class="badge crit">есть критичные</span>' : '') +
      (v._yellows ? '<span class="badge warn">есть некритичные</span>' : '');
    tr.innerHTML = `<td class="vac"><span class="chev">${open.has(v.file) ? '▼' : '▶'}</span><a href="${v.url}"
        target="_blank" rel="noopener" title="Открыть вакансию на career.avito.com">${v.title}</a>
      <span class="badges">${badges}</span>
      <div class="meta">${[v.direction, v.team, v.location].filter(Boolean).join(' · ')}</div></td>
      <td class="recruiter-col">${v.recruiter ? `<span class="recruiter-pill">${esc(v.recruiter)}</span>` : '<span class="recruiter-pill empty">нет данных</span>'}</td>${cells}`;
    tr.querySelector('a').onclick = e => e.stopPropagation();
    const toggle = () => {
      if (getSelection().toString()) return;
      open.has(v.file) ? open.delete(v.file) : open.add(v.file);
      render();
    };
    tr.onclick = toggle;
    tr.onkeydown = e => {
      if ((e.key === 'Enter' || e.key === ' ') && e.target === tr) { e.preventDefault(); toggle(); }
    };
    tb.append(tr);
    if (open.has(v.file)) {
      const dtr = document.createElement('tr');
      dtr.className = 'details';
      const cards = DATA.criteria.map(c => {
        const cr = v.criteria[c.key];
        if (!cr || !cr.comments.length) return '';
        const hasRed = cr.comments.some(x => x.severity === 'red');
        const hasYellow = cr.comments.some(x => x.severity === 'yellow');
        const severityBadges = `${hasRed ? '<span class="badge crit">Критичная</span>' : ''}` +
          `${hasYellow ? '<span class="badge warn">Некритичная</span>' : ''}`;
        const lis = cr.comments.map(x => {
          const jump = ` <a class="jump" href="${x.quote ? highlightUrl(v, x) : v.url}" target="_blank"
            rel="noopener" title="Открыть вакансию на career.avito.com">${x.quote ? 'показать место ↗' : 'открыть вакансию ↗'}</a>`;
          const severityLabel = x.severity === 'red'
            ? '<span class="badge crit">Критичная</span>'
            : '<span class="badge warn">Некритичная</span>';
          const details = (x.details ?? []).map(d => {
            const detailJump = ` <a class="jump" href="${d.quote ? highlightUrl(v, d) : v.url}" target="_blank"
              rel="noopener" title="Открыть вакансию на career.avito.com">${d.quote ? 'показать место ↗' : 'открыть вакансию ↗'}</a>`;
            return `<li>${esc(d.text)}${detailJump}</li>`;
          }).join('');
          const detailList = details ? `<ul class="group-details">${details}</ul>` : '';
          return `<li class="${x.severity}">${severityLabel}<span class="group-title">${esc(x.text)}</span>${x.details ? detailList : jump}</li>`;
        }).join('');
        return `<div class="dcard"><h4><span class="chip ${cr.status}">${ICONS[cr.status]}</span>${c.label}<span class="badges">${severityBadges}</span></h4><ul>${lis}</ul></div>`;
      }).join('') || '<div class="dcard empty"><span class="chip green">✓</span> Замечаний нет</div>';
      const meta = [
        v.closed ? '<span class="closednote">вакансии уже нет на сайте</span>' : '',
        v.published ? `опубликована ${v.published}` : '',
        v.recruiter ? `рекрутер: ${esc(v.recruiter)}` : '',
        (LOCAL || SERVED) ? `<a href="../vacancies/${v.file}" target="_blank" rel="noopener">текст вакансии (md)</a>` : '']
        .filter(Boolean).join(' · ');
      const delOne = (v.closed && SERVED)
        ? ' <button class="tbtn danger delone" type="button">🗑 Удалить из отчёта</button>' : '';
      dtr.innerHTML = `<td colspan="${DATA.criteria.length + 2}"><div class="detail-inner">
        <div class="detail-head">${meta}${delOne}</div>
        <div class="detail-grid">${cards}</div></div></td>`;
      const delBtnOne = dtr.querySelector('.delone');
      if (delBtnOne) delBtnOne.onclick = () => deleteVacancies([v.file]);
      tb.append(dtr);
    }
  });
}

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
['q', 'fDir', 'fTeam', 'fRecruiter', 'fCritical', 'fCriticalCriterion', 'fClosed'].forEach(id =>
  document.getElementById(id).addEventListener('input', render));
document.getElementById('fRecruitmentLead').addEventListener('input', () => { updateLeadDependentOptions(); render(); });
document.getElementById('csvBtn').onclick = exportCsv;
document.getElementById('xlsBtn').onclick = exportProblems;
document.getElementById('expandBtn').onclick = () => {
  const rows = visible();
  if (rows.length && rows.every(v => open.has(v.file))) rows.forEach(v => open.delete(v.file));
  else rows.forEach(v => open.add(v.file));
  render();
};
loadHash();
updateLeadDependentOptions();
render();
</script>
"""

SHELL_TOP = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1">\n')
TEMPLATE = SHELL_TOP + HEAD_CORE + "</head>\n<body>\n" + BODY_CORE + "</body>\n</html>\n"
ARTIFACT_TEMPLATE = HEAD_CORE + BODY_CORE


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-r", "--report", default="report.json")
    parser.add_argument("-o", "--out", default="site/index.html")
    parser.add_argument("-a", "--artifact", default="",
                        help="дополнительно собрать версию для публикации по ссылке (без <html>-каркаса)")
    args = parser.parse_args()

    data = json.loads(pathlib.Path(args.report).read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
    print(f"Сайт собран: {out} (вакансий: {len(data['vacancies'])})")
    if args.artifact:
        ap = pathlib.Path(args.artifact)
        ap.parent.mkdir(parents=True, exist_ok=True)
        ap.write_text(ARTIFACT_TEMPLATE.replace("__DATA__", payload), encoding="utf-8")
        print(f"Версия для публикации по ссылке: {ap}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())




