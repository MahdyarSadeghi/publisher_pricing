"""
Generates a standalone dashboard.html — no server needed.
Usage: python3 generate_html.py
"""
import json
import numpy as np
import pandas as pd

# ─── Jalali ───────────────────────────────────────────────────────────────────
JALALI_MONTHS_FA = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور',
                    'مهر','آبان','آذر','دی','بهمن','اسفند']

def gregorian_to_jalali(gy, gm, gd):
    if gy > 1600: jy, gy = 979, gy - 1600
    else:         jy, gy = 0,   gy - 621
    gy2 = gy + 1 if gm > 2 else gy
    g2j = [0,31,59,90,120,151,181,212,243,273,304,334]
    days = 365*gy + (gy2+3)//4 - (gy2+99)//100 + (gy2+399)//400 - 80 + gd + g2j[gm-1]
    jy += 33*(days//12053); days %= 12053
    jy += 4*(days//1461);   days %= 1461
    if days > 365: jy += (days-1)//365; days = (days-1)%365
    if days < 186: jm, jd = 1 + days//31, 1 + days%31
    else:          days -= 186; jm, jd = 7 + days//30, 1 + days%30
    return jy, jm, jd

def month_to_fa(m):
    y, mo = int(m[:4]), int(m[5:7])
    jy, jm, _ = gregorian_to_jalali(y, mo, 1)
    return f"{JALALI_MONTHS_FA[jm-1]} {jy}"

# ─── Business position names ──────────────────────────────────────────────────
PT_NAMES = {
    'banner-article':         'بنر',
    'banner-sticky':          'بنر استیکی',
    'article-display':        'نیتیو',
    'article-display-card':   'نیتیو کارتی',
    'article-display-sticky': 'نیتیو استیکی',
    'article-text':           'نیتیو متنی',
    'notification':           'نوتیف',
    'footer-sticky':          'فوتر استیکی',
    'slider':                 'اسلایدر',
    'pre_roll':               'پری‌رول',
}

LOCATION_RULES = [
    (["شناور","sticky","چسبنده","چسبان"],              "شناور"),
    (["سایدبار","sidebar","کناری","جانبی"],            "سایدبار"),
    (["میان مطلب","میانی","میان","وسط","بین مطلب"],    "میانی"),
    (["بالا","بالای","اول","ابتدا","هدر","header","سردبیر"], "بالا"),
    (["پایین","پایینی","آخر","انتها","فوتر","footer"],  "پایین"),
]

def classify(desc, pt):
    fa = PT_NAMES.get(pt, pt)
    tags = [lbl for kws, lbl in LOCATION_RULES if any(k in str(desc) for k in kws)]
    return f"{fa} | {' · '.join(tags)}" if tags else fa

# ─── Load ─────────────────────────────────────────────────────────────────────
df = pd.read_excel("daily_position_details.xlsx")
df["date"] = pd.to_datetime(df["date"])
df["month"] = df["date"].dt.to_period("M").astype(str)
df["pl"] = df.apply(lambda r: classify(r["description"], r["position_type"]), axis=1)

daily_pv = (df.groupby(["publisher_id","date"])["page_views"].max()
              .reset_index().rename(columns={"page_views":"pub_daily_pv"}))
df = df.merge(daily_pv, on=["publisher_id","date"])

month_fa_map = {m: month_to_fa(m) for m in df["month"].unique()}
df["mf"] = df["month"].map(month_fa_map)

# ─── Data structures ──────────────────────────────────────────────────────────
publishers = (df[["publisher_id","publisher_name"]].drop_duplicates()
              .sort_values("publisher_name")
              .rename(columns={"publisher_id":"id","publisher_name":"name"})
              .to_dict("records"))

pub_avg_pv = {str(k): int(round(v))
              for k,v in daily_pv.groupby("publisher_id")["pub_daily_pv"].mean().items()}

pmp = (daily_pv
       .assign(month=lambda x: pd.to_datetime(x["date"]).dt.to_period("M").astype(str))
       .groupby(["publisher_id","month"])["pub_daily_pv"].sum().reset_index()
       .rename(columns={"pub_daily_pv":"pv","publisher_id":"pid"}))
pmp["pid"] = pmp["pid"].astype(str)
pmp["mf"]  = pmp["month"].map(month_fa_map)

# tab1: pid × month × pl → rev / fixed / billboard
tab1 = (df.groupby(["publisher_id","month","mf","pl"])
          .agg(rev=("total_adv_cost","sum"), fixed=("fixed_adv_cost","sum"),
               billboard=("billboard_adv_cost","sum"))
          .reset_index().rename(columns={"publisher_id":"pid"}))
tab1["pid"] = tab1["pid"].astype(str)

# tab2: pid × month × position → rev / fixed / billboard
tab2 = (df.groupby(["publisher_id","month","mf","position_id","description","pl"])
          .agg(rev=("total_adv_cost","sum"), fixed=("fixed_adv_cost","sum"),
               billboard=("billboard_adv_cost","sum"))
          .reset_index()
          .rename(columns={"publisher_id":"pid","position_id":"pos_id","description":"desc"}))
tab2["pid"]    = tab2["pid"].astype(str)
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

.topbar{background:#16213e;color:#fff;padding:12px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.topbar h1{font-size:1.05rem;flex:1;white-space:nowrap}
.topbar .ctrl{display:flex;flex-direction:column;gap:3px}
.topbar label{font-size:0.73rem;color:#aab}
.topbar select,.topbar input[type=range]{padding:5px 9px;border-radius:6px;border:none;font-family:Tahoma,sans-serif;font-size:0.85rem;background:#fff;min-width:200px;cursor:pointer}
.topbar .rrow{display:flex;align-items:center;gap:8px}
.topbar .rv{font-size:0.85rem;min-width:28px}

.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:16px 24px 0}
.kpi{background:#fff;border-radius:10px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
.kpi .lbl{font-size:0.72rem;color:#888;margin-bottom:3px}
.kpi .val{font-size:1.35rem;font-weight:bold;color:#16213e}

.tabs-bar{display:flex;padding:16px 24px 0;gap:4px}
.tab-btn{padding:9px 24px;background:#d8dce8;border:none;cursor:pointer;font-family:Tahoma,sans-serif;font-size:0.87rem;border-radius:8px 8px 0 0;color:#555;transition:background .15s}
.tab-btn.active{background:#fff;color:#16213e;font-weight:bold}

.tab-panel{display:none;background:#fff;margin:0 24px 24px;border-radius:0 0 10px 10px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);overflow-y:auto;max-height:calc(100vh - 195px)}
.tab-panel.active{display:block}

.sec{font-size:0.93rem;font-weight:bold;color:#16213e;border-right:3px solid #4285F4;padding-right:8px;margin:22px 0 12px}
.sec:first-child{margin-top:0}

.frow{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.frow label{font-size:0.8rem;color:#666;white-space:nowrap}
.frow select{padding:5px 9px;border-radius:6px;border:1px solid #dde;font-family:Tahoma,sans-serif;font-size:0.82rem;cursor:pointer}

.chart2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:4px}

.tbl-wrap{overflow-x:auto;margin-top:4px}
table{width:100%;border-collapse:collapse;font-size:0.81rem}
thead th{background:#f0f3fa;padding:8px 10px;text-align:center;font-weight:bold;cursor:pointer;user-select:none;white-space:nowrap}
thead th:hover{background:#e2e7f5}
tbody td{padding:7px 10px;border-bottom:1px solid #f0f0f0;text-align:center}
tbody tr:hover{background:#f8faff}
.total-row td{background:#eef3ff;font-weight:bold;border-top:2px solid #4285F4}

/* pricing */
.sim-bar{background:#f4f7ff;border-radius:8px;padding:10px 14px;font-size:0.83rem;margin-bottom:16px;line-height:1.8}
.sim-bar .spubs{color:#555;font-size:0.78rem}

.bench-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px;margin-top:4px}
.bench-card{border:1px solid #e0e4f0;border-radius:8px;overflow:hidden;font-size:0.8rem}
.bench-hdr{background:#2c3e6b;color:#fff;padding:8px 12px;font-size:0.82rem;font-weight:bold}
.bench-body{padding:10px 12px}
.bench-scen{display:flex;gap:6px;margin-top:8px}
.bs{flex:1;text-align:center;border-radius:6px;padding:6px 4px;font-size:0.76rem}
.bs.bad {background:#fde8e8;color:#a93226}
.bs.real{background:#fff8e1;color:#a04000}
.bs.good{background:#e8f5e9;color:#1e7f3e}
.bs .bv{font-size:1.1rem;font-weight:bold;margin-top:2px}

.nodata{color:#999;padding:20px;text-align:center;font-size:0.85rem}

@media(max-width:700px){
  .kpis{grid-template-columns:1fr 1fr}
  .chart2{grid-template-columns:1fr}
}
</style>
</head>
<body>

<div class="topbar">
  <h1>📊 Publisher Pricing Dashboard</h1>
  <div class="ctrl">
    <label>پابلیشر</label>
    <select id="pubSel" onchange="boot()"></select>
  </div>
  <div class="ctrl">
    <label>بازه شباهت (log scale)</label>
    <div class="rrow">
      <input type="range" id="logW" min="0.3" max="1.2" step="0.1" value="0.6"
             oninput="document.getElementById('lwv').textContent=this.value;renderTab2()">
      <span class="rv" id="lwv">0.6</span>
    </div>
  </div>
</div>

<div class="kpis">
  <div class="kpi"><div class="lbl">میانگین درآمد ماهانه</div><div class="val" id="k1">—</div></div>
  <div class="kpi"><div class="lbl">میانگین PV روزانه</div><div class="val" id="k2">—</div></div>
  <div class="kpi"><div class="lbl">پوزیشن‌های فعال</div><div class="val" id="k3">—</div></div>
  <div class="kpi"><div class="lbl">RPM میانگین</div><div class="val" id="k4">—</div></div>
</div>

<div class="tabs-bar">
  <button class="tab-btn active" onclick="showTab('t1',this)">📈 عملکرد ناشر</button>
  <button class="tab-btn" onclick="showTab('t2',this)">💰 قیمت‌گذاری</button>
</div>

<!-- Tab 1 -->
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
  <div id="cPosRpm" style="min-height:370px;margin-top:16px"></div>
</div>

<!-- Tab 2 -->
<div id="t2" class="tab-panel">
  <div class="sec">ناشران مشابه</div>
  <div id="simBar" class="sim-bar"></div>

  <div class="sec">جدول قیمت‌گذاری</div>
  <div class="tbl-wrap" id="pricingTbl"></div>

  <div class="sec">منابع بنچمارک</div>
  <div id="benchCards" class="bench-grid"></div>
</div>

<script>
const RAW=""" + data_json + r""";

// helpers
const fmtN=(n,s='')=>{if(n==null||isNaN(n))return'—';if(Math.abs(n)>=1e9)return(n/1e9).toFixed(1)+'B'+s;if(Math.abs(n)>=1e6)return(n/1e6).toFixed(1)+'M'+s;if(Math.abs(n)>=1e3)return(n/1e3).toFixed(0)+'K'+s;return n.toFixed(0)+s;};
const fmtC=n=>n==null||isNaN(n)?'—':Math.round(n).toLocaleString();
const R=v=>v==null||isNaN(v)?'—':String(Math.round(v));

function quantile(arr,q){const s=[...arr].sort((a,b)=>a-b),pos=(s.length-1)*q,lo=Math.floor(pos),hi=Math.ceil(pos);return s[lo]+(s[hi]-s[lo])*(pos-lo);}
const p25=a=>a.length?quantile(a,.25):null;
const med=a=>a.length?quantile(a,.5):null;
const p75=a=>a.length?quantile(a,.75):null;

// pub_monthly_pv lookup
const pmpLookup={};
const monthFa={};
for(const r of RAW.pub_monthly_pv){
  if(!pmpLookup[r.pid])pmpLookup[r.pid]={};
  pmpLookup[r.pid][r.month]=r.pv;
  monthFa[r.month]=r.mf;
}

let selPid=null;

// init publisher selector
const pubSel=document.getElementById('pubSel');
RAW.publishers.forEach(p=>{const o=document.createElement('option');o.value=String(p.id);o.textContent=p.name;pubSel.appendChild(o);});
selPid=String(RAW.publishers[0].id);pubSel.value=selPid;

function boot(){
  selPid=pubSel.value;
  updateKpis();populateFilters();renderOverview();renderPositions();renderTab2();
}

// KPIs
function updateKpis(){
  const rows=RAW.tab1.filter(r=>r.pid===selPid);
  const pv=pmpLookup[selPid]||{};
  const months=[...new Set(rows.map(r=>r.month))].sort();
  const totalRev=rows.reduce((s,r)=>s+r.rev,0);
  const avgMonRev=months.length?totalRev/months.length:0;
  const pvArr=Object.values(pv);
  const totalPv=pvArr.reduce((a,b)=>a+b,0);
  const avgDailyPv=pvArr.length?totalPv/pvArr.length/30:0;
  const rpm=totalPv?totalRev/totalPv:0;
  const nPos=new Set(RAW.tab2_monthly.filter(r=>r.pid===selPid).map(r=>r.pos_id)).size;
  document.getElementById('k1').textContent=fmtN(avgMonRev,' ت');
  document.getElementById('k2').textContent=fmtN(avgDailyPv);
  document.getElementById('k3').textContent=nPos;
  document.getElementById('k4').textContent=R(rpm);
}

// populate filters (position_label)
function populateFilters(){
  const pls=[...new Set(RAW.tab2_monthly.filter(r=>r.pid===selPid).map(r=>r.pl))].sort();
  ['t1f','t2f'].forEach(id=>{
    const el=document.getElementById(id);
    el.innerHTML='<option value="">همه</option>';
    pls.forEach(pl=>{const o=document.createElement('option');o.value=pl;o.textContent=pl;el.appendChild(o);});
  });
}

// ── Tab 1: Overview charts ────────────────────────────────────────────────────
function renderOverview(){
  const filt=document.getElementById('t1f').value;
  const pv=pmpLookup[selPid]||{};
  let rows=RAW.tab1.filter(r=>r.pid===selPid);
  if(filt)rows=rows.filter(r=>r.pl===filt);

  const bm={};
  rows.forEach(r=>{
    if(!bm[r.month])bm[r.month]={rev:0,fixed:0,bb:0,mf:r.mf};
    bm[r.month].rev+=r.rev;bm[r.month].fixed+=r.fixed;bm[r.month].bb+=r.billboard;
  });
  const ms=Object.keys(bm).sort();
  const mf=ms.map(m=>bm[m].mf);
  const tot=ms.map(m=>bm[m].rev);
  const fix=ms.map(m=>bm[m].fixed);
  const bb=ms.map(m=>bm[m].bb);
  const reg=ms.map((m,i)=>tot[i]-fix[i]-bb[i]);
  const rpm=ms.map(m=>pv[m]?Math.round(bm[m].rev/pv[m]):null);

  // Stacked bar: regular + fixed + billboard = total
  Plotly.react('cRev',[
    {type:'bar',x:mf,y:reg,name:'درآمد معمولی',marker:{color:'#4285F4'},hovertemplate:'%{y:,.0f}<extra>معمولی</extra>'},
    {type:'bar',x:mf,y:fix,name:'فیکس',marker:{color:'#34A853'},hovertemplate:'%{y:,.0f}<extra>فیکس</extra>'},
    {type:'bar',x:mf,y:bb, name:'بیلبورد',marker:{color:'#FBBC04'},hovertemplate:'%{y:,.0f}<extra>بیلبورد</extra>'},
  ],{
    title:'درآمد ماهانه (تومان)',barmode:'stack',height:320,
    xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'تومان'},
    legend:{orientation:'h',y:1.18},
    margin:{t:50,b:70,l:60,r:10},
  },{responsive:true});

  Plotly.react('cRpm',[
    {type:'scatter',mode:'lines+markers',x:mf,y:rpm,
     line:{color:'#EA4335',width:2},marker:{size:7}},
  ],{
    title:'RPM ماهانه (تومان/پیج‌ویو)',height:320,
    xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'RPM'},
    margin:{t:50,b:70,l:60,r:10},
  },{responsive:true});
}

// ── Tab 1: Positions table + chart ────────────────────────────────────────────
function renderPositions(){
  const filt=document.getElementById('t2f').value;
  const pv=pmpLookup[selPid]||{};
  const totalPv=Object.values(pv).reduce((a,b)=>a+b,0);

  let rows=RAW.tab2_monthly.filter(r=>r.pid===selPid);
  if(filt)rows=rows.filter(r=>r.pl===filt);

  const pm={};
  rows.forEach(r=>{
    if(!pm[r.pos_id])pm[r.pos_id]={desc:r.desc,pl:r.pl,rev:0,fixed:0,bb:0,months:new Set()};
    pm[r.pos_id].rev+=r.rev;pm[r.pos_id].fixed+=r.fixed;pm[r.pos_id].bb+=r.billboard;pm[r.pos_id].months.add(r.month);
  });

  const sumRows=Object.values(pm).map(p=>({
    desc:p.desc,pl:p.pl,
    avgRev:p.months.size?p.rev/p.months.size:0,
    rpm:totalPv?p.rev/totalPv:0,
    fPct:p.rev?p.fixed/p.rev*100:0,
    bbPct:p.rev?p.bb/p.rev*100:0,
    months:p.months.size,
  })).sort((a,b)=>b.rpm-a.rpm);

  // total row
  const totRev=sumRows.reduce((s,r)=>s+r.avgRev,0);
  const totRpm=sumRows.reduce((s,r)=>s+r.rpm,0);
  const totFixed=sumRows.reduce((s,r)=>s+r.avgRev*(r.fPct/100),0);
  const totBb=sumRows.reduce((s,r)=>s+r.avgRev*(r.bbPct/100),0);

  const wrap=document.getElementById('posTbl');
  wrap.innerHTML='';
  let sortCol='rpm',sortAsc=false;

  function buildTbl(){
    const sorted=[...sumRows].sort((a,b)=>{
      const va=a[sortCol],vb=b[sortCol];
      if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return -1;
      return sortAsc?(va>vb?1:-1):(va<vb?1:-1);
    });
    const cols=[
      {k:'desc',  l:'توضیحات',       f:v=>v.substring(0,40)},
      {k:'pl',    l:'دسته‌بندی',     f:v=>v},
      {k:'avgRev',l:'درآمد ماهانه',  f:fmtC},
      {k:'rpm',   l:'RPM',           f:R},
      {k:'fPct',  l:'فیکس %',        f:v=>v.toFixed(0)+'%'},
      {k:'bbPct', l:'بیلبورد %',     f:v=>v.toFixed(0)+'%'},
      {k:'months',l:'ماه‌های فعال',  f:v=>String(v)},
    ];
    let h=`<table><thead><tr>`;
    cols.forEach(c=>{h+=`<th onclick="sortPT('${c.k}')">${c.l}${sortCol===c.k?(sortAsc?'▲':'▼'):''}</th>`;});
    h+=`</tr></thead><tbody>`;
    sorted.forEach(r=>{h+=`<tr>${cols.map(c=>`<td>${c.f(r[c.k])}</td>`).join('')}</tr>`;});
    // total row
    h+=`<tr class="total-row">
      <td>جمع</td><td>—</td>
      <td>${fmtC(totRev)}</td>
      <td>${R(totRpm)}</td>
      <td>${totRev?((totFixed/totRev)*100).toFixed(0)+'%':'—'}</td>
      <td>${totRev?((totBb/totRev)*100).toFixed(0)+'%':'—'}</td>
      <td>—</td>
    </tr>`;
    h+=`</tbody></table>`;
    wrap.innerHTML=h;
  }
  window.sortPT=(col)=>{if(sortCol===col)sortAsc=!sortAsc;else{sortCol=col;sortAsc=false;}buildTbl();};
  buildTbl();

  // Top 10 trend chart
  const top10=Object.entries(pm).sort((a,b)=>b[1].rev-a[1].rev).slice(0,10).map(e=>e[0]);
  const traces=[];
  top10.forEach(posId=>{
    const p=pm[posId];
    const mr=rows.filter(r=>r.pos_id===posId).sort((a,b)=>a.month>b.month?1:-1);
    traces.push({
      type:'scatter',mode:'lines+markers',name:p.desc.substring(0,30),
      x:mr.map(r=>monthFa[r.month]||r.month),
      y:mr.map(r=>pv[r.month]?Math.round(r.rev/pv[r.month]):null),
      marker:{size:5},
    });
  });
  Plotly.react('cPosRpm',traces,{
    title:'ترند RPM ماهانه — ۱۰ پوزیشن برتر',height:370,
    xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'RPM'},
    legend:{orientation:'h',y:-0.4,x:0},
    margin:{t:40,b:120,l:60,r:10},
  },{responsive:true});
}

// ── Tab 2: Pricing ────────────────────────────────────────────────────────────
function getSimilarPids(){
  const lw=parseFloat(document.getElementById('logW').value);
  const tPv=RAW.pub_avg_pv[selPid];
  if(!tPv||tPv<=0)return[];
  const tLog=Math.log10(tPv);
  return Object.entries(RAW.pub_avg_pv)
    .filter(([pid,pv])=>pid!==selPid&&pv>0&&Math.abs(Math.log10(pv)-tLog)<=lw)
    .map(([pid])=>pid);
}

function renderTab2(){
  const simPids=getSimilarPids();
  const tPv=RAW.pub_avg_pv[selPid];

  // sim info
  const simNames=simPids.map(pid=>{const p=RAW.publishers.find(x=>String(x.id)===pid);return p?`${p.name} (${fmtN(RAW.pub_avg_pv[pid])})`:pid;});
  document.getElementById('simBar').innerHTML=
    `<strong>${simPids.length} ناشر مشابه</strong> — PV روزانه شما: <strong>${fmtN(tPv)}</strong><br>`+
    (simNames.length?`<span class="spubs">${simNames.join(' &nbsp;·&nbsp; ')}</span>`:'بازه شباهت را افزایش دهید.');

  if(!simPids.length){
    document.getElementById('pricingTbl').innerHTML='<div class="nodata">ناشر مشابه یافت نشد.</div>';
    document.getElementById('benchCards').innerHTML='';
    return;
  }

  // target publisher data
  const tPvByMonth=pmpLookup[selPid]||{};
  const totalTPv=Object.values(tPvByMonth).reduce((a,b)=>a+b,0);
  const nMon=Object.keys(tPvByMonth).length||1;
  const targetMonPv=totalTPv/nMon;

  // scenarios per pl from similar publishers
  const simRows=RAW.tab2_monthly.filter(r=>simPids.includes(r.pid));
  const plRpms={};   // pl → {pid → [{month,rpm,mf}]}
  const plAllRpms={}; // pl → [rpm,...] for P25/med/P75

  simRows.forEach(r=>{
    const mpv=pmpLookup[r.pid]&&pmpLookup[r.pid][r.month];
    if(!mpv)return;
    const rpm=r.rev/mpv;
    if(!plRpms[r.pl])plRpms[r.pl]={};
    if(!plRpms[r.pl][r.pid])plRpms[r.pl][r.pid]=[];
    plRpms[r.pl][r.pid].push({month:r.month,mf:monthFa[r.month]||r.month,rev:r.rev,rpm});
    if(!plAllRpms[r.pl])plAllRpms[r.pl]=[];
    plAllRpms[r.pl].push(rpm);
  });

  const scen={};
  Object.entries(plAllRpms).forEach(([pl,arr])=>{
    if(arr.length>=2) scen[pl]={bad:p25(arr),real:med(arr),good:p75(arr),n:arr.length};
  });

  // target positions
  const tPosMap={};
  RAW.tab2_monthly.filter(r=>r.pid===selPid).forEach(r=>{
    if(!tPosMap[r.pos_id])tPosMap[r.pos_id]={desc:r.desc,pl:r.pl,rev:0,months:new Set()};
    tPosMap[r.pos_id].rev+=r.rev;tPosMap[r.pos_id].months.add(r.month);
  });

  // Build pricing table rows
  const pRows=Object.values(tPosMap).map(p=>{
    const s=scen[p.pl];
    const curRpm=totalTPv?p.rev/totalTPv:0;
    const avgMon=p.months.size?p.rev/p.months.size:0;
    return {
      pl:p.pl,desc:p.desc,
      curRpm,avgMon,
      bad:s?.bad??null, real:s?.real??null, good:s?.good??null, n:s?.n??0,
      revBad: s?s.bad*targetMonPv:null,
      revReal:s?s.real*targetMonPv:null,
      revGood:s?s.good*targetMonPv:null,
    };
  }).sort((a,b)=>b.curRpm-a.curRpm);

  // totals (only rows with scenario data)
  const withScen=pRows.filter(r=>r.real!=null);
  const totCurRpm=pRows.reduce((s,r)=>s+r.curRpm,0);
  const totBad=withScen.reduce((s,r)=>s+r.bad,0);
  const totReal=withScen.reduce((s,r)=>s+r.real,0);
  const totGood=withScen.reduce((s,r)=>s+r.good,0);
  const totRevBad=withScen.reduce((s,r)=>s+r.revBad,0);
  const totRevReal=withScen.reduce((s,r)=>s+r.revReal,0);
  const totRevGood=withScen.reduce((s,r)=>s+r.revGood,0);

  // Pricing table
  const cols=[
    {k:'pl',    l:'دسته‌بندی'},
    {k:'desc',  l:'توضیحات',       f:v=>v.substring(0,38)},
    {k:'curRpm',l:'RPM فعلی',      f:R},
    {k:'bad',   l:'RPM بدبینانه',  f:R},
    {k:'real',  l:'RPM واقع‌بینانه',f:R},
    {k:'good',  l:'RPM خوش‌بینانه',f:R},
    {k:'revReal',l:'درآمد واقع‌بینانه',f:fmtC},
    {k:'n',     l:'نمونه‌ها',      f:v=>v?String(v):'—'},
  ];

  let sortPC='real',sortPA=false;
  const ptWrap=document.getElementById('pricingTbl');

  function buildPT(){
    const sorted=[...pRows].sort((a,b)=>{
      const va=a[sortPC],vb=b[sortPC];
      if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return -1;
      return sortPA?(va>vb?1:-1):(va<vb?1:-1);
    });
    let h=`<table><thead><tr>`;
    cols.forEach(c=>{h+=`<th onclick="sortPT2('${c.k}')">${c.l}${sortPC===c.k?(sortPA?'▲':'▼'):''}</th>`;});
    h+=`</tr></thead><tbody>`;
    sorted.forEach(r=>{h+=`<tr>${cols.map(c=>`<td>${c.f?c.f(r[c.k]):(r[c.k]??'—')}</td>`).join('')}</tr>`;});
    h+=`<tr class="total-row">
      <td>جمع</td><td>—</td>
      <td>${R(totCurRpm)}</td>
      <td>${R(totBad)}</td>
      <td>${R(totReal)}</td>
      <td>${R(totGood)}</td>
      <td>${fmtC(totRevReal)}</td>
      <td>—</td>
    </tr>`;
    h+=`</tbody></table>`;
    ptWrap.innerHTML=h;
  }
  window.sortPT2=(col)=>{if(sortPC===col)sortPA=!sortPA;else{sortPC=col;sortPA=false;}buildPT();};
  buildPT();

  // Benchmark cards (compact)
  const usedPls=[...new Set(pRows.map(r=>r.pl))];
  let benchHtml='';
  usedPls.forEach(pl=>{
    const s=scen[pl];if(!s)return;
    const pubData=plRpms[pl]||{};
    const pubRows=Object.entries(pubData).map(([pid,months])=>{
      const pub=RAW.publishers.find(x=>String(x.id)===pid);
      const rpms=months.map(m=>m.rpm);
      const avg=rpms.reduce((a,b)=>a+b)/rpms.length;
      return {name:pub?pub.name:pid,avg:Math.round(avg),n:months.length};
    }).sort((a,b)=>b.avg-a.avg);

    const trs=pubRows.map(r=>`<tr><td>${r.name}</td><td>${r.avg}</td><td>${r.n}</td></tr>`).join('');
    benchHtml+=`
    <div class="bench-card">
      <div class="bench-hdr">${pl}</div>
      <div class="bench-body">
        <table style="font-size:0.76rem">
          <thead><tr><th>ناشر</th><th>RPM میانگین</th><th>ماه‌ها</th></tr></thead>
          <tbody>${trs}</tbody>
        </table>
        <div class="bench-scen">
          <div class="bs bad">بدبینانه<div class="bv">${R(s.bad)}</div></div>
          <div class="bs real">واقع‌بینانه<div class="bv">${R(s.real)}</div></div>
          <div class="bs good">خوش‌بینانه<div class="bv">${R(s.good)}</div></div>
        </div>
      </div>
    </div>`;
  });
  document.getElementById('benchCards').innerHTML=benchHtml||'<div class="nodata">داده بنچمارک کافی نیست.</div>';
}

// tab switch
function showTab(id,btn){
  document.querySelectorAll('.tab-panel').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
  document.getElementById(id).classList.add('active');btn.classList.add('active');
}

boot();
</script>
</body>
</html>
"""

with open("dashboard.html","w",encoding="utf-8") as f:
    f.write(HTML)
print("✅ dashboard.html written.")
