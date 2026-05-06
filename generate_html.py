"""
Generates a standalone dashboard.html — no server needed.
Usage: python3 generate_html.py
"""
import json
import numpy as np
import pandas as pd


# ─── Load & process ───────────────────────────────────────────────────────────

df = pd.read_excel("daily_position_details.xlsx")
df["date"] = pd.to_datetime(df["date"])
df["month"] = df["date"].dt.to_period("M").astype(str)

LOCATION_RULES = [
    (["شناور", "sticky", "چسبنده", "چسبان"], "شناور"),
    (["سایدبار", "sidebar", "کناری", "جانبی"], "سایدبار"),
    (["میان مطلب", "میانی", "میان", "وسط", "بین مطلب"], "میانی"),
    (["بالا", "بالای", "اول", "ابتدا", "هدر", "header", "سردبیر"], "بالا"),
    (["پایین", "پایینی", "آخر", "انتها", "فوتر", "footer"], "پایین"),
]


def classify(desc, pos_type):
    tags = [lbl for kws, lbl in LOCATION_RULES if any(k in str(desc) for k in kws)]
    return f"{pos_type} | {' · '.join(tags)}" if tags else pos_type


df["position_label"] = df.apply(lambda r: classify(r["description"], r["position_type"]), axis=1)

# Publisher daily PV (same across all positions for same pub+date)
daily_pub_pv = (
    df.groupby(["publisher_id", "date"])["page_views"]
    .max()
    .reset_index()
    .rename(columns={"page_views": "pub_daily_pv"})
)
df = df.merge(daily_pub_pv, on=["publisher_id", "date"])

# ─── publishers list ──────────────────────────────────────────────────────────

publishers = (
    df[["publisher_id", "publisher_name"]]
    .drop_duplicates()
    .sort_values("publisher_name")
    .rename(columns={"publisher_id": "id", "publisher_name": "name"})
    .to_dict("records")
)

# ─── pub_avg_pv ───────────────────────────────────────────────────────────────

pub_avg_pv = (
    daily_pub_pv.groupby("publisher_id")["pub_daily_pv"]
    .mean()
    .round(0)
    .astype(int)
    .to_dict()
)
pub_avg_pv = {str(k): v for k, v in pub_avg_pv.items()}

# ─── pub_monthly_pv ───────────────────────────────────────────────────────────

pub_monthly_pv = (
    daily_pub_pv.assign(month=lambda x: pd.to_datetime(x["date"]).dt.to_period("M").astype(str))
    .groupby(["publisher_id", "month"])["pub_daily_pv"]
    .sum()
    .reset_index()
    .rename(columns={"pub_daily_pv": "pv", "publisher_id": "pid"})
)
pub_monthly_pv["pid"] = pub_monthly_pv["pid"].astype(str)
pub_monthly_pv_list = pub_monthly_pv.to_dict("records")

# ─── tab1_data: monthly revenue × publisher × position_type ──────────────────

tab1 = (
    df.groupby(["publisher_id", "month", "position_type"])
    .agg(
        rev=("total_adv_cost", "sum"),
        fixed=("fixed_adv_cost", "sum"),
        billboard=("billboard_adv_cost", "sum"),
    )
    .reset_index()
    .rename(columns={"publisher_id": "pid", "position_type": "pt"})
)
tab1["pid"] = tab1["pid"].astype(str)
tab1_list = tab1.to_dict("records")

# ─── tab2_monthly: monthly revenue × publisher × position ────────────────────

tab2_m = (
    df.groupby(["publisher_id", "month", "position_id", "description", "position_type", "position_label"])
    .agg(
        rev=("total_adv_cost", "sum"),
        fixed=("fixed_adv_cost", "sum"),
        billboard=("billboard_adv_cost", "sum"),
    )
    .reset_index()
    .rename(columns={"publisher_id": "pid", "position_type": "pt",
                     "position_label": "pl", "position_id": "pos_id",
                     "description": "desc"})
)
tab2_m["pid"] = tab2_m["pid"].astype(str)
tab2_m["pos_id"] = tab2_m["pos_id"].astype(str)
tab2_monthly_list = tab2_m.to_dict("records")

print(f"Data sizes — publishers: {len(publishers)}, tab1: {len(tab1_list)}, "
      f"tab2_monthly: {len(tab2_monthly_list)}, pub_monthly_pv: {len(pub_monthly_pv_list)}")

