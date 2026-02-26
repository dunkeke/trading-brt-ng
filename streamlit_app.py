from datetime import datetime
import pandas as pd
import streamlit as st

from app.config import settings
from app.core.engine import PositionEngine
from app.core.pnl import PNLCalculator
from app.models.trade import Trade, TradeStatus, TradeType
from app.services.parser import TradeParser


st.set_page_config(page_title="合约交易分析终端", layout="wide")
st.title("📈 合约交易分析终端（Streamlit 版）")
st.caption("可直接部署到 Streamlit Cloud，无需单独后端 API。")


if "trades" not in st.session_state:
    st.session_state.trades = []

if "market_prices" not in st.session_state:
    st.session_state.market_prices = {}

parser = TradeParser()
engine = PositionEngine(ttf_multiplier=settings.DEFAULT_SETTINGS["ttfMultiplier"])

with st.sidebar:
    st.header("参数")
    brent_fee = st.number_input("Brent 费率", min_value=0.0, value=0.0, step=0.0001, format="%.4f")
    hh_fee = st.number_input("HH/其他费率", min_value=0.0, value=0.0, step=0.0001, format="%.4f")
    ttf_multiplier = st.number_input("TTF 倍数", min_value=1.0, value=3412.0, step=1.0)
    initial_realized = st.number_input("初始已实现盈亏", value=0.0)

settings_dict = {
    "fees": {"brentPerBbl": brent_fee, "hhPerMMBtu": hh_fee},
    "ttfMultiplier": ttf_multiplier,
    "initialRealizedPL": initial_realized,
}
engine.ttf_multiplier = ttf_multiplier


with st.expander("1) 导入交易文本", expanded=True):
    text = st.text_area("粘贴交易文本（每行一笔）", height=180, placeholder="Sold 200x Brent May26 @ 84.2")
    col1, col2 = st.columns(2)
    if col1.button("解析并加入交易", type="primary"):
        parsed = parser.parse_text(text)
        added = 0
        for p in parsed:
            if p.is_valid and p.quantity != 0 and p.price != 0:
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
        st.success(f"已新增 {added} 条交易")

    if col2.button("清空交易", type="secondary"):
        st.session_state.trades = []
        st.session_state.market_prices = {}
        st.warning("已清空")


trades = st.session_state.trades
positions, history = engine.calculate_positions(trades, settings_dict)

st.subheader("2) 当前交易")
if trades:
    df_trades = pd.DataFrame(
        [
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
        ]
    ).sort_values("date", ascending=False)
    st.dataframe(df_trades, use_container_width=True)
else:
    st.info("暂无交易")

st.subheader("3) 持仓与浮盈")
for pos in positions:
    key = f"{pos['product']}::{pos['contract']}"
    default_mtm = st.session_state.market_prices.get(key, pos["avg_price"])
    st.session_state.market_prices[key] = st.number_input(
        f"MTM - {key}",
        value=float(default_mtm),
        key=f"mtm_{key}",
    )

market_prices = st.session_state.market_prices
total_floating = engine.calculate_total_floating(positions, market_prices, settings_dict)
total_realized = PNLCalculator.calculate_realized_total(history, initial_realized)

metric_cols = st.columns(3)
metric_cols[0].metric("当前持仓数", len(positions))
metric_cols[1].metric("总浮动盈亏", f"{total_floating:,.2f}")
metric_cols[2].metric("累计已实现盈亏", f"{total_realized:,.2f}")

if positions:
    df_pos = pd.DataFrame(positions)
    df_pos["mtm"] = df_pos.apply(lambda r: market_prices.get(f"{r['product']}::{r['contract']}", r["avg_price"]), axis=1)
    df_pos["floating_pnl"] = df_pos.apply(
        lambda r: engine.calculate_floating_pnl(r.to_dict(), r["mtm"], settings_dict),
        axis=1,
    )
    st.dataframe(df_pos, use_container_width=True)

st.subheader("4) 历史平仓")
if history:
    df_h = pd.DataFrame(history).sort_values("date", ascending=False)
    st.dataframe(df_h, use_container_width=True)
else:
    st.info("暂无平仓历史")
