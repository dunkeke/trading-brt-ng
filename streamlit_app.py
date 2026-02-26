from datetime import datetime
from typing import List, Dict

import pandas as pd
import streamlit as st

from app.config import settings
from app.core.engine import PositionEngine
from app.core.pnl import PNLCalculator
from app.models.trade import Trade, TradeStatus, TradeType
from app.services.parser import TradeParser


st.set_page_config(page_title="合约交易分析终端", layout="wide")

st.markdown(
    """
<style>
    .stApp { background: linear-gradient(180deg, #06102b 0%, #081734 100%); color: #e6edf7; }
    .panel {
        background: #0a1b3f; border: 1px solid #1c3f7a; border-radius: 12px;
        padding: 14px 16px; margin-bottom: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    }
    .kpi {
        background: #0c214b; border: 1px solid #23509b; border-radius: 10px;
        padding: 8px 12px;
    }
    .section-title { font-size: 1.02rem; font-weight: 700; margin-bottom: 8px; }
    .small-muted { color: #96a8c8; font-size: 0.85rem; }
</style>
""",
    unsafe_allow_html=True,
)


if "trades" not in st.session_state:
    st.session_state.trades = []
if "market_prices" not in st.session_state:
    st.session_state.market_prices = {}
if "news" not in st.session_state:
    st.session_state.news = [
        "Saudi Aramco hints output adjustment amid Asia demand shift.",
        "US LNG export outage update supports near-term gas volatility.",
        "OPEC+ monitor meeting discusses H2 balancing path.",
        "Freight rates in key clean tanker routes edge higher.",
    ]


parser = TradeParser()
engine = PositionEngine(ttf_multiplier=settings.DEFAULT_SETTINGS["ttfMultiplier"])


# ---- Left column controls ----
left_col, right_col = st.columns([1, 2.35], gap="large")

with left_col:
    st.markdown("<div class='panel'><div class='section-title'>📅 统计周期筛选</div>", unsafe_allow_html=True)
    filter_date = st.date_input("起始日期", value=datetime.utcnow().date())
    st.caption("仅展示该日期之后的交易与盈亏")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='section-title'>📝 记录交易</div>", unsafe_allow_html=True)
    import_text = st.text_area(
        "智能文本导入",
        height=100,
        placeholder="示例：Sold 10x Brent May26 @ 85.5",
    )
    if st.button("📥 智能文本导入（或追加）", use_container_width=True, type="primary"):
        parsed = parser.parse_text(import_text)
        added = 0
        for p in parsed:
            if p.is_valid and p.quantity and p.price:
                st.session_state.trades.append(
                    Trade(
                        id=f"{datetime.utcnow().timestamp()}-{added}",
                        date=datetime.utcnow(),
                        trader=p.trader,
                        product=p.product,
                        contract=p.contract,
                        quantity=p.quantity,
                        price=p.price,
                        status=TradeStatus.ACTIVE,
                        type=TradeType.REGULAR,
                    )
                )
                added += 1
        st.success(f"新增 {added} 条")

    c1, c2 = st.columns(2)
    trader = c1.selectbox("交易员", settings.TRADERS, index=0)
    product = c2.selectbox("品种", ["Brent", "Henry Hub", "JKM", "TTF"], index=0)
    contract = st.text_input("合约", value="2602")
    trade_type = st.selectbox("交易类型", [TradeType.REGULAR.value, TradeType.ADJUSTMENT.value], index=0)
    q1, q2 = st.columns(2)
    quantity = q1.number_input("数量", value=-10.0, step=1.0)
    price = q2.number_input("价格", value=85.5, step=0.1)

    if st.button("提交交易", use_container_width=True):
        st.session_state.trades.append(
            Trade(
                id=f"{datetime.utcnow().timestamp()}-manual",
                date=datetime.utcnow(),
                trader=trader,
                product=product,
                contract=contract,
                quantity=quantity,
                price=price,
                status=TradeStatus.ACTIVE,
                type=TradeType(trade_type),
            )
        )
        st.success("交易已提交")

    if st.button("清空所有交易", use_container_width=True):
        st.session_state.trades = []
        st.session_state.market_prices = {}
        st.warning("已清空")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='section-title'>⚙️ 参数设置</div>", unsafe_allow_html=True)
    brent_fee = st.number_input("Brent 费率", value=0.0, step=0.0001, format="%.4f")
    hh_fee = st.number_input("Gas(HH/JKM) 费率", value=0.0, step=0.0001, format="%.4f")
    ttf_multiplier = st.number_input("TTF 换算", value=3412.0, step=1.0)
    exchange_rate = st.number_input("USD/CNY 汇率", value=6.96, step=0.01)
    initial_realized = st.number_input("初始已实现盈亏", value=0.0, step=1000.0)
    st.markdown("</div>", unsafe_allow_html=True)


