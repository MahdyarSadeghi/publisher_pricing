"""
Generates a standalone dashboard.html — no server needed.
Usage: python3 generate_html.py
"""
import json
import numpy as np
import pandas as pd

# ─── Jalali (Shamsi) conversion ───────────────────────────────────────────────

JALALI_MONTHS_FA = [
    'فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور',
    'مهر','آبان','آذر','دی','بهمن','اسفند'
]

def gregorian_to_jalali(gy, gm, gd):
    if gy > 1600:
        jy, gy = 979, gy - 1600
    else:
        jy, gy = 0, gy - 621
    gy2 = gy + 1 if gm > 2 else gy
    g2j = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    days = (365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400
            - 80 + gd + g2j[gm-1])
    jy += 33*(days//12053); days %= 12053
    jy += 4*(days//1461);   days %= 1461
    if days > 365:
        jy += (days-1)//365; days = (days-1)%365
    if days < 186:
        jm, jd = 1 + days//31, 1 + days%31
    else:
        days -= 186
        jm, jd = 7 + days//30, 1 + days%30
    return jy, jm, jd

def month_to_fa(month_str):
    y, m = int(month_str[:4]), int(month_str[5:7])
    jy, jm, _ = gregorian_to_jalali(y, m, 1)
    return f"{JALALI_MONTHS_FA[jm-1]} {jy}"

# ─── Load & classify ──────────────────────────────────────────────────────────

df = pd.read_excel("daily_position_details.xlsx")
df["date"] = pd.to_datetime(df["date"])
df["month"] = df["date"].dt.to_period("M").astype(str)

LOCATION_RULES = [
    (["شناور","sticky","چسبنده","چسبان"],             "شناور"),
    (["سایدبار","sidebar","کناری","جانبی"],           "سایدبار"),
    (["میان مطلب","میانی","میان","وسط","بین مطلب"],   "میانی"),
    (["بالا","بالای","اول","ابتدا","هدر","header","سردبیر"], "بالا"),
    (["پایین","پایینی","آخر","انتها","فوتر","footer"], "پایین"),
]

def classify(desc, pt):
    tags = [lbl for kws, lbl in LOCATION_RULES if any(k in str(desc) for k in kws)]
    return f"{pt} | {' · '.join(tags)}" if tags else pt

df["pl"] = df.apply(lambda r: classify(r["description"], r["position_type"]), axis=1)

# publisher daily PV (same for all positions of same pub+day)
daily_pv = (
    df.groupby(["publisher_id","date"])["page_views"].max()
    .reset_index().rename(columns={"page_views":"pub_daily_pv"})
)
df = df.merge(daily_pv, on=["publisher_id","date"])

# Jalali month display
months_unique = df["month"].unique()
month_fa_map = {m: month_to_fa(m) for m in months_unique}
df["mf"] = df["month"].map(month_fa_map)

# ─── Build data structures ───────────────────────────────────────────────────

publishers = (
    df[["publisher_id","publisher_name"]].drop_duplicates()
    .sort_values("publisher_name")
    .rename(columns={"publisher_id":"id","publisher_name":"name"})
    .to_dict("records")
)

pub_avg_pv = {
    str(k): int(round(v))
    for k, v in daily_pv.groupby("publisher_id")["pub_daily_pv"].mean().items()
}

# pub_monthly_pv: pid × month → pv
pmp = (
    daily_pv.assign(month=lambda x: pd.to_datetime(x["date"]).dt.to_period("M").astype(str))
    .groupby(["publisher_id","month"])["pub_daily_pv"].sum().reset_index()
    .rename(columns={"pub_daily_pv":"pv","publisher_id":"pid"})
)
pmp["pid"] = pmp["pid"].astype(str)
pmp["mf"] = pmp["month"].map(month_fa_map)

# tab1: pid × month × position_label → revenue
tab1 = (
    df.groupby(["publisher_id","month","mf","pl"])
    .agg(rev=("total_adv_cost","sum"), fixed=("fixed_adv_cost","sum"),
         billboard=("billboard_adv_cost","sum"))
    .reset_index()
    .rename(columns={"publisher_id":"pid"})
)
tab1["pid"] = tab1["pid"].astype(str)

# tab2_monthly: pid × month × position → revenue
tab2 = (
    df.groupby(["publisher_id","month","mf","position_id","description","pl"])
    .agg(rev=("total_adv_cost","sum"), fixed=("fixed_adv_cost","sum"),
         billboard=("billboard_adv_cost","sum"))
    .reset_index()
    .rename(columns={"publisher_id":"pid","position_id":"pos_id","description":"desc"})
)
tab2["pid"] = tab2["pid"].astype(str)
tab2["pos_id"] = tab2["pos_id"].astype(str)

DATA = {
    "publishers":    publishers,
    "pub_avg_pv":    pub_avg_pv,
    "pub_monthly_pv": pmp.to_dict("records"),
    "tab1":          tab1.to_dict("records"),
    "tab2_monthly":  tab2.to_dict("records"),
}
data_json = json.dumps(DATA, ensure_ascii=False)

print(f"publishers:{len(publishers)}  tab1:{len(tab1)}  tab2:{len(tab2)}  pmp:{len(pmp)}")

# ─── HTML ─────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Publisher Pricing Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Tahoma,'Vazir',sans-serif;background:#eef0f5;color:#222;direction:rtl}

/* ── topbar ── */
.topbar{
  background:#16213e;color:#fff;
  padding:12px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap;
}
.topbar h1{font-size:1.05rem;flex:1;white-space:nowrap}
.topbar .ctrl{display:flex;flex-direction:column;gap:3px}
.topbar label{font-size:0.73rem;color:#aab}
.topbar select,.topbar input[type=range]{
  padding:5px 9px;border-radius:6px;border:none;
  font-family:Tahoma,sans-serif;font-size:0.85rem;
  background:#fff;min-width:200px;cursor:pointer
}
.topbar .range-row{display:flex;align-items:center;gap:8px}
.topbar .range-val{font-size:0.85rem;min-width:28px}

/* ── kpis ── */
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:16px 24px 0}
.kpi{background:#fff;border-radius:10px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.kpi .lbl{font-size:0.72rem;color:#888;margin-bottom:3px}
.kpi .val{font-size:1.35rem;font-weight:bold;color:#16213e}

/* ── tabs ── */
.tabs-bar{display:flex;padding:16px 24px 0;gap:4px}
.tab-btn{
  padding:9px 24px;background:#d8dce8;border:none;cursor:pointer;
  font-family:Tahoma,sans-serif;font-size:0.87rem;
  border-radius:8px 8px 0 0;color:#555;transition:background .15s
}
.tab-btn.active{background:#fff;color:#16213e;font-weight:bold;box-shadow:0 -1px 4px rgba(0,0,0,.06)}

/* ── tab panels ── */
.tab-panel{
  display:none;background:#fff;
  margin:0 24px 24px;border-radius:0 0 10px 10px;
  padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);
  overflow-y:auto;max-height:calc(100vh - 200px)
}
.tab-panel.active{display:block}

/* ── section title ── */
.sec{
  font-size:0.93rem;font-weight:bold;color:#16213e;
  border-right:3px solid #4285F4;padding-right:8px;
  margin:22px 0 12px
}
.sec:first-child{margin-top:0}

/* ── filter row ── */
.frow{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.frow label{font-size:0.8rem;color:#666;white-space:nowrap}
.frow select{
  padding:5px 9px;border-radius:6px;border:1px solid #dde;
  font-family:Tahoma,sans-serif;font-size:0.82rem;cursor:pointer
}

/* ── two-col chart layout ── */
.chart2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:4px}

/* ── tables ── */
.tbl-wrap{overflow-x:auto;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:0.81rem}
thead th{
  background:#f0f3fa;padding:8px 10px;
  text-align:center;font-weight:bold;
  cursor:pointer;user-select:none;white-space:nowrap
}
thead th:hover{background:#e2e7f5}
tbody td{padding:7px 10px;border-bottom:1px solid #f0f0f0;text-align:center}
tbody tr:hover{background:#f8faff}

/* ── pricing cards ── */
.pl-cards{display:flex;flex-direction:column;gap:16px;margin-top:4px}
.pl-card{border:1px solid #e0e4f0;border-radius:10px;overflow:hidden}
.pl-card-hdr{
  background:#16213e;color:#fff;
  padding:10px 16px;font-size:0.88rem;font-weight:bold
}
.pl-card-body{padding:14px 16px;display:flex;flex-direction:column;gap:12px}

.scen-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.scen{border-radius:8px;padding:10px;text-align:center;font-size:0.82rem}
.scen.bad {background:#fde8e8;color:#a93226}
.scen.real{background:#fff8e1;color:#a04000}
.scen.good{background:#e8f5e9;color:#1e7f3e}
.scen .sv{font-size:1.4rem;font-weight:bold;margin-top:3px}

.target-sec{background:#f4f7ff;border-radius:8px;padding:10px 12px}
.target-sec .tsec-lbl{font-size:0.76rem;color:#555;margin-bottom:6px;font-weight:bold}
.target-pos{font-size:0.8rem;padding:3px 0;border-bottom:1px solid #e8ecf5}
.target-pos:last-child{border-bottom:none}

.sim-info{
  background:#eef3ff;border-radius:8px;
  padding:10px 14px;font-size:0.82rem;margin-bottom:16px;
  line-height:1.7
}
.sim-pubs{color:#555;font-size:0.78rem}

/* ── no-data ── */
.nodata{color:#999;padding:20px;text-align:center;font-size:0.85rem}

@media(max-width:700px){
  .kpis{grid-template-columns:1fr 1fr}
  .chart2{grid-template-columns:1fr}
  .scen-row{grid-template-columns:1fr}
}
</style>
</head>
<body>

<!-- ── Topbar ── -->
<div class="topbar">
  <h1>📊 Publisher Pricing Dashboard</h1>
  <div class="ctrl">
    <label>پابلیشر</label>
    <select id="pubSel" onchange="boot()"></select>
  </div>
  <div class="ctrl">
    <label>بازه شباهت (log scale)</label>
    <div class="range-row">
      <input type="range" id="logW" min="0.3" max="1.2" step="0.1" value="0.6"
             oninput="document.getElementById('lwv').textContent=this.value;renderTab2()">
      <span class="range-val" id="lwv">0.6</span>
    </div>
  </div>
</div>

<!-- ── KPIs ── -->
<div class="kpis">
  <div class="kpi"><div class="lbl">میانگین درآمد ماهانه</div><div class="val" id="k1">—</div></div>
  <div class="kpi"><div class="lbl">میانگین PV روزانه</div><div class="val" id="k2">—</div></div>
  <div class="kpi"><div class="lbl">پوزیشن‌های فعال</div><div class="val" id="k3">—</div></div>
  <div class="kpi"><div class="lbl">RPM میانگین</div><div class="val" id="k4">—</div></div>
</div>

<!-- ── Tabs ── -->
<div class="tabs-bar">
  <button class="tab-btn active" onclick="showTab('t1',this)">📈 عملکرد ناشر</button>
  <button class="tab-btn" onclick="showTab('t2',this)">💰 قیمت‌گذاری</button>
</div>

<!-- ── Tab 1 ── -->
<div id="t1" class="tab-panel active">

  <div class="sec">نمای کلی</div>
  <div class="frow">
    <label>فیلتر دسته‌بندی:</label>
    <select id="t1f" onchange="renderOverview()"></select>
  </div>
  <div class="chart2">
    <div id="cRev" style="min-height:320px"></div>
    <div id="cRpm" style="min-height:320px"></div>
  </div>

  <div class="sec">پوزیشن‌ها</div>
  <div class="frow">
    <label>فیلتر دسته‌بندی:</label>
    <select id="t2f" onchange="renderPositions()"></select>
  </div>
  <div class="tbl-wrap" id="posTbl"></div>

  <div style="margin-top:16px" id="cPosRpm" style="min-height:360px"></div>

  <div class="sec">جزئیات پوزیشن</div>
  <div class="frow">
    <label>پوزیشن:</label>
    <select id="posDetSel" onchange="renderPosDetail()">
      <option value="">— انتخاب کنید —</option>
    </select>
  </div>
  <div class="chart2" id="cPosDetail"></div>

</div>

<!-- ── Tab 2 ── -->
<div id="t2" class="tab-panel">
  <div id="simInfo" class="sim-info"></div>
  <div id="plCards" class="pl-cards"></div>

  <div class="sec">جمع کل ماهانه تخمینی</div>
  <div class="scen-row" id="totals" style="max-width:500px"></div>
</div>

<script>
const RAW = """ + data_json + r""";

// ─── helpers ──────────────────────────────────────────────────────────────────
const fmtN = (n,s='') => {
  if(n==null||isNaN(n)) return '—';
  if(Math.abs(n)>=1e9) return (n/1e9).toFixed(1)+'B'+s;
  if(Math.abs(n)>=1e6) return (n/1e6).toFixed(1)+'M'+s;
  if(Math.abs(n)>=1e3) return (n/1e3).toFixed(0)+'K'+s;
  return n.toFixed(0)+s;
};
const fmtC = n => n==null||isNaN(n) ? '—' : Math.round(n).toLocaleString();
const rpmRound = v => v==null||isNaN(v) ? '—' : String(Math.round(v));

function quantile(arr, q) {
  const s=[...arr].sort((a,b)=>a-b), pos=(s.length-1)*q;
  const lo=Math.floor(pos),hi=Math.ceil(pos);
  return s[lo]+(s[hi]-s[lo])*(pos-lo);
}
const p25 = a => a.length ? quantile(a,.25) : null;
const med = a => a.length ? quantile(a,.5)  : null;
const p75 = a => a.length ? quantile(a,.75) : null;

// Build lookup: pubMonthPv[pid][month] = pv
const pubMonthPv = {};
for(const r of RAW.pub_monthly_pv){
  if(!pubMonthPv[r.pid]) pubMonthPv[r.pid]={};
  pubMonthPv[r.pid][r.month]=r.pv;
}
// also build month → mf (Farsi display) map
const monthFa = {};
for(const r of RAW.pub_monthly_pv) monthFa[r.month]=r.mf;

// ─── state ────────────────────────────────────────────────────────────────────
let selPid = null;

// ─── init ─────────────────────────────────────────────────────────────────────
const pubSel = document.getElementById('pubSel');
RAW.publishers.forEach(p=>{
  const o=document.createElement('option');
  o.value=String(p.id); o.textContent=p.name;
  pubSel.appendChild(o);
});
selPid = String(RAW.publishers[0].id);
pubSel.value = selPid;

function boot(){
  selPid = pubSel.value;
  updateKpis();
  populateFilters();
  renderOverview();
  renderPositions();
  document.getElementById('posDetSel').value='';
  document.getElementById('cPosDetail').innerHTML='';
  renderTab2();
}

// ─── KPIs ─────────────────────────────────────────────────────────────────────
function updateKpis(){
  const rows = RAW.tab1.filter(r=>r.pid===selPid);
  const pv = pubMonthPv[selPid]||{};
  const months=[...new Set(rows.map(r=>r.month))].sort();
  const totalRev = rows.reduce((s,r)=>s+r.rev,0);
  const avgMonRev = months.length ? totalRev/months.length : 0;
  const pvArr=Object.values(pv);
  const avgMonPv = pvArr.length ? pvArr.reduce((a,b)=>a+b)/pvArr.length : 0;
  const totalPv = pvArr.reduce((a,b)=>a+b,0);
  const rpm = totalPv ? totalRev/totalPv : 0;
  const nPos = new Set(RAW.tab2_monthly.filter(r=>r.pid===selPid).map(r=>r.pos_id)).size;

  document.getElementById('k1').textContent = fmtN(avgMonRev,' ت');
  document.getElementById('k2').textContent = fmtN(avgMonPv/30);
  document.getElementById('k3').textContent = nPos;
  document.getElementById('k4').textContent = rpmRound(rpm);
}

// ─── populate filters ─────────────────────────────────────────────────────────
function populateFilters(){
  const pls=[...new Set(RAW.tab2_monthly.filter(r=>r.pid===selPid).map(r=>r.pl))].sort();
  ['t1f','t2f'].forEach(id=>{
    const el=document.getElementById(id);
    el.innerHTML='<option value="">همه</option>';
    pls.forEach(pl=>{const o=document.createElement('option');o.value=pl;o.textContent=pl;el.appendChild(o);});
  });
  // position detail selector
  const byRev={};
  RAW.tab2_monthly.filter(r=>r.pid===selPid).forEach(r=>{
    if(!byRev[r.pos_id]) byRev[r.pos_id]={desc:r.desc,rev:0};
    byRev[r.pos_id].rev+=r.rev;
  });
  const sel=document.getElementById('posDetSel');
  sel.innerHTML='<option value="">— انتخاب کنید —</option>';
  Object.entries(byRev).sort((a,b)=>b[1].rev-a[1].rev).forEach(([pid,d])=>{
    const o=document.createElement('option');
    o.value=pid; o.textContent=d.desc.substring(0,50);
    sel.appendChild(o);
  });
}

// ─── Tab 1: Overview ──────────────────────────────────────────────────────────
function renderOverview(){
  const filt = document.getElementById('t1f').value;
  const pv = pubMonthPv[selPid]||{};

  let rows = RAW.tab1.filter(r=>r.pid===selPid);
  if(filt) rows = rows.filter(r=>r.pl===filt);

  const byMonth={};
  rows.forEach(r=>{
    if(!byMonth[r.month]) byMonth[r.month]={rev:0,fixed:0,bb:0,mf:r.mf};
    byMonth[r.month].rev+=r.rev;
    byMonth[r.month].fixed+=r.fixed;
    byMonth[r.month].bb+=r.billboard;
  });
  const months=Object.keys(byMonth).sort();
  const mf=months.map(m=>byMonth[m].mf);
  const rev=months.map(m=>byMonth[m].rev);
  const fix=months.map(m=>byMonth[m].fixed);
  const bb=months.map(m=>byMonth[m].bb);
  const rpm=months.map(m=>pv[m]?Math.round(byMonth[m].rev/pv[m]):null);

  Plotly.react('cRev',[
    {type:'bar',x:mf,y:rev,name:'کل درآمد',marker:{color:'#4285F4'},opacity:.9},
    {type:'bar',x:mf,y:fix,name:'فیکس',marker:{color:'#34A853'},opacity:.85},
    {type:'bar',x:mf,y:bb,name:'بیلبورد',marker:{color:'#FBBC04'},opacity:.85},
  ],{
    title:'درآمد ماهانه (تومان)',barmode:'overlay',height:320,
    xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'تومان'},
    legend:{orientation:'h',y:1.18},
    margin:{t:50,b:70,l:60,r:10},
  },{responsive:true});

  Plotly.react('cRpm',[
    {type:'scatter',mode:'lines+markers',x:mf,y:rpm,
     line:{color:'#EA4335',width:2},marker:{size:7}},
  ],{
    title:'RPM ماهانه',height:320,
    xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'RPM (تومان/پیج‌ویو)'},
    margin:{t:50,b:70,l:60,r:10},
  },{responsive:true});
}

// ─── Tab 1: Positions table + chart ──────────────────────────────────────────
function renderPositions(){
  const filt = document.getElementById('t2f').value;
  const pv = pubMonthPv[selPid]||{};
  const totalPv = Object.values(pv).reduce((a,b)=>a+b,0);

  let rows = RAW.tab2_monthly.filter(r=>r.pid===selPid);
  if(filt) rows = rows.filter(r=>r.pl===filt);

  // summary per position
  const pm={};
  rows.forEach(r=>{
    if(!pm[r.pos_id]) pm[r.pos_id]={desc:r.desc,pl:r.pl,rev:0,fixed:0,bb:0,months:new Set()};
    pm[r.pos_id].rev+=r.rev; pm[r.pos_id].fixed+=r.fixed;
    pm[r.pos_id].bb+=r.billboard; pm[r.pos_id].months.add(r.month);
  });
  const sumRows=Object.values(pm).map(p=>({
    desc:p.desc, pl:p.pl,
    avgRev: p.months.size ? p.rev/p.months.size : 0,
    rpm: totalPv ? p.rev/totalPv : 0,
    fPct: p.rev ? p.fixed/p.rev*100 : 0,
    bbPct: p.rev ? p.bb/p.rev*100 : 0,
    months: p.months.size,
  })).sort((a,b)=>b.rpm-a.rpm);

  // table
  const wrap = document.getElementById('posTbl');
  wrap.innerHTML='';
  let sortCol='rpm', sortAsc=false;
  function buildTbl(){
    const sorted=[...sumRows].sort((a,b)=>{
      const va=a[sortCol],vb=b[sortCol];
      if(va==null&&vb==null)return 0;
      if(va==null)return 1; if(vb==null)return -1;
      return sortAsc?(va>vb?1:-1):(va<vb?1:-1);
    });
    const cols=[
      {k:'desc',   l:'توضیحات',         f:v=>v.substring(0,40)},
      {k:'pl',     l:'دسته‌بندی',        f:v=>v},
      {k:'avgRev', l:'درآمد ماهانه',     f:fmtC},
      {k:'rpm',    l:'RPM',             f:rpmRound},
      {k:'fPct',   l:'فیکس %',          f:v=>v.toFixed(1)+'%'},
      {k:'bbPct',  l:'بیلبورد %',       f:v=>v.toFixed(1)+'%'},
      {k:'months', l:'ماه‌های فعال',     f:v=>String(v)},
    ];
    let h=`<table><thead><tr>`;
    cols.forEach(c=>{ h+=`<th onclick="sortPosTbl('${c.k}')">${c.l}${sortCol===c.k?(sortAsc?'▲':'▼'):''}</th>`; });
    h+=`</tr></thead><tbody>`;
    sorted.forEach(r=>{ h+=`<tr>${cols.map(c=>`<td>${c.f(r[c.k])}</td>`).join('')}</tr>`; });
    h+=`</tbody></table>`;
    wrap.innerHTML=h;
  }
  window.sortPosTbl=(col)=>{ if(sortCol===col)sortAsc=!sortAsc; else{sortCol=col;sortAsc=false;} buildTbl(); };
  buildTbl();

  // top 10 RPM trend chart
  const top10ids = Object.entries(pm).sort((a,b)=>b[1].rev-a[1].rev).slice(0,10).map(e=>e[0]);
  const traces=[];
  top10ids.forEach(posId=>{
    const p=pm[posId];
    const mr=rows.filter(r=>r.pos_id===posId).sort((a,b)=>a.month>b.month?1:-1);
    traces.push({
      type:'scatter',mode:'lines+markers',
      name:p.desc.substring(0,30),
      x:mr.map(r=>monthFa[r.month]||r.month),
      y:mr.map(r=>pv[r.month]?Math.round(r.rev/pv[r.month]):null),
      marker:{size:5},
    });
  });
  Plotly.react('cPosRpm', traces, {
    title:'ترند RPM ماهانه — ۱۰ پوزیشن برتر',
    height:370,
    xaxis:{title:'ماه',tickangle:-30},
    yaxis:{title:'RPM'},
    legend:{orientation:'h',y:-0.35,x:0},
    margin:{t:40,b:110,l:60,r:10},
  },{responsive:true});
}

// ─── Tab 1: Position detail ───────────────────────────────────────────────────
function renderPosDetail(){
  const posId=document.getElementById('posDetSel').value;
  const el=document.getElementById('cPosDetail');
  el.innerHTML='';
  if(!posId) return;

  const pv=pubMonthPv[selPid]||{};
  const rows=RAW.tab2_monthly.filter(r=>r.pid===selPid&&r.pos_id===posId)
    .sort((a,b)=>a.month>b.month?1:-1);

  const xArr=rows.map(r=>monthFa[r.month]||r.month);
  const revArr=rows.map(r=>r.rev);
  const rpmArr=rows.map(r=>pv[r.month]?Math.round(r.rev/pv[r.month]):null);

  const d1=document.createElement('div');d1.style.minHeight='270px';
  const d2=document.createElement('div');d2.style.minHeight='270px';
  el.appendChild(d1);el.appendChild(d2);

  Plotly.newPlot(d1,[{type:'bar',x:xArr,y:revArr,marker:{color:'#4285F4'}}],
    {title:'درآمد ماهانه',height:270,xaxis:{tickangle:-30},yaxis:{title:'تومان'},
     margin:{t:40,b:70,l:60,r:10}},{responsive:true});
  Plotly.newPlot(d2,[{type:'scatter',mode:'lines+markers',x:xArr,y:rpmArr,
    line:{color:'#EA4335',width:2},marker:{size:7}}],
    {title:'RPM ماهانه',height:270,xaxis:{tickangle:-30},yaxis:{title:'RPM'},
     margin:{t:40,b:70,l:60,r:10}},{responsive:true});
}

// ─── Tab 2: Pricing ───────────────────────────────────────────────────────────
function getSimilarPids(){
  const lw=parseFloat(document.getElementById('logW').value);
  const tPv=RAW.pub_avg_pv[selPid];
  if(!tPv||tPv<=0) return [];
  const tLog=Math.log10(tPv);
  return Object.entries(RAW.pub_avg_pv)
    .filter(([pid,pv])=>pid!==selPid&&pv>0&&Math.abs(Math.log10(pv)-tLog)<=lw)
    .map(([pid])=>pid);
}

function renderTab2(){
  const simPids=getSimilarPids();
  const tPv=RAW.pub_avg_pv[selPid];

  // Similarity info
  const simNames=simPids.map(pid=>{
    const p=RAW.publishers.find(x=>String(x.id)===pid);
    return p?`${p.name} (${fmtN(RAW.pub_avg_pv[pid])})`:pid;
  });
  document.getElementById('simInfo').innerHTML=
    `<strong>${simPids.length} ناشر مشابه</strong> بر اساس میانگین PV روزانه <strong>${fmtN(tPv)}</strong><br>`+
    (simNames.length ? `<span class="sim-pubs">${simNames.join(' &nbsp;·&nbsp; ')}</span>` : '');

  if(!simPids.length){
    document.getElementById('plCards').innerHTML='<div class="nodata">هیچ ناشر مشابهی یافت نشد — بازه شباهت را افزایش دهید.</div>';
    document.getElementById('totals').innerHTML='';
    return;
  }

  // Target publisher data
  const tPvByMonth=pubMonthPv[selPid]||{};
  const totalTPv=Object.values(tPvByMonth).reduce((a,b)=>a+b,0);
  const nMonths=Object.keys(tPvByMonth).length||1;
  const targetMonPv=totalTPv/nMonths;

  // Target positions grouped by pl
  const tPosByPl={};
  RAW.tab2_monthly.filter(r=>r.pid===selPid).forEach(r=>{
    if(!tPosByPl[r.pl]) tPosByPl[r.pl]={};
    if(!tPosByPl[r.pl][r.pos_id]) tPosByPl[r.pl][r.pos_id]={desc:r.desc,rev:0,months:new Set()};
    tPosByPl[r.pl][r.pos_id].rev+=r.rev;
    tPosByPl[r.pl][r.pos_id].months.add(r.month);
  });

  // Similar publishers data grouped by pl → pid → monthly
  const simRows=RAW.tab2_monthly.filter(r=>simPids.includes(r.pid));
  const plData={};  // pl → pid → [{month, rev, rpm}]
  simRows.forEach(r=>{
    const mpv=pubMonthPv[r.pid]&&pubMonthPv[r.pid][r.month];
    if(!mpv) return;
    const rpm=r.rev/mpv;
    if(!plData[r.pl]) plData[r.pl]={};
    if(!plData[r.pl][r.pid]) plData[r.pl][r.pid]=[];
    plData[r.pl][r.pid].push({month:r.month,mf:monthFa[r.month]||r.month,rev:r.rev,rpm});
  });

  // Build cards — prioritize labels where target publisher has positions
  const allPls=Object.keys(plData);
  allPls.sort((a,b)=>{
    const ha=tPosByPl[a]?1:0, hb=tPosByPl[b]?1:0;
    return hb-ha;
  });

  let totalBad=0, totalReal=0, totalGood=0;

  const cardsHtml=allPls.map(pl=>{
    const pubData=plData[pl];

    // Collect all RPM values + per-pub summary
    const allRpms=[];
    const pubRows=[];
    Object.entries(pubData).forEach(([pid,months])=>{
      const pub=RAW.publishers.find(x=>String(x.id)===pid);
      const name=pub?pub.name:pid;
      const rpms=months.map(m=>m.rpm);
      const avgRpm=rpms.reduce((a,b)=>a+b)/rpms.length;
      allRpms.push(...rpms);
      // last month RPM
      const latest=[...months].sort((a,b)=>a.month>b.month?-1:1)[0];
      pubRows.push({name, avgRpm:Math.round(avgRpm), n:months.length,
                    lastMonRpm:Math.round(latest.rpm), lastMon:latest.mf});
    });
    pubRows.sort((a,b)=>b.avgRpm-a.avgRpm);

    const p25v=p25(allRpms), medv=med(allRpms), p75v=p75(allRpms);

    // target positions section
    const tPos=tPosByPl[pl]||{};
    const tPosHtml=Object.values(tPos).map(p=>{
      const curRpm=totalTPv?Math.round(p.rev/totalTPv):0;
      const avgMon=p.months.size?Math.round(p.rev/p.months.size):0;
      return `<div class="target-pos">
        • ${p.desc}
        &nbsp;—&nbsp; RPM فعلی: <strong>${curRpm}</strong>
        &nbsp;|&nbsp; درآمد ماهانه فعلی: <strong>${fmtC(avgMon)} ت</strong>
      </div>`;
    }).join('');

    // accumulate totals (only for labels where target has positions)
    if(Object.keys(tPos).length){
      totalBad  += (p25v||0)/1*targetMonPv;
      totalReal += (medv||0)/1*targetMonPv;
      totalGood += (p75v||0)/1*targetMonPv;
    }

    const pubTableRows=pubRows.map(r=>`<tr>
      <td>${r.name}</td>
      <td>${r.avgRpm}</td>
      <td>${r.n}</td>
      <td>${r.lastMonRpm} <small style="color:#999">(${r.lastMon})</small></td>
    </tr>`).join('');

    return `
    <div class="pl-card">
      <div class="pl-card-hdr">🎯 ${pl}</div>
      <div class="pl-card-body">
        <div class="tbl-wrap">
          <table>
            <thead><tr>
              <th>ناشر مشابه</th>
              <th>RPM میانگین</th>
              <th>ماه‌های فعال</th>
              <th>آخرین RPM</th>
            </tr></thead>
            <tbody>${pubTableRows}</tbody>
          </table>
        </div>
        <div class="scen-row">
          <div class="scen bad">📉 بدبینانه<div class="sv">${rpmRound(p25v)}</div></div>
          <div class="scen real">📊 واقع‌بینانه<div class="sv">${rpmRound(medv)}</div></div>
          <div class="scen good">📈 خوش‌بینانه<div class="sv">${rpmRound(p75v)}</div></div>
        </div>
        ${tPosHtml ? `<div class="target-sec">
          <div class="tsec-lbl">پوزیشن‌های این ناشر در این دسته:</div>
          ${tPosHtml}
        </div>` : ''}
      </div>
    </div>`;
  }).join('');

  document.getElementById('plCards').innerHTML=cardsHtml||'<div class="nodata">داده‌ای برای نمایش وجود ندارد.</div>';

  document.getElementById('totals').innerHTML=`
    <div class="scen bad">📉 بدبینانه<div class="sv">${fmtN(totalBad,' ت')}</div></div>
    <div class="scen real">📊 واقع‌بینانه<div class="sv">${fmtN(totalReal,' ت')}</div></div>
    <div class="scen good">📈 خوش‌بینانه<div class="sv">${fmtN(totalGood,' ت')}</div></div>
  `;
}

// ─── tab switching ────────────────────────────────────────────────────────────
function showTab(id,btn){
  document.querySelectorAll('.tab-panel').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}

// ─── boot ─────────────────────────────────────────────────────────────────────
boot();
</script>
</body>
</html>
""" + ""  # end of triple-quote

with open("dashboard.html","w",encoding="utf-8") as f:
    f.write(HTML)
print("✅ dashboard.html written.")
