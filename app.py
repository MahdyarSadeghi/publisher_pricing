import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Publisher Pricing Dashboard",
    layout="wide",
    page_icon="📊",
)

st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.4rem; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)


# ─── Data Loading ─────────────────────────────────────────────────────────────

@st.cache_data
def load_data():
    df = pd.read_excel("daily_position_details.xlsx")
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


def classify_position(description: str, position_type: str) -> str:
    """
    Combine position_type with location keywords parsed from description.
    Examples:
      notification + شناور   → "notification | شناور"
      banner-article + میانی → "banner-article | میانی"
    """
    desc = str(description)

    location_rules = [
        (["شناور", "sticky", "چسبنده", "چسبان"], "شناور"),
        (["سایدبار", "sidebar", "کناری", "جانبی"], "سایدبار"),
        (["میان مطلب", "میانی", "میان", "وسط", "بین مطلب"], "میانی"),
        (["بالا", "بالای", "اول", "ابتدا", "هدر", "header", "سردبیر"], "بالا"),
        (["پایین", "پایینی", "آخر", "انتها", "فوتر", "footer"], "پایین"),
    ]

    tags = []
    for keywords, label in location_rules:
        if any(k in desc for k in keywords):
            tags.append(label)

    if tags:
        return f"{position_type} | {' · '.join(tags)}"
    return position_type


@st.cache_data
def process_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["position_label"] = df.apply(
        lambda r: classify_position(r["description"], r["position_type"]), axis=1
    )
    # Publisher daily PV is the same for every position on the same day
    daily_pub_pv = (
        df.groupby(["publisher_id", "date"])["page_views"]
        .max()
        .reset_index()
        .rename(columns={"page_views": "pub_daily_pv"})
    )
    df = df.merge(daily_pub_pv, on=["publisher_id", "date"])
    return df


def fmt_num(n, suffix="") -> str:
    if pd.isna(n):
        return "—"
    n = float(n)
    if abs(n) >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B{suffix}"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M{suffix}"
    if abs(n) >= 1_000:
        return f"{n/1_000:.0f}K{suffix}"
    return f"{n:.0f}{suffix}"


# ─── Load ─────────────────────────────────────────────────────────────────────

df_raw = load_data()
df = process_data(df_raw)

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ تنظیمات")

    pub_list = (
        df[["publisher_id", "publisher_name"]]
        .drop_duplicates()
        .sort_values("publisher_name")
    )
    pub_map = dict(zip(pub_list["publisher_name"], pub_list["publisher_id"]))

    sel_name = st.selectbox("پابلیشر", list(pub_map.keys()))
    sel_id = pub_map[sel_name]

    st.divider()

    date_min = df["date"].min().date()
    date_max = df["date"].max().date()
    date_range = st.date_input(
        "بازه زمانی",
        value=(date_min, date_max),
        min_value=date_min,
        max_value=date_max,
    )

    st.divider()

    log_window = st.slider(
        "بازه شباهت (log scale)",
        0.3, 1.2, 0.6, 0.1,
        help="0.6 ≈ پابلیشرهایی با pageview بین ۴× کمتر تا ۴× بیشتر",
    )

# ─── Date Filter ──────────────────────────────────────────────────────────────

if len(date_range) == 2:
    df_f = df[
        (df["date"] >= pd.Timestamp(date_range[0]))
        & (df["date"] <= pd.Timestamp(date_range[1]))
    ].copy()
else:
    df_f = df.copy()

pub_df = df_f[df_f["publisher_id"] == sel_id].copy()

if pub_df.empty:
    st.error("داده‌ای برای این پابلیشر در بازه انتخابی وجود ندارد.")
    st.stop()

# ─── Publisher-level daily / monthly aggregates ───────────────────────────────

daily_pub = (
    pub_df.groupby("date")
    .agg(daily_rev=("total_adv_cost", "sum"), daily_pv=("pub_daily_pv", "first"))
    .reset_index()
)
daily_pub["month"] = daily_pub["date"].dt.to_period("M").astype(str)

monthly_pub = (
    daily_pub.groupby("month")
    .agg(rev=("daily_rev", "sum"), pv=("daily_pv", "sum"))
    .reset_index()
    .sort_values("month")
)
monthly_pub["rpm"] = monthly_pub["rev"] / monthly_pub["pv"] * 1_000

n_months = monthly_pub.shape[0]
avg_monthly_rev = monthly_pub["rev"].mean()
avg_daily_pv = daily_pub["daily_pv"].mean()
n_positions = pub_df["position_id"].nunique()
overall_rpm = monthly_pub["rpm"].mean()