settings_dict = {
    "fees": {"brentPerBbl": brent_fee, "hhPerMMBtu": hh_fee},
    "ttfMultiplier": ttf_multiplier,
    "exchangeRateRMB": exchange_rate,
    "initialRealizedPL": initial_realized,
}
engine.ttf_multiplier = ttf_multiplier


# ---- Right dashboard ----
with right_col:
    trades: List[Trade] = [t for t in st.session_state.trades if t.date.date() >= filter_date]
    positions, history = engine.calculate_positions(trades, settings_dict)

    k1, k2, k3, k4 = st.columns(4)
    total_realized = PNLCalculator.calculate_realized_total(history, initial_realized)
    market_prices: Dict[str, float] = st.session_state.market_prices
    total_floating = engine.calculate_total_floating(positions, market_prices, settings_dict)
    total_qty = sum(abs(p["quantity"]) for p in positions)

    k1.metric("交易笔数", len(trades))
    k2.metric("当前持仓", len(positions))
    k3.metric("总浮动盈亏", f"{total_floating:,.2f}")
    k4.metric("累计已实现", f"{total_realized:,.2f}")

    st.markdown("<div class='panel'><div class='section-title'>🌍 市场行情可视化</div>", unsafe_allow_html=True)
    market_rows = []
    for p in ["Brent", "WTI", "Gasoline", "Diesel"]:
        default_value = 70.0 if p in ["Brent", "WTI"] else 1.5
        market_rows.append({"品种": p, "价格": default_value})
    market_df = pd.DataFrame(market_rows)

    g1, g2 = st.columns([2, 1], gap="medium")
    with g1:
        st.bar_chart(market_df, x="品种", y="价格", height=260)
    with g2:
        st.markdown("**📰 资讯流**")
        for n in st.session_state.news:
            st.caption(f"• {n}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='section-title'>🚀 当前持仓</div>", unsafe_allow_html=True)
    if positions:
        df_pos = pd.DataFrame(positions)
        for idx, row in df_pos.iterrows():
            key = f"{row['product']}::{row['contract']}"
            if key not in market_prices:
                market_prices[key] = float(row["avg_price"])
            market_prices[key] = st.number_input(
                f"MTM {key}",
                value=float(market_prices[key]),
                key=f"mtm_{key}",
                step=0.1,
            )
            df_pos.loc[idx, "mtm"] = market_prices[key]
            df_pos.loc[idx, "floating_pnl"] = engine.calculate_floating_pnl(row.to_dict(), market_prices[key], settings_dict)
            df_pos.loc[idx, "方向"] = "Long" if row["quantity"] > 0 else "Short"

        show_cols = ["trader", "product", "contract", "quantity", "方向", "avg_price", "mtm", "floating_pnl"]
        st.dataframe(df_pos[show_cols], use_container_width=True, height=280)

        subtotal = (
            df_pos.groupby("product", as_index=False)
            .agg(total_qty=("quantity", "sum"), total_floating=("floating_pnl", "sum"))
            .sort_values("total_floating", ascending=False)
        )
        st.caption("分品种汇总")
        st.dataframe(subtotal, use_container_width=True, height=150)
    else:
        st.info("暂无持仓")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='section-title'>📒 交易日志 & 历史平仓</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**交易日志（最近500条）**")
        if trades:
            df_t = pd.DataFrame([
                {
                    "date": t.date,
                    "trader": t.trader,
                    "product": t.product,
                    "contract": t.contract,
                    "quantity": t.quantity,
                    "price": t.price,
                    "status": t.status.value,
                }
                for t in trades
            ]).sort_values("date", ascending=False)
            st.dataframe(df_t.head(500), use_container_width=True, height=220)
        else:
            st.caption("暂无数据")

    with c2:
        st.markdown("**历史平仓（最近500条）**")
        if history:
            df_h = pd.DataFrame(history).sort_values("date", ascending=False)
            st.dataframe(df_h.head(500), use_container_width=True, height=220)
        else:
            st.caption("暂无数据")

    csv_data = pd.DataFrame(history).to_csv(index=False).encode("utf-8") if history else "".encode("utf-8")
    st.download_button("导出 CSV", csv_data, file_name="history_export.csv", use_container_width=False)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"<div class='small-muted'>更新时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</div>", unsafe_allow_html=True)
