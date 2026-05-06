"""
Generates a standalone dashboard.html — no server needed.
Usage: python3 generate_html.py
"""
import json
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

# publisher primary category
pub_cats = {}
for pid, grp in df.groupby("publisher_id"):
    cats = grp["category"].dropna()
    pub_cats[str(pid)] = str(cats.mode()[0]) if len(cats) > 0 else ""

# available months sorted (for date range filter)
months_sorted = sorted(month_fa_map.items(), key=lambda x: x[0])
months_list = [{"key": k, "fa": v} for k, v in months_sorted]

# pub_monthly_pv
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
    "publishers":     publishers,
    "pub_avg_pv":     pub_avg_pv,
    "pub_cats":       pub_cats,
    "months_list":    months_list,
    "pub_monthly_pv": pmp.to_dict("records"),
    "tab1":           tab1.to_dict("records"),
    "tab2_monthly":   tab2.to_dict("records"),
}
data_json = json.dumps(DATA, ensure_ascii=False)
print(f"publishers:{len(publishers)}  tab1:{len(tab1)}  tab2:{len(tab2)}  months:{len(months_list)}")

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

/* topbar */
.topbar{background:#16213e;color:#fff;padding:12px 24px;display:flex;align-items:flex-end;gap:18px;flex-wrap:wrap}
.topbar h1{font-size:1rem;color:#fff;align-self:center;flex:none;white-space:nowrap}
.ctrl{display:flex;flex-direction:column;gap:4px}
.ctrl label{font-size:0.7rem;color:#9ab;letter-spacing:.3px}
.ctrl select{padding:6px 10px;border-radius:6px;border:none;font-family:Tahoma,sans-serif;font-size:0.83rem;background:#fff;cursor:pointer}
.ctrl input[type=range]{width:120px;accent-color:#4285F4}
.rrow{display:flex;align-items:center;gap:6px}
.rv{font-size:0.83rem;color:#dde;min-width:24px}

/* search */
.search-wrap{position:relative}
.search-wrap input{
  padding:6px 32px 6px 10px;border-radius:6px;border:none;
  font-family:Tahoma,sans-serif;font-size:0.83rem;
  width:220px;background:#fff;color:#222;
  outline:none
}
.search-wrap .si{position:absolute;left:8px;top:50%;transform:translateY(-50%);font-size:0.9rem;pointer-events:none}
.sugg{
  position:absolute;top:calc(100% + 4px);right:0;
  background:#fff;border:1px solid #dde;border-radius:8px;
  box-shadow:0 4px 16px rgba(0,0,0,.15);
  min-width:260px;max-height:220px;overflow-y:auto;
  z-index:100;display:none
}
.sugg.open{display:block}
.sugg-item{
  padding:8px 12px;cursor:pointer;font-size:0.82rem;
  border-bottom:1px solid #f0f2f8;color:#222
}
.sugg-item:last-child{border-bottom:none}
.sugg-item:hover{background:#eef3ff}
.sugg-item .sid{font-size:0.7rem;color:#888;margin-right:6px}
.sugg-item.active-pub{background:#eef3ff;font-weight:bold}
.no-result{padding:12px;color:#888;font-size:0.8rem;text-align:center}

/* tabs */
.tabs-bar{display:flex;padding:16px 24px 0;gap:4px}
.tab-btn{padding:9px 24px;background:#d8dce8;border:none;cursor:pointer;font-family:Tahoma,sans-serif;font-size:0.87rem;border-radius:8px 8px 0 0;color:#555;transition:background .15s}
.tab-btn.active{background:#fff;color:#16213e;font-weight:bold}

/* panels */
.tab-panel{display:none;background:#fff;margin:0 24px 24px;border-radius:0 0 10px 10px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.08);overflow-y:auto;max-height:calc(100vh - 140px)}
.tab-panel.active{display:block}

/* section title */
.sec{font-size:0.93rem;font-weight:bold;color:#16213e;border-right:3px solid #4285F4;padding-right:8px;margin:22px 0 12px}
.sec:first-child{margin-top:0}

/* filter row */
.frow{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.frow label{font-size:0.8rem;color:#666;white-space:nowrap}
.frow select{padding:5px 9px;border-radius:6px;border:1px solid #dde;font-family:Tahoma,sans-serif;font-size:0.82rem;cursor:pointer}

/* chart grid */
.chart2{display:grid;grid-template-columns:1fr 1fr;gap:14px}

/* tables */
.tbl-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:0.81rem}
thead th{background:#f0f3fa;padding:8px 10px;text-align:center;font-weight:bold;cursor:pointer;user-select:none;white-space:nowrap}
thead th:hover{background:#e2e7f5}
tbody td{padding:7px 10px;border-bottom:1px solid #f0f0f0;text-align:center}
tbody tr:hover{background:#f8faff}
.total-row td{background:#eef3ff;font-weight:bold;border-top:2px solid #4285F4}

/* sim bar */
.sim-bar{background:#f4f7ff;border-radius:8px;padding:10px 14px;font-size:0.83rem;margin-bottom:16px;line-height:1.8}
.sim-bar .spubs{color:#555;font-size:0.78rem}
.cat-badge{display:inline-block;background:#4285F4;color:#fff;font-size:0.68rem;border-radius:4px;padding:1px 5px;margin-right:4px;vertical-align:middle}
.cat-badge.match{background:#34A853}

/* bench grid */
.bench-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:4px}
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

@media(max-width:700px){.chart2{grid-template-columns:1fr}}
</style>
</head>
<body>

<!-- topbar -->
<div class="topbar">
  <h1>📊 Publisher Pricing</h1>

  <div class="ctrl">
    <label>جستجوی ناشر</label>
    <div class="search-wrap">
      <input id="pubSearch" type="text" placeholder="نام یا آیدی ناشر..." autocomplete="off"
             oninput="onSearch(this.value)" onfocus="openSugg()" onblur="closeSugg()">
      <span class="si">🔍</span>
      <div id="pubSugg" class="sugg"></div>
    </div>
  </div>

  <div class="ctrl">
    <label>از ماه</label>
    <select id="dateFrom" onchange="applyDateFilter()"></select>
  </div>

  <div class="ctrl">
    <label>تا ماه</label>
    <select id="dateTo" onchange="applyDateFilter()"></select>
  </div>

  <div class="ctrl">
    <label>بازه شباهت (log)</label>
    <div class="rrow">
      <input type="range" id="logW" min="0.3" max="1.2" step="0.1" value="0.6"
             oninput="document.getElementById('lwv').textContent=this.value;renderTab2()">
      <span class="rv" id="lwv">0.6</span>
    </div>
  </div>
</div>

<!-- tabs -->
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
</div>

<!-- Tab 2 -->
<div id="t2" class="tab-panel">
  <div class="sec">ناشران مشابه</div>
  <div id="simBar" class="sim-bar">ناشر انتخاب نشده</div>

  <div class="sec">جدول قیمت‌گذاری</div>
  <div class="tbl-wrap" id="pricingTbl"></div>

  <div class="sec">منابع بنچمارک</div>
  <div id="benchCards" class="bench-grid"></div>
</div>

<script>
const RAW=""" + data_json + r""";

// ─── helpers ──────────────────────────────────────────────────────────────────
const fmtN=(n,s='')=>{if(n==null||isNaN(n))return'—';if(Math.abs(n)>=1e9)return(n/1e9).toFixed(1)+'B'+s;if(Math.abs(n)>=1e6)return(n/1e6).toFixed(1)+'M'+s;if(Math.abs(n)>=1e3)return(n/1e3).toFixed(0)+'K'+s;return n.toFixed(0)+s;};
const fmtC=n=>n==null||isNaN(n)?'—':Math.round(n).toLocaleString();
const R=v=>v==null||isNaN(v)?'—':String(Math.round(v));

function quantile(arr,q){const s=[...arr].sort((a,b)=>a-b),pos=(s.length-1)*q,lo=Math.floor(pos),hi=Math.ceil(pos);return s[lo]+(s[hi]-s[lo])*(pos-lo);}
const p25=a=>a.length?quantile(a,.25):null;
const med=a=>a.length?quantile(a,.5):null;
const p75=a=>a.length?quantile(a,.75):null;

// lookup tables
const pmpLookup={};
const monthFa={};
for(const r of RAW.pub_monthly_pv){
  if(!pmpLookup[r.pid])pmpLookup[r.pid]={};
  pmpLookup[r.pid][r.month]=r.pv;
  monthFa[r.month]=r.mf;
}

// ─── state ────────────────────────────────────────────────────────────────────
let selPid = String(RAW.publishers[0].id);
let fromMonth = RAW.months_list[0].key;
let toMonth   = RAW.months_list[RAW.months_list.length-1].key;

// ─── date range selectors ─────────────────────────────────────────────────────
(function initDateSelectors(){
  const selF=document.getElementById('dateFrom');
  const selT=document.getElementById('dateTo');
  RAW.months_list.forEach(m=>{
    const oF=document.createElement('option');oF.value=m.key;oF.textContent=m.fa;selF.appendChild(oF);
    const oT=document.createElement('option');oT.value=m.key;oT.textContent=m.fa;selT.appendChild(oT);
  });
  selF.value=fromMonth;
  selT.value=toMonth;
})();

function applyDateFilter(){
  fromMonth=document.getElementById('dateFrom').value;
  toMonth  =document.getElementById('dateTo').value;
  if(fromMonth>toMonth){
    // swap
    [fromMonth,toMonth]=[toMonth,fromMonth];
    document.getElementById('dateFrom').value=fromMonth;
    document.getElementById('dateTo').value  =toMonth;
  }
  renderAll();
}

function inRange(month){ return month>=fromMonth && month<=toMonth; }

// ─── publisher search ─────────────────────────────────────────────────────────
let _searchQ='';
const suggEl=document.getElementById('pubSugg');
const searchEl=document.getElementById('pubSearch');

// init: show current selected publisher name
searchEl.value=RAW.publishers[0].name;

function onSearch(q){
  _searchQ=q.trim().toLowerCase();
  renderSugg();
}
function openSugg(){ renderSugg(); suggEl.classList.add('open'); }
function closeSugg(){ setTimeout(()=>suggEl.classList.remove('open'),180); }

function renderSugg(){
  const q=_searchQ;
  const matches = !q
    ? RAW.publishers.slice(0,12)
    : RAW.publishers.filter(p=>
        p.name.toLowerCase().includes(q)||String(p.id).includes(q)
      ).slice(0,12);

  if(!matches.length){
    suggEl.innerHTML='<div class="no-result">ناشری یافت نشد</div>';
    suggEl.classList.add('open');
    return;
  }
  suggEl.innerHTML=matches.map(p=>`
    <div class="sugg-item${String(p.id)===selPid?' active-pub':''}"
         onmousedown="selectPub('${p.id}','${p.name.replace(/'/g,"\\'")}')">
      ${p.name}<span class="sid">#${p.id}</span>
    </div>`).join('');
  suggEl.classList.add('open');
}

function selectPub(id,name){
  selPid=String(id);
  searchEl.value=name;
  _searchQ='';
  suggEl.classList.remove('open');
  populateFilters();
  renderAll();
}

// ─── filter selectors ─────────────────────────────────────────────────────────
function populateFilters(){
  const pls=[...new Set(
    RAW.tab2_monthly.filter(r=>r.pid===selPid&&inRange(r.month)).map(r=>r.pl)
  )].sort();
  ['t1f','t2f'].forEach(id=>{
    const el=document.getElementById(id);
    el.innerHTML='<option value="">همه</option>';
    pls.forEach(pl=>{const o=document.createElement('option');o.value=pl;o.textContent=pl;el.appendChild(o);});
  });
}

function renderAll(){ populateFilters(); renderOverview(); renderPositions(); renderTab2(); }

// ─── Tab 1: Overview ──────────────────────────────────────────────────────────
function renderOverview(){
  const filt=document.getElementById('t1f').value;
  const pv=pmpLookup[selPid]||{};
  let rows=RAW.tab1.filter(r=>r.pid===selPid&&inRange(r.month));
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

  Plotly.react('cRev',[
    {type:'bar',x:mf,y:reg,name:'درآمد معمولی',marker:{color:'#4285F4'}},
    {type:'bar',x:mf,y:fix,name:'فیکس',marker:{color:'#34A853'}},
    {type:'bar',x:mf,y:bb, name:'بیلبورد',marker:{color:'#FBBC04'}},
  ],{title:'درآمد ماهانه',barmode:'stack',height:320,
     xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'تومان'},
     legend:{orientation:'h',y:1.18},margin:{t:50,b:70,l:60,r:10}},{responsive:true});

  Plotly.react('cRpm',[
    {type:'scatter',mode:'lines+markers',x:mf,y:rpm,
     line:{color:'#EA4335',width:2},marker:{size:7}},
  ],{title:'RPM ماهانه (تومان/پیج‌ویو)',height:320,
     xaxis:{title:'ماه',tickangle:-30},yaxis:{title:'RPM'},
     margin:{t:50,b:70,l:60,r:10}},{responsive:true});
}

// ─── Tab 1: Positions table ───────────────────────────────────────────────────
function renderPositions(){
  const filt=document.getElementById('t2f').value;
  const pv=pmpLookup[selPid]||{};
  const filtPv={};
  Object.entries(pv).forEach(([m,v])=>{ if(inRange(m))filtPv[m]=v; });
  const totalPv=Object.values(filtPv).reduce((a,b)=>a+b,0);

  let rows=RAW.tab2_monthly.filter(r=>r.pid===selPid&&inRange(r.month));
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

  const totRev=sumRows.reduce((s,r)=>s+r.avgRev,0);
  const totRpm=sumRows.reduce((s,r)=>s+r.rpm,0);
  const totF=sumRows.reduce((s,r)=>s+r.avgRev*(r.fPct/100),0);
  const totB=sumRows.reduce((s,r)=>s+r.avgRev*(r.bbPct/100),0);

  const wrap=document.getElementById('posTbl');
  wrap.innerHTML='';
  let sc='rpm',sa=false;

  function buildTbl(){
    const sorted=[...sumRows].sort((a,b)=>{
      const va=a[sc],vb=b[sc];
      if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return -1;
      return sa?(va>vb?1:-1):(va<vb?1:-1);
    });
    const cols=[
      {k:'desc',  l:'توضیحات',      f:v=>v.substring(0,40)},
      {k:'pl',    l:'دسته‌بندی',    f:v=>v},
      {k:'avgRev',l:'درآمد ماهانه', f:fmtC},
      {k:'rpm',   l:'RPM',          f:R},
      {k:'fPct',  l:'فیکس %',       f:v=>v.toFixed(0)+'%'},
      {k:'bbPct', l:'بیلبورد %',    f:v=>v.toFixed(0)+'%'},
      {k:'months',l:'ماه‌های فعال', f:String},
    ];
    let h=`<table><thead><tr>`;
    cols.forEach(c=>{h+=`<th onclick="sortPosT('${c.k}')">${c.l}${sc===c.k?(sa?'▲':'▼'):''}</th>`;});
    h+=`</tr></thead><tbody>`;
    sorted.forEach(r=>{h+=`<tr>${cols.map(c=>`<td>${c.f(r[c.k])}</td>`).join('')}</tr>`;});
    h+=`<tr class="total-row"><td>جمع</td><td>—</td><td>${fmtC(totRev)}</td><td>${R(totRpm)}</td>`+
       `<td>${totRev?((totF/totRev)*100).toFixed(0)+'%':'—'}</td>`+
       `<td>${totRev?((totB/totRev)*100).toFixed(0)+'%':'—'}</td><td>—</td></tr>`;
    h+=`</tbody></table>`;
    wrap.innerHTML=h;
  }
  window.sortPosT=(col)=>{if(sc===col)sa=!sa;else{sc=col;sa=false;}buildTbl();};
  buildTbl();
}

// ─── Tab 2: Pricing ───────────────────────────────────────────────────────────
function getSimilarPids(){
  const lw=parseFloat(document.getElementById('logW').value);
  const tPv=RAW.pub_avg_pv[selPid];
  const tCat=RAW.pub_cats[selPid]||'';
  if(!tPv||tPv<=0)return[];
  const tLog=Math.log10(tPv);
  return Object.entries(RAW.pub_avg_pv)
    .filter(([pid,pv])=>pid!==selPid&&pv>0&&Math.abs(Math.log10(pv)-tLog)<=lw)
    .map(([pid,pv])=>({
      pid,
      dist:Math.abs(Math.log10(pv)-tLog),
      sameCat: tCat && RAW.pub_cats[pid]===tCat,
    }))
    // same category + closer pv first
    .sort((a,b)=>{
      if(a.sameCat&&!b.sameCat)return -1;
      if(!a.sameCat&&b.sameCat)return 1;
      return a.dist-b.dist;
    })
    .map(x=>x.pid);
}

function renderTab2(){
  const simPids=getSimilarPids();
  const tPv=RAW.pub_avg_pv[selPid];
  const tCat=RAW.pub_cats[selPid]||'';

  // sim bar
  const simNames=simPids.map(pid=>{
    const p=RAW.publishers.find(x=>String(x.id)===pid);
    const cat=RAW.pub_cats[pid]||'';
    const match=tCat&&cat===tCat;
    return p?`<span>${p.name}<span class="cat-badge${match?' match':''}"> ${cat||'?'}</span></span>`:pid;
  });
  document.getElementById('simBar').innerHTML=
    `<strong>${simPids.length} ناشر مشابه</strong>`+
    (tCat?` — دسته شما: <span class="cat-badge match">${tCat}</span>`:'')+
    ` — PV روزانه: <strong>${fmtN(tPv)}</strong><br>`+
    (simNames.length?`<span class="spubs">${simNames.join(' &nbsp;·&nbsp; ')}</span>`:
    '<span style="color:#c0392b">ناشر مشابهی یافت نشد — بازه شباهت را افزایش دهید.</span>');

  if(!simPids.length){
    document.getElementById('pricingTbl').innerHTML='<div class="nodata">ناشر مشابه یافت نشد.</div>';
    document.getElementById('benchCards').innerHTML='';
    return;
  }

  // filtered target pv
  const tPvByMonth=pmpLookup[selPid]||{};
  const filtTPv=Object.entries(tPvByMonth).filter(([m])=>inRange(m));
  const totalTPv=filtTPv.reduce((s,[,v])=>s+v,0);
  const nMon=filtTPv.length||1;
  const targetMonPv=totalTPv/nMon;

  // scenarios per pl from similar publishers (filtered by date range)
  const simRows=RAW.tab2_monthly.filter(r=>simPids.includes(r.pid)&&inRange(r.month));
  const plRpms={};
  const plAllRpms={};

  simRows.forEach(r=>{
    const mpv=pmpLookup[r.pid]&&pmpLookup[r.pid][r.month];
    if(!mpv)return;
    const rpm=r.rev/mpv;
    if(!plRpms[r.pl])plRpms[r.pl]={};
    if(!plRpms[r.pl][r.pid])plRpms[r.pl][r.pid]=[];
    plRpms[r.pl][r.pid].push({month:r.month,mf:monthFa[r.month]||r.month,rpm});
    if(!plAllRpms[r.pl])plAllRpms[r.pl]=[];
    plAllRpms[r.pl].push(rpm);
  });

  const scen={};
  Object.entries(plAllRpms).forEach(([pl,arr])=>{
    if(arr.length>=2)scen[pl]={bad:p25(arr),real:med(arr),good:p75(arr),n:arr.length};
  });

  // target positions
  const tPosMap={};
  RAW.tab2_monthly.filter(r=>r.pid===selPid&&inRange(r.month)).forEach(r=>{
    if(!tPosMap[r.pos_id])tPosMap[r.pos_id]={desc:r.desc,pl:r.pl,rev:0,months:new Set()};
    tPosMap[r.pos_id].rev+=r.rev;tPosMap[r.pos_id].months.add(r.month);
  });

  const pRows=Object.values(tPosMap).map(p=>{
    const s=scen[p.pl];
    const curRpm=totalTPv?p.rev/totalTPv:0;
    return {
      pl:p.pl,desc:p.desc,curRpm,
      avgMon:p.months.size?p.rev/p.months.size:0,
      bad:s?.bad??null,real:s?.real??null,good:s?.good??null,n:s?.n??0,
      revBad:s?s.bad*targetMonPv:null,
      revReal:s?s.real*targetMonPv:null,
      revGood:s?s.good*targetMonPv:null,
    };
  }).sort((a,b)=>b.curRpm-a.curRpm);

  const ws=pRows.filter(r=>r.real!=null);
  const totCurRpm=pRows.reduce((s,r)=>s+r.curRpm,0);
  const totBad=ws.reduce((s,r)=>s+r.bad,0);
  const totReal=ws.reduce((s,r)=>s+r.real,0);
  const totGood=ws.reduce((s,r)=>s+r.good,0);
  const totRevReal=ws.reduce((s,r)=>s+r.revReal,0);

  // Pricing table
  const cols=[
    {k:'pl',     l:'دسته‌بندی'},
    {k:'desc',   l:'توضیحات',         f:v=>v.substring(0,38)},
    {k:'curRpm', l:'RPM فعلی',        f:R},
    {k:'bad',    l:'RPM بدبینانه',    f:R},
    {k:'real',   l:'RPM واقع‌بینانه', f:R},
    {k:'good',   l:'RPM خوش‌بینانه',  f:R},
    {k:'revReal',l:'درآمد واقع‌بینانه',f:fmtC},
    {k:'n',      l:'نمونه‌ها',        f:v=>v?String(v):'—'},
  ];

  let sPC='real',sPA=false;
  const ptWrap=document.getElementById('pricingTbl');

  function buildPT(){
    const sorted=[...pRows].sort((a,b)=>{
      const va=a[sPC],vb=b[sPC];
      if(va==null&&vb==null)return 0;if(va==null)return 1;if(vb==null)return -1;
      return sPA?(va>vb?1:-1):(va<vb?1:-1);
    });
    let h=`<table><thead><tr>`;
    cols.forEach(c=>{h+=`<th onclick="sortPT2('${c.k}')">${c.l}${sPC===c.k?(sPA?'▲':'▼'):''}</th>`;});
    h+=`</tr></thead><tbody>`;
    sorted.forEach(r=>{h+=`<tr>${cols.map(c=>`<td>${c.f?c.f(r[c.k]):(r[c.k]??'—')}</td>`).join('')}</tr>`;});
    h+=`<tr class="total-row"><td>جمع</td><td>—</td>`+
       `<td>${R(totCurRpm)}</td><td>${R(totBad)}</td><td>${R(totReal)}</td><td>${R(totGood)}</td>`+
       `<td>${fmtC(totRevReal)}</td><td>—</td></tr>`;
    h+=`</tbody></table>`;
    ptWrap.innerHTML=h;
  }
  window.sortPT2=(col)=>{if(sPC===col)sPA=!sPA;else{sPC=col;sPA=false;}buildPT();};
  buildPT();

  // Benchmark cards
  const usedPls=[...new Set(pRows.map(r=>r.pl))];
  let benchHtml='';
  usedPls.forEach(pl=>{
    const s=scen[pl];if(!s)return;
    const pubData=plRpms[pl]||{};
    const pubRows=Object.entries(pubData).map(([pid,months])=>{
      const pub=RAW.publishers.find(x=>String(x.id)===pid);
      const cat=RAW.pub_cats[pid]||'';
      const match=tCat&&cat===tCat;
      const rpms=months.map(m=>m.rpm);
      return {name:pub?pub.name:pid,cat,match,avg:Math.round(rpms.reduce((a,b)=>a+b)/rpms.length),n:months.length};
    }).sort((a,b)=>b.avg-a.avg);

    const trs=pubRows.map(r=>`<tr>
      <td>${r.name}${r.cat?`<span class="cat-badge${r.match?' match':''}">${r.cat}</span>`:''}</td>
      <td>${r.avg}</td><td>${r.n}</td>
    </tr>`).join('');

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

// ─── tab switch ───────────────────────────────────────────────────────────────
function showTab(id,btn){
  document.querySelectorAll('.tab-panel').forEach(e=>e.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(e=>e.classList.remove('active'));
  document.getElementById(id).classList.add('active');btn.classList.add('active');
}

// ─── boot ─────────────────────────────────────────────────────────────────────
populateFilters();
renderOverview();
renderPositions();
renderTab2();
</script>
</body>
</html>
"""

with open("dashboard.html","w",encoding="utf-8") as f:
    f.write(HTML)
print("✅ dashboard.html written.")