# ─── Header KPIs ──────────────────────────────────────────────────────────────

st.title(f"📰 {sel_name}")
st.caption(f"Publisher ID: {sel_id}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("میانگین درآمد ماهانه", fmt_num(avg_monthly_rev, " ت"))
c2.metric("میانگین PV روزانه", fmt_num(avg_daily_pv))
c3.metric("پوزیشن‌های فعال", n_positions)
c4.metric("RPM میانگین", f"{overall_rpm:.2f}")

st.divider()

# ─── Tabs ─────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["📈 نمای کلی", "🎯 پوزیشن‌ها", "💰 سناریوهای قیمت"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    pos_types_t1 = ["همه"] + sorted(pub_df["position_type"].unique().tolist())
    filt_t1 = st.selectbox("فیلتر نوع پوزیشن", pos_types_t1, key="t1_pt")

    fdf1 = pub_df if filt_t1 == "همه" else pub_df[pub_df["position_type"] == filt_t1]

    daily_filt1 = (
        fdf1.groupby("date")
        .agg(
            rev=("total_adv_cost", "sum"),
            fixed=("fixed_adv_cost", "sum"),
            billboard=("billboard_adv_cost", "sum"),
            pv=("pub_daily_pv", "first"),
        )
        .reset_index()
    )
    daily_filt1["month"] = daily_filt1["date"].dt.to_period("M").astype(str)

    mf1 = (
        daily_filt1.groupby("month")
        .agg(
            rev=("rev", "sum"),
            fixed=("fixed", "sum"),
            billboard=("billboard", "sum"),
            pv=("pv", "sum"),
        )
        .reset_index()
        .sort_values("month")
    )
    mf1["rpm"] = mf1["rev"] / mf1["pv"] * 1_000

    col_l, col_r = st.columns(2)

    with col_l:
        fig_rev = go.Figure()
        fig_rev.add_bar(
            x=mf1["month"], y=mf1["rev"],
            name="کل درآمد", marker_color="#4285F4", opacity=0.85,
        )
        fig_rev.add_bar(
            x=mf1["month"], y=mf1["fixed"],
            name="فیکس", marker_color="#34A853", opacity=0.8,
        )
        fig_rev.add_bar(
            x=mf1["month"], y=mf1["billboard"],
            name="بیلبورد", marker_color="#FBBC04", opacity=0.8,
        )
        fig_rev.update_layout(
            title="درآمد ماهانه (تومان)",
            barmode="overlay",
            height=360,
            xaxis_title="ماه",
            yaxis_title="تومان",
            legend=dict(orientation="h", y=1.12),
        )
        st.plotly_chart(fig_rev, use_container_width=True)

    with col_r:
        fig_rpm = px.line(
            mf1, x="month", y="rpm",
            markers=True,
            title="RPM ماهانه",
            labels={"month": "ماه", "rpm": "RPM"},
        )
        fig_rpm.update_traces(line_color="#EA4335", marker_size=8)
        fig_rpm.update_layout(height=360)
        st.plotly_chart(fig_rpm, use_container_width=True)

    st.subheader("جدول ماهانه")
    st.dataframe(
        mf1[["month", "rev", "pv", "rpm", "fixed", "billboard"]]
        .rename(columns={
            "month": "ماه", "rev": "درآمد کل", "pv": "PV ماهانه",
            "rpm": "RPM", "fixed": "فیکس", "billboard": "بیلبورد",
        })
        .sort_values("ماه", ascending=False)
        .style.format({
            "درآمد کل": "{:,.0f}", "PV ماهانه": "{:,.0f}",
            "RPM": "{:.2f}", "فیکس": "{:,.0f}", "بیلبورد": "{:,.0f}",
        }),
        use_container_width=True,
        hide_index=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — POSITIONS
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    pos_types_t2 = ["همه"] + sorted(pub_df["position_type"].unique().tolist())
    filt_t2 = st.selectbox("فیلتر نوع پوزیشن", pos_types_t2, key="t2_pt")

    fdf2 = pub_df if filt_t2 == "همه" else pub_df[pub_df["position_type"] == filt_t2]

    # Monthly publisher PV (needed for RPM per position)
    monthly_pv_pub = (
        daily_pub.groupby("month")["daily_pv"].sum().reset_index()
        .rename(columns={"daily_pv": "pub_monthly_pv"})
    )

    monthly_pos = (
        fdf2.groupby(["month", "position_id", "description", "position_type", "position_label"])
        .agg(rev=("total_adv_cost", "sum"), fixed=("fixed_adv_cost", "sum"),
             billboard=("billboard_adv_cost", "sum"))
        .reset_index()
        .merge(monthly_pv_pub, on="month")
    )
    monthly_pos["rpm"] = monthly_pos["rev"] / monthly_pos["pub_monthly_pv"] * 1_000

    # Summary per position
    total_pub_pv = daily_pub["daily_pv"].sum()
    pos_summary = (
        fdf2.groupby(["position_id", "description", "position_type", "position_label"])
        .agg(
            total_rev=("total_adv_cost", "sum"),
            total_fixed=("fixed_adv_cost", "sum"),
            total_billboard=("billboard_adv_cost", "sum"),
            active_months=("month", "nunique"),
        )
        .reset_index()
    )
    pos_summary["rpm_overall"] = pos_summary["total_rev"] / total_pub_pv * 1_000
    pos_summary["avg_monthly_rev"] = pos_summary["total_rev"] / pos_summary["active_months"]
    pos_summary["fixed_pct"] = (
        pos_summary["total_fixed"] / pos_summary["total_rev"].replace(0, np.nan) * 100
    ).fillna(0)
    pos_summary["billboard_pct"] = (
        pos_summary["total_billboard"] / pos_summary["total_rev"].replace(0, np.nan) * 100
    ).fillna(0)

    st.subheader(f"خلاصه {len(pos_summary)} پوزیشن")
    st.dataframe(
        pos_summary[[
            "description", "position_label", "avg_monthly_rev",
            "rpm_overall", "fixed_pct", "billboard_pct", "active_months",
        ]]
        .rename(columns={
            "description": "توضیحات",
            "position_label": "نوع",
            "avg_monthly_rev": "درآمد ماهانه (میانگین)",
            "rpm_overall": "RPM کل",
            "fixed_pct": "فیکس %",
            "billboard_pct": "بیلبورد %",
            "active_months": "ماه‌های فعال",
        })
        .sort_values("RPM کل", ascending=False)
        .style.format({
            "درآمد ماهانه (میانگین)": "{:,.0f}",
            "RPM کل": "{:.3f}",
            "فیکس %": "{:.1f}",
            "بیلبورد %": "{:.1f}",
        }),
        use_container_width=True,
        hide_index=True,
    )

    # RPM trend chart — top 10 positions by total revenue
    top10_ids = pos_summary.nlargest(10, "total_rev")["position_id"].tolist()
    chart_data = monthly_pos[monthly_pos["position_id"].isin(top10_ids)].copy()
    chart_data["label"] = chart_data["description"].str[:35]
    chart_data = chart_data.sort_values("month")

    st.subheader("ترند RPM ماهانه — ۱۰ پوزیشن برتر")
    fig_pos = px.line(
        chart_data,
        x="month", y="rpm", color="label",
        markers=True,
        labels={"month": "ماه", "rpm": "RPM", "label": "پوزیشن"},
    )
    fig_pos.update_layout(
        height=430,
        legend=dict(orientation="h", yanchor="top", y=-0.25, x=0),
    )
    st.plotly_chart(fig_pos, use_container_width=True)

    # Per-position monthly detail (on demand)
    st.subheader("جزئیات ماهانه هر پوزیشن")
    pos_options = ["— انتخاب کنید —"] + pos_summary.sort_values("rpm_overall", ascending=False)["description"].tolist()
    sel_pos_desc = st.selectbox("پوزیشن", pos_options, key="t2_pos")

    if sel_pos_desc != "— انتخاب کنید —":
        pos_detail = monthly_pos[monthly_pos["description"] == sel_pos_desc].sort_values("month")
        col_a, col_b = st.columns(2)
        with col_a:
            fig_pd_rev = px.bar(
                pos_detail, x="month", y="rev",
                title="درآمد ماهانه (تومان)",
                labels={"month": "ماه", "rev": "تومان"},
                color_discrete_sequence=["#4285F4"],
            )
            fig_pd_rev.update_layout(height=300)
            st.plotly_chart(fig_pd_rev, use_container_width=True)
        with col_b:
            fig_pd_rpm = px.line(
                pos_detail, x="month", y="rpm",
                markers=True,
                title="RPM ماهانه",
                labels={"month": "ماه", "rpm": "RPM"},
            )
            fig_pd_rpm.update_traces(line_color="#EA4335", marker_size=8)
            fig_pd_rpm.update_layout(height=300)
            st.plotly_chart(fig_pd_rpm, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PRICING SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    # ── Find similar publishers ───────────────────────────────────────────────
    pub_avg_pv = (
        df_f.groupby(["publisher_id", "date"])["page_views"]
        .max()
        .groupby("publisher_id")
        .mean()
    )

    if sel_id not in pub_avg_pv.index or pub_avg_pv[sel_id] <= 0:
        st.error("نمی‌توان میانگین pageview این پابلیشر را محاسبه کرد.")
        st.stop()

    target_log = np.log10(pub_avg_pv[sel_id])

    similar_ids = [
        pid for pid, pv in pub_avg_pv.items()
        if pid != sel_id and pv > 0 and abs(np.log10(pv) - target_log) <= log_window
    ]

    st.subheader("پابلیشرهای مشابه")
    col_info, _ = st.columns([2, 1])
    with col_info:
        st.info(
            f"میانگین PV روزانه شما: **{fmt_num(pub_avg_pv[sel_id])}**  "
            f"— {len(similar_ids)} پابلیشر مشابه یافت شد."
        )

    if not similar_ids:
        st.warning("هیچ پابلیشر مشابهی پیدا نشد. بازه شباهت را در سایدبار افزایش دهید.")
        st.stop()

    sim_names_df = (
        df_f[df_f["publisher_id"].isin(similar_ids)][["publisher_id", "publisher_name"]]
        .drop_duplicates()
    )
    with st.expander("نمایش لیست پابلیشرهای مشابه"):
        for _, row in sim_names_df.iterrows():
            pv = pub_avg_pv[row["publisher_id"]]
            st.write(f"• **{row['publisher_name']}** — PV روزانه: {fmt_num(pv)}")

    # ── Monthly RPM per position_label for similar publishers ─────────────────
    sim_df = df_f[df_f["publisher_id"].isin(similar_ids)].copy()

    sim_daily_pv = (
        sim_df.groupby(["publisher_id", "date"])["page_views"]
        .max()
        .reset_index()
        .rename(columns={"page_views": "pub_daily_pv"})
    )
    sim_daily_pv["month"] = pd.to_datetime(sim_daily_pv["date"]).dt.to_period("M").astype(str)

    sim_monthly_pv = (
        sim_daily_pv.groupby(["publisher_id", "month"])["pub_daily_pv"]
        .sum()
        .reset_index()
        .rename(columns={"pub_daily_pv": "pub_monthly_pv"})
    )

    sim_monthly = (
        sim_df.groupby(["publisher_id", "month", "position_label"])
        .agg(rev=("total_adv_cost", "sum"))
        .reset_index()
        .merge(sim_monthly_pv, on=["publisher_id", "month"])
    )
    sim_monthly = sim_monthly[sim_monthly["pub_monthly_pv"] > 0]
    sim_monthly["rpm"] = sim_monthly["rev"] / sim_monthly["pub_monthly_pv"] * 1_000

    # ── Scenarios per position_label ─────────────────────────────────────────
    scenarios = (
        sim_monthly.groupby("position_label")["rpm"]
        .agg(
            pessimistic=lambda x: x.quantile(0.25),
            realistic="median",
            optimistic=lambda x: x.quantile(0.75),
            n_samples="count",
        )
        .reset_index()
    )
    scenarios = scenarios[scenarios["n_samples"] >= 3]

    st.subheader("RPM پوزیشن‌های مشابه در سایت‌های مشابه")
    st.caption("هر ردیف = میانگین RPM ماهانه از پابلیشرهای مشابه برای این نوع پوزیشن")

    st.dataframe(
        scenarios.rename(columns={
            "position_label": "نوع پوزیشن",
            "pessimistic": "RPM بدبینانه",
            "realistic": "RPM واقع‌بینانه",
            "optimistic": "RPM خوش‌بینانه",
            "n_samples": "نمونه‌ها",
        })
        .sort_values("RPM واقع‌بینانه", ascending=False)
        .style.format({
            "RPM بدبینانه": "{:.3f}",
            "RPM واقع‌بینانه": "{:.3f}",
            "RPM خوش‌بینانه": "{:.3f}",
        })
        .background_gradient(subset=["RPM واقع‌بینانه"], cmap="YlGn"),
        use_container_width=True,
        hide_index=True,
    )

    # ── Per-position pricing recommendation ──────────────────────────────────
    st.subheader("پیشنهاد قیمت برای پوزیشن‌های این پابلیشر")

    target_monthly_pv = daily_pub["daily_pv"].sum() / n_months if n_months > 0 else 1
    st.caption(
        f"محاسبه بر اساس میانگین **{fmt_num(target_monthly_pv)}** پیج‌ویو ماهانه  "
        f"(میانگین {n_months} ماه)"
    )

    pub_pos_agg = (
        pub_df.groupby(["position_id", "description", "position_type", "position_label"])
        .agg(
            total_rev=("total_adv_cost", "sum"),
            months_active=("month", "nunique"),
            fixed_sum=("fixed_adv_cost", "sum"),
            billboard_sum=("billboard_adv_cost", "sum"),
        )
        .reset_index()
    )
    pub_pos_agg["current_rpm"] = pub_pos_agg["total_rev"] / total_pub_pv * 1_000
    pub_pos_agg["current_monthly_rev"] = pub_pos_agg["total_rev"] / pub_pos_agg["months_active"]
    pub_pos_agg["has_fixed"] = pub_pos_agg["fixed_sum"] > 0
    pub_pos_agg["has_billboard"] = pub_pos_agg["billboard_sum"] > 0

    pricing = pub_pos_agg.merge(
        scenarios[["position_label", "pessimistic", "realistic", "optimistic"]],
        on="position_label",
        how="left",
    )
    pricing["rev_pessimistic"] = pricing["pessimistic"] / 1_000 * target_monthly_pv
    pricing["rev_realistic"] = pricing["realistic"] / 1_000 * target_monthly_pv
    pricing["rev_optimistic"] = pricing["optimistic"] / 1_000 * target_monthly_pv

    # Flag positions with no match in similar publishers
    no_match = pricing["realistic"].isna().sum()
    if no_match:
        st.caption(
            f"⚠️ {no_match} پوزیشن در پابلیشرهای مشابه نمونه کافی ندارد (عدد خالی)."
        )

    display_pricing = pricing[[
        "description", "position_label",
        "current_monthly_rev", "current_rpm",
        "pessimistic", "realistic", "optimistic",
        "rev_pessimistic", "rev_realistic", "rev_optimistic",
        "has_fixed", "has_billboard",
    ]].rename(columns={
        "description": "توضیحات",
        "position_label": "نوع پوزیشن",
        "current_monthly_rev": "درآمد ماهانه فعلی",
        "current_rpm": "RPM فعلی",
        "pessimistic": "RPM بدبینانه",
        "realistic": "RPM واقع‌بینانه",
        "optimistic": "RPM خوش‌بینانه",
        "rev_pessimistic": "درآمد بدبینانه",
        "rev_realistic": "درآمد واقع‌بینانه",
        "rev_optimistic": "درآمد خوش‌بینانه",
        "has_fixed": "پتانسیل فیکس",
        "has_billboard": "پتانسیل بیلبورد",
    }).sort_values("درآمد واقع‌بینانه", ascending=False)

    st.dataframe(
        display_pricing.style.format(
            {
                "درآمد ماهانه فعلی": "{:,.0f}",
                "RPM فعلی": "{:.3f}",
                "RPM بدبینانه": "{:.3f}",
                "RPM واقع‌بینانه": "{:.3f}",
                "RPM خوش‌بینانه": "{:.3f}",
                "درآمد بدبینانه": "{:,.0f}",
                "درآمد واقع‌بینانه": "{:,.0f}",
                "درآمد خوش‌بینانه": "{:,.0f}",
            },
            na_rep="—",
        ),
        use_container_width=True,
        hide_index=True,
    )

    # ── Summary totals ────────────────────────────────────────────────────────
    st.subheader("جمع کل ماهانه تخمینی")

    total_bad = pricing["rev_pessimistic"].sum()
    total_real = pricing["rev_realistic"].sum()
    total_good = pricing["rev_optimistic"].sum()

    c_bad, c_real, c_good = st.columns(3)
    c_bad.metric(
        "📉 بدبینانه",
        fmt_num(total_bad, " ت"),
        delta=f"{(total_real - total_bad) / total_real * 100:.0f}% کمتر از واقع‌بینانه"
        if total_real else None,
        delta_color="off",
    )
    c_real.metric("📊 واقع‌بینانه", fmt_num(total_real, " ت"))
    c_good.metric(
        "📈 خوش‌بینانه",
        fmt_num(total_good, " ت"),
        delta=f"+{(total_good - total_real) / total_real * 100:.0f}% نسبت به واقع‌بینانه"
        if total_real else None,
    )