# ─── Embed in HTML ────────────────────────────────────────────────────────────

DATA = {
    "publishers": publishers,
    "pub_avg_pv": pub_avg_pv,
    "pub_monthly_pv": pub_monthly_pv_list,
    "tab1": tab1_list,
    "tab2_monthly": tab2_monthly_list,
}

data_json = json.dumps(DATA, ensure_ascii=False)

HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Publisher Pricing Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Tahoma, 'Vazir', sans-serif;
    background: #f5f6fa;
    color: #333;
    direction: rtl;
  }
  .topbar {
    background: #1a1a2e;
    color: white;
    padding: 14px 28px;
    display: flex;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }
  .topbar h1 { font-size: 1.15rem; flex: 1; }
  .topbar select, .topbar input[type=range] {
    padding: 6px 10px;
    border-radius: 6px;
    border: none;
    font-family: Tahoma, sans-serif;
    font-size: 0.9rem;
    background: #fff;
    min-width: 220px;
  }
  .topbar label { font-size: 0.82rem; color: #ccc; }
  .topbar .slider-wrap { display: flex; align-items: center; gap: 8px; }
  .topbar .slider-wrap span { font-size: 0.85rem; min-width: 30px; }

  .kpis {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    padding: 18px 28px 0;
  }
  .kpi-card {
    background: white;
    border-radius: 10px;
    padding: 16px 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
  }
  .kpi-card .label { font-size: 0.78rem; color: #888; margin-bottom: 4px; }
  .kpi-card .value { font-size: 1.5rem; font-weight: bold; color: #1a1a2e; }

  .tabs-bar {
    display: flex;
    gap: 0;
    padding: 18px 28px 0;
  }
  .tab-btn {
    padding: 9px 22px;
    background: #e2e6f0;
    border: none;
    cursor: pointer;
    font-family: Tahoma, sans-serif;
    font-size: 0.88rem;
    border-radius: 8px 8px 0 0;
    color: #555;
    margin-left: 3px;
    transition: background .15s;
  }
  .tab-btn.active { background: white; color: #1a1a2e; font-weight: bold; }

  .tab-content {
    display: none;
    background: white;
    margin: 0 28px 28px;
    border-radius: 0 0 10px 10px;
    padding: 20px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
  }
  .tab-content.active { display: block; }

  .filter-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }
  .filter-row label { font-size: 0.85rem; color: #666; }
  .filter-row select {
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid #ddd;
    font-family: Tahoma, sans-serif;
    font-size: 0.85rem;
  }

  .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .chart-box { min-height: 340px; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;
    margin-top: 16px;
  }
  thead th {
    background: #f0f2f8;
    padding: 9px 10px;
    text-align: right;
    font-weight: bold;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  thead th:hover { background: #e0e4f0; }
  tbody tr:hover { background: #f8f9fc; }
  tbody td { padding: 7px 10px; border-bottom: 1px solid #f0f0f0; white-space: nowrap; }
  .num { text-align: left; font-variant-numeric: tabular-nums; }

  .scenarios-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 16px 0;
  }
  .scenario-card {
    border-radius: 10px;
    padding: 16px;
    text-align: center;
  }
  .scenario-card.bad  { background: #fde8e8; }
  .scenario-card.real { background: #fff8e1; }
  .scenario-card.good { background: #e8f5e9; }
  .scenario-card .s-label { font-size: 0.82rem; color: #555; margin-bottom: 4px; }
  .scenario-card .s-value { font-size: 1.6rem; font-weight: bold; }
  .scenario-card.bad  .s-value { color: #c0392b; }
  .scenario-card.real .s-value { color: #e67e22; }
  .scenario-card.good .s-value { color: #27ae60; }

  .sim-info {
    background: #eef3ff;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.85rem;
    margin-bottom: 14px;
  }
  .section-title {
    font-size: 0.95rem;
    font-weight: bold;
    margin: 18px 0 8px;
    color: #1a1a2e;
    border-right: 3px solid #4285F4;
    padding-right: 8px;
  }

  @media (max-width: 768px) {
    .kpis { grid-template-columns: 1fr 1fr; }
    .charts-row { grid-template-columns: 1fr; }
    .scenarios-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- Top Bar -->
<div class="topbar">
  <h1>📊 Publisher Pricing Dashboard</h1>
  <div>
    <label>پابلیشر</label><br>
    <select id="pubSelect" onchange="onPubChange()"></select>
  </div>
  <div class="slider-wrap">
    <div>
      <label>بازه شباهت (log)</label><br>
      <input type="range" id="logWindow" min="0.3" max="1.2" step="0.1" value="0.6"
             oninput="document.getElementById('lwVal').textContent=this.value; renderTab3()">
    </div>
    <span id="lwVal">0.6</span>
  </div>
</div>

<!-- KPIs -->
<div class="kpis">
  <div class="kpi-card">
    <div class="label">میانگین درآمد ماهانه</div>
    <div class="value" id="kpi1">—</div>
  </div>
  <div class="kpi-card">
    <div class="label">میانگین PV روزانه</div>
    <div class="value" id="kpi2">—</div>
  </div>
  <div class="kpi-card">
    <div class="label">پوزیشن‌های فعال</div>
    <div class="value" id="kpi3">—</div>
  </div>
  <div class="kpi-card">
    <div class="label">RPM میانگین</div>
    <div class="value" id="kpi4">—</div>
  </div>
</div>

<!-- Tabs -->
<div class="tabs-bar">
  <button class="tab-btn active" onclick="showTab('t1',this)">📈 نمای کلی</button>
  <button class="tab-btn" onclick="showTab('t2',this)">🎯 پوزیشن‌ها</button>
  <button class="tab-btn" onclick="showTab('t3',this)">💰 سناریوهای قیمت</button>
</div>

<!-- Tab 1 -->
<div id="t1" class="tab-content active">
  <div class="filter-row">
    <label>فیلتر نوع پوزیشن:</label>
    <select id="t1PtFilter" onchange="renderTab1()"></select>
  </div>
  <div class="charts-row">
    <div class="chart-box" id="chartRev"></div>
    <div class="chart-box" id="chartRpm"></div>
  </div>
  <div class="section-title">جدول ماهانه</div>
  <div id="t1Table"></div>
</div>

<!-- Tab 2 -->
<div id="t2" class="tab-content">
  <div class="filter-row">
    <label>فیلتر نوع پوزیشن:</label>
    <select id="t2PtFilter" onchange="renderTab2()"></select>
  </div>
  <div class="section-title">خلاصه پوزیشن‌ها</div>
  <div id="t2SummaryTable"></div>
  <div class="section-title">ترند RPM ماهانه — ۱۰ پوزیشن برتر</div>
  <div id="chartPosRpm" style="min-height:380px"></div>
  <div class="section-title">جزئیات پوزیشن</div>
  <div class="filter-row">
    <label>پوزیشن:</label>
    <select id="t2PosDetail" onchange="renderPosDetail()">
      <option value="">— انتخاب کنید —</option>
    </select>
  </div>
  <div class="charts-row" id="posDetailCharts"></div>
</div>

<!-- Tab 3 -->
<div id="t3" class="tab-content">
  <div id="simInfo" class="sim-info"></div>
  <div class="section-title">RPM پوزیشن‌های مشابه در سایت‌های مشابه</div>
  <div id="t3ScenTable"></div>
  <div class="section-title">پیشنهاد قیمت برای پوزیشن‌های این پابلیشر</div>
  <div id="t3PricingTable"></div>
  <div class="section-title">جمع کل ماهانه تخمینی</div>
  <div class="scenarios-grid" id="t3Totals"></div>
</div>

<script>
const RAW = """ + data_json + r""";

// ─── helpers ──────────────────────────────────────────────────────────────────
function fmtNum(n, suffix='') {
  if (n == null || isNaN(n)) return '—';
  if (Math.abs(n) >= 1e9) return (n/1e9).toFixed(1)+'B'+suffix;
  if (Math.abs(n) >= 1e6) return (n/1e6).toFixed(1)+'M'+suffix;
  if (Math.abs(n) >= 1e3) return (n/1e3).toFixed(0)+'K'+suffix;
  return n.toFixed(0)+suffix;
}
function fmtComma(n) {
  if (n == null || isNaN(n)) return '—';
  return Math.round(n).toLocaleString();
}
function fmtRpm(n) {
  if (n == null || isNaN(n)) return '—';
  return n.toFixed(2);
}

function groupBy(arr, keys, aggs) {
  const map = new Map();
  for (const row of arr) {
    const key = keys.map(k => row[k]).join('||');
    if (!map.has(key)) {
      const base = {};
      keys.forEach(k => base[k] = row[k]);
      for (const [col, fn, init] of aggs) base[col] = init;
      map.set(key, base);
    }
    const acc = map.get(key);
    for (const [col, fn, init] of aggs) fn(acc, row, col);
  }
  return [...map.values()];
}
const sumAgg = (col) => [col, (acc,row,c) => acc[c] += (row[c]||0), 0];
const firstAgg = (col) => [col, (acc,row,c) => acc[c] = acc[c] || row[c], null];
const setAgg = (col) => [col, (acc,row,c) => { if(!acc[c]) acc[c]=new Set(); acc[c].add(row[c]); }, null];

function quantile(sorted, q) {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
function median(arr) {
  if (!arr.length) return null;
  const s = [...arr].sort((a,b) => a-b);
  return quantile(s, 0.5);
}
function p25(arr) {
  if (!arr.length) return null;
  const s = [...arr].sort((a,b) => a-b);
  return quantile(s, 0.25);
}
function p75(arr) {
  if (!arr.length) return null;
  const s = [...arr].sort((a,b) => a-b);
  return quantile(s, 0.75);
}

// Build lookup: pub_monthly_pv[pid][month] = pv
const pubMonthlyPv = {};
for (const r of RAW.pub_monthly_pv) {
  if (!pubMonthlyPv[r.pid]) pubMonthlyPv[r.pid] = {};
  pubMonthlyPv[r.pid][r.month] = r.pv;
}

// ─── state ────────────────────────────────────────────────────────────────────
let selPid = null;

// ─── init publisher select ────────────────────────────────────────────────────
const pubSel = document.getElementById('pubSelect');
for (const p of RAW.publishers) {
  const o = document.createElement('option');
  o.value = p.id;
  o.textContent = p.name;
  pubSel.appendChild(o);
}
selPid = String(RAW.publishers[0].id);
pubSel.value = selPid;

function onPubChange() {
  selPid = pubSel.value;
  updateKpis();
  populateFilters();
  renderTab1();
  renderTab2();
  renderTab3();
}

// ─── KPIs ─────────────────────────────────────────────────────────────────────
function updateKpis() {
  const rows = RAW.tab1.filter(r => r.pid === selPid);
  const pv = pubMonthlyPv[selPid] || {};

  // group by month
  const months = [...new Set(rows.map(r => r.month))].sort();
  let totalRev = 0;
  for (const r of rows) totalRev += r.rev;
  const avgMonthlyRev = months.length ? totalRev / months.length : 0;

  const pvArr = Object.values(pv);
  const avgMonthlyPv = pvArr.length ? pvArr.reduce((a,b)=>a+b,0)/pvArr.length : 0;
  const avgDailyPv = avgMonthlyPv / 30;

  const positions = new Set(RAW.tab2_monthly.filter(r=>r.pid===selPid).map(r=>r.pos_id));

  let totalPv = pvArr.reduce((a,b)=>a+b,0);
  const overallRpm = totalPv ? totalRev / totalPv * 1000 : 0;

  document.getElementById('kpi1').textContent = fmtNum(avgMonthlyRev, ' ت');
  document.getElementById('kpi2').textContent = fmtNum(avgDailyPv);
  document.getElementById('kpi3').textContent = positions.size;
  document.getElementById('kpi4').textContent = overallRpm.toFixed(2);
}

// ─── populate filters ─────────────────────────────────────────────────────────
function populateFilters() {
  const pts = [...new Set(
    RAW.tab2_monthly.filter(r=>r.pid===selPid).map(r=>r.pt)
  )].sort();

  for (const selId of ['t1PtFilter','t2PtFilter']) {
    const el = document.getElementById(selId);
    el.innerHTML = '<option value="">همه</option>';
    pts.forEach(pt => {
      const o = document.createElement('option');
      o.value = pt; o.textContent = pt;
      el.appendChild(o);
    });
  }
}

function makeTable(cols, rows, sortColInit) {
  let sortCol = sortColInit, sortAsc = false;
  let container = document.createElement('div');
  container.style.overflowX = 'auto';

  function build() {
    const sorted = [...rows].sort((a,b) => {
      const va = a[sortCol], vb = b[sortCol];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1);
    });
    let html = '<table><thead><tr>';
    for (const c of cols) {
      html += `<th onclick="this.closest('table')._sort('${c.key}')">${c.label}${sortCol===c.key?(sortAsc?'▲':'▼'):''}</th>`;
    }
    html += '</tr></thead><tbody>';
    for (const r of sorted) {
      html += '<tr>';
      for (const c of cols) {
        const v = r[c.key];
        html += `<td class="${c.num?'num':''}">${c.fmt ? c.fmt(v) : (v==null?'—':v)}</td>`;
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    container.innerHTML = html;
    container.querySelector('table')._sort = (col) => {
      if (sortCol === col) sortAsc = !sortAsc; else { sortCol = col; sortAsc = false; }
      build();
    };
  }
  build();
  return container;
}

// ─── TAB 1 ────────────────────────────────────────────────────────────────────
function renderTab1() {
  const ptFilter = document.getElementById('t1PtFilter').value;
  let rows = RAW.tab1.filter(r => r.pid === selPid);
  if (ptFilter) rows = rows.filter(r => r.pt === ptFilter);

  // group by month
  const byMonth = {};
  for (const r of rows) {
    if (!byMonth[r.month]) byMonth[r.month] = {rev:0, fixed:0, billboard:0};
    byMonth[r.month].rev += r.rev;
    byMonth[r.month].fixed += r.fixed;
    byMonth[r.month].billboard += r.billboard;
  }
  const pv = pubMonthlyPv[selPid] || {};
  const months = Object.keys(byMonth).sort();

  const revArr = months.map(m => byMonth[m].rev);
  const fixedArr = months.map(m => byMonth[m].fixed);
  const bbArr = months.map(m => byMonth[m].billboard);
  const rpmArr = months.map(m => pv[m] ? byMonth[m].rev / pv[m] * 1000 : null);

  Plotly.react('chartRev', [
    {type:'bar', x:months, y:revArr, name:'کل درآمد', marker:{color:'#4285F4'}, opacity:0.9},
    {type:'bar', x:months, y:fixedArr, name:'فیکس', marker:{color:'#34A853'}, opacity:0.8},
    {type:'bar', x:months, y:bbArr, name:'بیلبورد', marker:{color:'#FBBC04'}, opacity:0.8},
  ], {
    title:'درآمد ماهانه (تومان)', barmode:'overlay', height:330,
    xaxis:{title:'ماه'}, yaxis:{title:'تومان'},
    legend:{orientation:'h', y:1.15},
    margin:{t:50,b:40,l:60,r:10},
  }, {responsive:true});

  Plotly.react('chartRpm', [
    {type:'scatter', mode:'lines+markers', x:months, y:rpmArr,
     name:'RPM', line:{color:'#EA4335', width:2}, marker:{size:7}},
  ], {
    title:'RPM ماهانه', height:330,
    xaxis:{title:'ماه'}, yaxis:{title:'RPM'},
    margin:{t:50,b:40,l:60,r:10},
  }, {responsive:true});

  // table
  const tableRows = months.map(m => ({
    month: m,
    rev: byMonth[m].rev,
    pv: pv[m] || null,
    rpm: pv[m] ? byMonth[m].rev / pv[m] * 1000 : null,
    fixed: byMonth[m].fixed,
    billboard: byMonth[m].billboard,
  })).reverse();

  const el = document.getElementById('t1Table');
  el.innerHTML = '';
  el.appendChild(makeTable([
    {key:'month', label:'ماه'},
    {key:'rev', label:'درآمد کل', num:true, fmt:fmtComma},
    {key:'pv', label:'PV ماهانه', num:true, fmt:fmtComma},
    {key:'rpm', label:'RPM', num:true, fmt:fmtRpm},
    {key:'fixed', label:'فیکس', num:true, fmt:fmtComma},
    {key:'billboard', label:'بیلبورد', num:true, fmt:fmtComma},
  ], tableRows, 'month'));
}

// ─── TAB 2 ────────────────────────────────────────────────────────────────────
function renderTab2() {
  const ptFilter = document.getElementById('t2PtFilter').value;
  let rows = RAW.tab2_monthly.filter(r => r.pid === selPid);
  if (ptFilter) rows = rows.filter(r => r.pt === ptFilter);

  const pv = pubMonthlyPv[selPid] || {};
  const totalPv = Object.values(pv).reduce((a,b)=>a+b,0);

  // summary per position
  const posMap = {};
  for (const r of rows) {
    if (!posMap[r.pos_id]) posMap[r.pos_id] = {
      pos_id:r.pos_id, desc:r.desc, pt:r.pt, pl:r.pl,
      rev:0, fixed:0, billboard:0, months: new Set()
    };
    const p = posMap[r.pos_id];
    p.rev += r.rev; p.fixed += r.fixed; p.billboard += r.billboard;
    p.months.add(r.month);
  }
  const summaryRows = Object.values(posMap).map(p => ({
    desc: p.desc,
    pl: p.pl,
    avg_monthly_rev: p.months.size ? p.rev / p.months.size : 0,
    rpm: totalPv ? p.rev / totalPv * 1000 : 0,
    fixed_pct: p.rev ? p.fixed / p.rev * 100 : 0,
    bb_pct: p.rev ? p.billboard / p.rev * 100 : 0,
    active_months: p.months.size,
  })).sort((a,b) => b.rpm - a.rpm);

  const summaryEl = document.getElementById('t2SummaryTable');
  summaryEl.innerHTML = '';
  summaryEl.appendChild(makeTable([
    {key:'desc', label:'توضیحات'},
    {key:'pl', label:'نوع'},
    {key:'avg_monthly_rev', label:'درآمد ماهانه', num:true, fmt:fmtComma},
    {key:'rpm', label:'RPM کل', num:true, fmt:v=>v.toFixed(3)},
    {key:'fixed_pct', label:'فیکس %', num:true, fmt:v=>v.toFixed(1)+'%'},
    {key:'bb_pct', label:'بیلبورد %', num:true, fmt:v=>v.toFixed(1)+'%'},
    {key:'active_months', label:'ماه‌های فعال', num:true},
  ], summaryRows, 'rpm'));

  // top 10 by rev for chart
  const top10 = Object.values(posMap)
    .sort((a,b)=>b.rev-a.rev).slice(0,10).map(p=>p.pos_id);

  const traces = [];
  for (const pos_id of top10) {
    const p = posMap[pos_id];
    const monthlyRows = rows.filter(r=>r.pos_id===pos_id).sort((a,b)=>a.month>b.month?1:-1);
    traces.push({
      type:'scatter', mode:'lines+markers',
      name: p.desc.substring(0,30),
      x: monthlyRows.map(r=>r.month),
      y: monthlyRows.map(r => pv[r.month] ? r.rev/pv[r.month]*1000 : null),
      marker:{size:6},
    });
  }
  Plotly.react('chartPosRpm', traces, {
    height:380,
    xaxis:{title:'ماه'}, yaxis:{title:'RPM'},
    legend:{orientation:'h', y:-0.35, x:0},
    margin:{t:20,b:100,l:60,r:10},
  }, {responsive:true});

  // populate position detail selector
  const sel = document.getElementById('t2PosDetail');
  const prevVal = sel.value;
  sel.innerHTML = '<option value="">— انتخاب کنید —</option>';
  Object.values(posMap).sort((a,b)=>b.rpm-a.rpm).forEach(p=>{
    const o = document.createElement('option');
    o.value = p.pos_id; o.textContent = p.desc.substring(0,50);
    sel.appendChild(o);
  });
  sel.value = prevVal;
  if (prevVal) renderPosDetail();
}

function renderPosDetail() {
  const posId = document.getElementById('t2PosDetail').value;
  const el = document.getElementById('posDetailCharts');
  el.innerHTML = '';
  if (!posId) return;

  const pv = pubMonthlyPv[selPid] || {};
  const rows = RAW.tab2_monthly
    .filter(r => r.pid === selPid && r.pos_id === posId)
    .sort((a,b) => a.month > b.month ? 1 : -1);

  const months = rows.map(r=>r.month);
  const revArr = rows.map(r=>r.rev);
  const rpmArr = rows.map(r => pv[r.month] ? r.rev/pv[r.month]*1000 : null);

  const divRev = document.createElement('div'); divRev.style.minHeight='280px';
  const divRpm = document.createElement('div'); divRpm.style.minHeight='280px';
  el.appendChild(divRev); el.appendChild(divRpm);

  Plotly.newPlot(divRev, [
    {type:'bar', x:months, y:revArr, marker:{color:'#4285F4'}}
  ], {title:'درآمد ماهانه', height:280, margin:{t:40,b:40,l:60,r:10}}, {responsive:true});

  Plotly.newPlot(divRpm, [
    {type:'scatter', mode:'lines+markers', x:months, y:rpmArr, line:{color:'#EA4335'}, marker:{size:7}}
  ], {title:'RPM ماهانه', height:280, margin:{t:40,b:40,l:60,r:10}}, {responsive:true});
}

// ─── TAB 3 ────────────────────────────────────────────────────────────────────
function getSimilarPubs() {
  const lw = parseFloat(document.getElementById('logWindow').value);
  const targetPv = RAW.pub_avg_pv[selPid];
  if (!targetPv || targetPv <= 0) return [];
  const tLog = Math.log10(targetPv);
  return Object.entries(RAW.pub_avg_pv)
    .filter(([pid, pv]) => pid !== selPid && pv > 0 && Math.abs(Math.log10(pv) - tLog) <= lw)
    .map(([pid]) => pid);
}

function renderTab3() {
  const simPids = getSimilarPubs();
  const targetPv = RAW.pub_avg_pv[selPid];
  const pubName = RAW.publishers.find(p=>String(p.id)===selPid)?.name || selPid;

  const simPvArr = pubMonthlyPv[selPid] ? Object.values(pubMonthlyPv[selPid]) : [];
  const nMonths = simPvArr.length || 1;
  const targetMonthlyPv = simPvArr.reduce((a,b)=>a+b,0) / nMonths;

  const simNamesList = simPids.map(pid => {
    const p = RAW.publishers.find(pp=>String(pp.id)===pid);
    return p ? `${p.name} (PV: ${fmtNum(RAW.pub_avg_pv[pid])})` : pid;
  });

  document.getElementById('simInfo').innerHTML =
    `<strong>${simPids.length} پابلیشر مشابه</strong> یافت شد — میانگین PV روزانه شما: <strong>${fmtNum(targetPv)}</strong><br>` +
    (simPids.length ? `<span style="color:#555;font-size:0.8rem">${simNamesList.join(' · ')}</span>` : '');

  if (!simPids.length) {
    document.getElementById('t3ScenTable').innerHTML = '<p style="color:#c0392b;padding:10px">هیچ پابلیشر مشابهی یافت نشد. بازه شباهت را افزایش دهید.</p>';
    document.getElementById('t3PricingTable').innerHTML = '';
    document.getElementById('t3Totals').innerHTML = '';
    return;
  }

  // Monthly RPM per similar publisher × position_label
  const simRows = RAW.tab2_monthly.filter(r => simPids.includes(r.pid));
  const pv = pubMonthlyPv;

  const rpmByLabel = {};
  // group simRows by pid × month × pl → sum rev, get pub monthly pv → rpm
  const grouped = {};
  for (const r of simRows) {
    const key = `${r.pid}||${r.month}||${r.pl}`;
    if (!grouped[key]) grouped[key] = {pid:r.pid, month:r.month, pl:r.pl, rev:0};
    grouped[key].rev += r.rev;
  }
  for (const g of Object.values(grouped)) {
    const mpv = pv[g.pid] && pv[g.pid][g.month];
    if (!mpv) continue;
    const rpm = g.rev / mpv * 1000;
    if (!rpmByLabel[g.pl]) rpmByLabel[g.pl] = [];
    rpmByLabel[g.pl].push(rpm);
  }

  const scenarios = Object.entries(rpmByLabel)
    .filter(([_, arr]) => arr.length >= 3)
    .map(([pl, arr]) => ({
      pl,
      bad: p25(arr),
      real: median(arr),
      good: p75(arr),
      n: arr.length,
    }))
    .sort((a,b) => b.real - a.real);

  const scenEl = document.getElementById('t3ScenTable');
  scenEl.innerHTML = '';
  scenEl.appendChild(makeTable([
    {key:'pl', label:'نوع پوزیشن'},
    {key:'bad',  label:'RPM بدبینانه',    num:true, fmt:v=>v.toFixed(3)},
    {key:'real', label:'RPM واقع‌بینانه', num:true, fmt:v=>v.toFixed(3)},
    {key:'good', label:'RPM خوش‌بینانه',  num:true, fmt:v=>v.toFixed(3)},
    {key:'n',    label:'نمونه‌ها',         num:true},
  ], scenarios, 'real'));

  // Pricing per target publisher's positions
  const targetRows = RAW.tab2_monthly.filter(r => r.pid === selPid);
  const posMap = {};
  for (const r of targetRows) {
    if (!posMap[r.pos_id]) posMap[r.pos_id] = {
      pos_id:r.pos_id, desc:r.desc, pl:r.pl,
      rev:0, fixed:0, billboard:0, months:new Set()
    };
    posMap[r.pos_id].rev += r.rev;
    posMap[r.pos_id].fixed += r.fixed;
    posMap[r.pos_id].billboard += r.billboard;
    posMap[r.pos_id].months.add(r.month);
  }

  const totalTargetPv = Object.values(pubMonthlyPv[selPid]||{}).reduce((a,b)=>a+b,0);
  const scenMap = Object.fromEntries(scenarios.map(s=>[s.pl,s]));

  const pricingRows = Object.values(posMap).map(p => {
    const s = scenMap[p.pl];
    const curRpm = totalTargetPv ? p.rev/totalTargetPv*1000 : 0;
    const curMonthly = p.months.size ? p.rev/p.months.size : 0;
    return {
      desc: p.desc,
      pl: p.pl,
      cur_monthly: curMonthly,
      cur_rpm: curRpm,
      rpm_bad:  s?.bad  ?? null,
      rpm_real: s?.real ?? null,
      rpm_good: s?.good ?? null,
      rev_bad:  s ? s.bad  / 1000 * targetMonthlyPv : null,
      rev_real: s ? s.real / 1000 * targetMonthlyPv : null,
      rev_good: s ? s.good / 1000 * targetMonthlyPv : null,
      has_fixed: p.fixed > 0 ? '✅' : '',
      has_bb: p.billboard > 0 ? '✅' : '',
    };
  }).sort((a,b) => (b.rev_real||0) - (a.rev_real||0));

  const pricingEl = document.getElementById('t3PricingTable');
  pricingEl.innerHTML = '';
  pricingEl.appendChild(makeTable([
    {key:'desc',      label:'توضیحات'},
    {key:'pl',        label:'نوع پوزیشن'},
    {key:'cur_monthly',label:'درآمد ماهانه فعلی', num:true, fmt:fmtComma},
    {key:'cur_rpm',   label:'RPM فعلی',       num:true, fmt:v=>v.toFixed(3)},
    {key:'rpm_bad',   label:'RPM بدبینانه',   num:true, fmt:v=>v!=null?v.toFixed(3):'—'},
    {key:'rpm_real',  label:'RPM واقع‌بینانه',num:true, fmt:v=>v!=null?v.toFixed(3):'—'},
    {key:'rpm_good',  label:'RPM خوش‌بینانه', num:true, fmt:v=>v!=null?v.toFixed(3):'—'},
    {key:'rev_bad',   label:'درآمد بدبینانه', num:true, fmt:v=>v!=null?fmtComma(v):'—'},
    {key:'rev_real',  label:'درآمد واقع‌بینانه',num:true, fmt:v=>v!=null?fmtComma(v):'—'},
    {key:'rev_good',  label:'درآمد خوش‌بینانه',num:true, fmt:v=>v!=null?fmtComma(v):'—'},
    {key:'has_fixed', label:'فیکس'},
    {key:'has_bb',    label:'بیلبورد'},
  ], pricingRows, 'rev_real'));

  // Totals
  const totBad  = pricingRows.reduce((s,r)=>s+(r.rev_bad||0),0);
  const totReal = pricingRows.reduce((s,r)=>s+(r.rev_real||0),0);
  const totGood = pricingRows.reduce((s,r)=>s+(r.rev_good||0),0);

  document.getElementById('t3Totals').innerHTML = `
    <div class="scenario-card bad">
      <div class="s-label">📉 بدبینانه</div>
      <div class="s-value">${fmtNum(totBad,' ت')}</div>
    </div>
    <div class="scenario-card real">
      <div class="s-label">📊 واقع‌بینانه</div>
      <div class="s-value">${fmtNum(totReal,' ت')}</div>
    </div>
    <div class="scenario-card good">
      <div class="s-label">📈 خوش‌بینانه</div>
      <div class="s-value">${fmtNum(totGood,' ت')}</div>
    </div>
  `;
}

// ─── tabs ─────────────────────────────────────────────────────────────────────
function showTab(id, btn) {
  document.querySelectorAll('.tab-content').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el=>el.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}

// ─── boot ─────────────────────────────────────────────────────────────────────
onPubChange();
</script>
</body>
</html>
"""

with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("✅ dashboard.html generated successfully.")
