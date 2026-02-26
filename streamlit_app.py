from __future__ import annotations

from datetime import datetime
import json
from typing import Dict, List

import pandas as pd
import streamlit as st

from app.config import settings
from app.core.engine import PositionEngine
from app.core.pnl import PNLCalculator
from app.models.trade import Trade, TradeStatus, TradeType
from app.services.parser import TradeParser


st.set_page_config(page_title="合约交易分析终端Pro", layout="wide")

st.markdown(
    """
<style>
    .stApp { background: radial-gradient(circle at top, rgba(30,58,138,0.35), rgba(2,6,23,0.95) 55%), linear-gradient(180deg, #0b1120 0%, #020617 100%); color: #e2e8f0; }
    .panel { background: rgba(15,23,42,0.78); border: 1px solid rgba(148,163,184,0.2); border-radius: 12px; padding: 14px; margin-bottom: 12px; }
    .panel-title { color: #e2e8f0; font-weight: 700; margin-bottom: 6px; }
    .muted { color: #94a3b8; font-size: 0.82rem; }
</style>
""",
    unsafe_allow_html=True,
)


def init_state() -> None:
    if "trades" not in st.session_state:
        st.session_state.trades = []
    if "market_prices" not in st.session_state:
        st.session_state.market_prices = {}
    if "external_market_data" not in st.session_state:
        st.session_state.external_market_data = None
    if "news_feed" not in st.session_state:
        st.session_state.news_feed = [
            "OPEC+ monitor meeting discusses H2 balancing path.",
            "US LNG export outage update supports near-term gas volatility.",
            "Middle-east freight route premiums drift higher.",
            "Asian prompt cargo demand stays resilient this week.",
        ]


def trade_to_dict(t: Trade) -> Dict:
    return {
        "id": t.id,
        "date": t.date.isoformat(),
        "trader": t.trader,
        "product": t.product,
        "contract": t.contract,
        "quantity": t.quantity,
        "price": t.price,
        "status": t.status.value,
        "type": t.type.value,
    }


def dict_to_trade(obj: Dict) -> Trade:
    return Trade(
        id=obj["id"],
        date=datetime.fromisoformat(obj["date"]),
        trader=obj["trader"],
        product=obj["product"],
        contract=obj["contract"],
        quantity=float(obj["quantity"]),
        price=float(obj["price"]),
        status=TradeStatus(obj.get("status", "active")),
        type=TradeType(obj.get("type", "regular")),
    )


def compute_stress_change(positions: List[Dict], brent_delta: float, gas_delta: float, ttf_delta: float, ttf_mult: float) -> float:
    total = 0.0
    for p in positions:
        if p["product"] == "Brent":
            delta = brent_delta
        elif p["product"] in ["Henry Hub", "JKM"]:
            delta = gas_delta
        else:
            delta = ttf_delta
        mult = settings.CONTRACT_MULTIPLIERS.get(p["product"], 1000)
        if p["product"] == "TTF":
            mult *= ttf_mult
        total += delta * p["quantity"] * mult
    return total


def build_ai_context_text(positions: List[Dict], history: List[Dict], total_realized: float) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = ["# 交易分析上下文数据", f"生成时间: {now} UTC", "", "## 持仓汇总"]
    if positions:
        df = pd.DataFrame(positions)
        grp = df.groupby("product", as_index=False).agg(net_qty=("quantity", "sum"), avg_price=("avg_price", "mean"))
        for _, r in grp.iterrows():
            lines.append(f"- {r['product']}: 净持仓 {r['net_qty']:.3f}, 平均价格 {r['avg_price']:.4f}")
    else:
        lines.append("- 暂无持仓")
    lines.extend(["", f"累计已实现盈亏: {total_realized:,.2f}", "", "## 最近平仓(前50)"])
    for h in history[:50]:
        lines.append(f"- {h['date'][:10]} {h['contract']} {h['closed_quantity']:.3f} -> {h['realized_pl']:.2f}")
    return "\n".join(lines)


init_state()
parser = TradeParser()
engine = PositionEngine(ttf_multiplier=settings.DEFAULT_SETTINGS["ttfMultiplier"])

st.markdown("""
<div style='text-align:center;margin-bottom:14px'>
<p style='letter-spacing:0.35em;color:#7dd3fc;font-size:12px;margin:0'>Aurora Trading Systems dundun©️</p>
<h1 style='margin:8px 0 4px 0;font-size:34px;'>合约交易分析终端Pro</h1>
<p style='color:#94a3b8;margin:0'>复盘看板版：当日平仓统计 | 综合仪表盘 | 导出报告</p>
</div>
""", unsafe_allow_html=True)

left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.markdown("<div class='panel'><div class='panel-title'>📅 统计周期筛选</div>", unsafe_allow_html=True)
    filter_date = st.date_input("起始日期", value=datetime.utcnow().date())
    st.markdown("<div class='muted'>仅统计该日期及之后交易。</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>📝 记录交易</div>", unsafe_allow_html=True)
    import_text = st.text_area("智能文本批量导入", height=120, placeholder="Sold 200x Brent May26 @ 85.5")
    if st.button("📥 解析并导入", use_container_width=True, type="primary"):
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
        st.success(f"导入 {added} 条")

    with st.expander("手动录入", expanded=True):
        c1, c2 = st.columns(2)
        trader = c1.selectbox("交易员", settings.TRADERS, index=0)
        product = c2.selectbox("品种", ["Brent", "Henry Hub", "JKM", "TTF"], index=0)
        contracts = settings.CONTRACTS.get(product, ["2602"])
        contract = st.selectbox("合约", contracts, index=0)
        trade_type = st.selectbox("交易类型", [TradeType.REGULAR.value, TradeType.ADJUSTMENT.value], index=0)
        q1, q2 = st.columns(2)
        quantity = q1.number_input("数量(负=卖)", value=-10.0, step=1.0)
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
            st.success("已提交")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>⚙️ 参数设置</div>", unsafe_allow_html=True)
    brent_fee = st.number_input("Brent 费用", value=0.0, step=0.0001, format="%.4f")
    hh_fee = st.number_input("Gas(HH/JKM) 费用", value=0.0, step=0.0001, format="%.4f")
    ttf_multiplier = st.number_input("TTF 换算", value=3412.0, step=1.0)
    exchange_rate = st.number_input("USD/CNY 汇率", value=6.96, step=0.01)
    initial_realized = st.number_input("期初盈亏", value=0.0, step=1000.0)
    rec_base = st.number_input("对账基准金", value=156170.0, step=1000.0)
    rec_other = st.number_input("对账调节项", value=45800.0, step=1000.0)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>💾 数据与报表</div>", unsafe_allow_html=True)
    export_payload = {
        "trades": [trade_to_dict(t) for t in st.session_state.trades],
        "market_prices": st.session_state.market_prices,
        "external_market_data": st.session_state.external_market_data,
    }
    st.download_button("备份数据(JSON)", data=json.dumps(export_payload, ensure_ascii=False, indent=2), file_name="trade_backup.json", use_container_width=True)

    imported = st.file_uploader("恢复备份JSON", type=["json"], key="restore_backup")
    if imported is not None:
        try:
            obj = json.loads(imported.read().decode("utf-8"))
            st.session_state.trades = [dict_to_trade(x) for x in obj.get("trades", [])]
            st.session_state.market_prices = obj.get("market_prices", {})
            st.session_state.external_market_data = obj.get("external_market_data")
            st.success("恢复成功")
        except Exception as e:
            st.error(f"恢复失败: {e}")

    mtm_file = st.file_uploader("导入行情(JSON)", type=["json"], key="mtm_json")
    if mtm_file is not None:
        try:
            mtm_obj = json.loads(mtm_file.read().decode("utf-8"))
            mp = mtm_obj.get("marketPrices", mtm_obj)
            if isinstance(mp, dict):
                for k, v in mp.items():
                    if isinstance(v, dict):
                        for c, px in v.items():
                            st.session_state.market_prices[f"{k}::{c}"] = float(px)
                    else:
                        if "::" in k:
                            st.session_state.market_prices[k] = float(v)
                st.success("行情已更新")
        except Exception as e:
            st.error(f"导入失败: {e}")

    daily_file = st.file_uploader("导入日报数据包(daily_data.json)", type=["json"], key="daily_pkg")
    if daily_file is not None:
        try:
            daily_obj = json.loads(daily_file.read().decode("utf-8"))
            st.session_state.external_market_data = daily_obj
            st.success("日报数据已导入")
        except Exception as e:
            st.error(f"导入失败: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    if st.button("🧹 清空交易与行情", use_container_width=True):
        st.session_state.trades = []
        st.session_state.market_prices = {}
        st.session_state.external_market_data = None
        st.warning("已清空")

settings_dict = {
    "fees": {"brentPerBbl": brent_fee, "hhPerMMBtu": hh_fee},
    "exchangeRateRMB": exchange_rate,
    "ttfMultiplier": ttf_multiplier,
    "initialRealizedPL": initial_realized,
    "reconciliation": {"base": rec_base, "other": rec_other},
}
engine.ttf_multiplier = ttf_multiplier

with right_col:
    trades: List[Trade] = [t for t in st.session_state.trades if t.date.date() >= filter_date]
    positions, history = engine.calculate_positions(trades, settings_dict)
    history.sort(key=lambda x: x["date"], reverse=True)

    market_prices: Dict[str, float] = st.session_state.market_prices
    total_floating = engine.calculate_total_floating(positions, market_prices, settings_dict)
    total_realized = PNLCalculator.calculate_realized_total(history, initial_realized)
    reconciled_net = total_realized + total_floating - rec_base - rec_other

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("当日交易笔数", len(trades))
    k2.metric("当前持仓", len(positions))
    k3.metric("当前总浮动盈亏", f"{total_floating:,.2f}")
    k4.metric("历史累计平仓实现", f"{(total_realized-rec_other):,.2f}")

    st.markdown("<div class='panel'><div class='panel-title'>🌍 市场行情可视化（daily_data.json）</div>", unsafe_allow_html=True)
    daily = st.session_state.external_market_data
    c1, c2 = st.columns([2, 1])
    with c1:
        if daily and isinstance(daily, dict) and isinstance(daily.get("prices"), dict):
            label_map = {
                "brent_future": "Brent",
                "wti_future": "WTI",
                "gasoline": "Gasoline",
                "diesel": "Diesel",
                "murban_crude": "Murban",
                "dme_oman": "DME Oman",
            }
            rows = []
            for k, name in label_map.items():
                v = daily["prices"].get(k)
                if v is not None:
                    rows.append({"品种": name, "价格": float(v)})
            if rows:
                st.bar_chart(pd.DataFrame(rows), x="品种", y="价格", height=260)
            else:
                st.info("导入数据中缺少可展示价格")
        else:
            fallback = pd.DataFrame([
                {"品种": "Brent", "价格": 70.0},
                {"品种": "WTI", "价格": 65.0},
                {"品种": "Gasoline", "价格": 2.2},
                {"品种": "Diesel", "价格": 2.5},
            ])
            st.bar_chart(fallback, x="品种", y="价格", height=260)
    with c2:
        st.caption(f"数据日期：{daily.get('date','未导入') if isinstance(daily, dict) else '未导入'}")
        st.markdown("**📰 要闻速览**")
        if isinstance(daily, dict) and daily.get("news_text"):
            for item in str(daily.get("news_text")).split("\n\n")[:5]:
                st.caption(f"• {item[:140]}")
        else:
            for item in st.session_state.news_feed:
                st.caption(f"• {item}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>⚡ 压力测试</div>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    brent_delta = s1.number_input("Brent 变动($)", value=0.0, step=0.1)
    gas_delta = s2.number_input("Gas 变动($)", value=0.0, step=0.1)
    ttf_delta = s3.number_input("TTF 变动($)", value=0.0, step=0.1)
    shock = compute_stress_change(positions, brent_delta, gas_delta, ttf_delta, ttf_multiplier)
    st.info(f"预计 P/L 变动: {shock:,.2f} | 新浮动 P/L: {total_floating + shock:,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>🚀 当前持仓</div>", unsafe_allow_html=True)
    if positions:
        pos_df = pd.DataFrame(positions)
        for idx, row in pos_df.iterrows():
            scoped = f"{row['product']}::{row['contract']}"
            if scoped not in market_prices:
                market_prices[scoped] = float(row["avg_price"])
            market_prices[scoped] = st.number_input(
                f"MTM {scoped}",
                value=float(market_prices[scoped]),
                key=f"mtm_{scoped}",
                step=0.01,
            )
            pos_df.loc[idx, "方向"] = "Long" if row["quantity"] > 0 else "Short"
            pos_df.loc[idx, "mtm"] = market_prices[scoped]
            pos_df.loc[idx, "floating_pnl"] = engine.calculate_floating_pnl(row.to_dict(), market_prices[scoped], settings_dict)

        grouped = (
            pos_df.groupby("product", as_index=False)
            .agg(total_qty=("quantity", "sum"), total_floating=("floating_pnl", "sum"), wavg=("avg_price", "mean"))
            .sort_values("total_floating", ascending=False)
        )
        st.dataframe(
            pos_df[["trader", "product", "contract", "quantity", "方向", "avg_price", "mtm", "floating_pnl"]],
            use_container_width=True,
            height=300,
        )
        st.caption("SUBTOTAL（分品种）")
        st.dataframe(grouped, use_container_width=True, height=160)

        selected_key = st.selectbox("快速撤销（按持仓键）", options=sorted(pos_df["key"].unique().tolist()))
        if st.button("撤销该持仓最新一笔交易"):
            idx = None
            for i in range(len(st.session_state.trades) - 1, -1, -1):
                t = st.session_state.trades[i]
                key = f"{t.trader}-{t.product}-{t.contract}"
                if key == selected_key and t.status == TradeStatus.ACTIVE:
                    idx = i
                    break
            if idx is None:
                st.warning("未找到可撤销交易")
            else:
                st.session_state.trades[idx].status = TradeStatus.REVERSED
                st.success("已撤销最新一笔")
    else:
        st.info("暂无持仓")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>📜 交易日志 & 🏁 历史平仓</div>", unsafe_allow_html=True)
    t1, t2 = st.columns(2)
    with t1:
        q = st.text_input("搜索交易日志", value="")
        tx_rows = [
            {
                "时间": t.date.strftime("%Y-%m-%d %H:%M:%S"),
                "交易员": t.trader,
                "合约": t.contract,
                "数量": t.quantity,
                "价格": t.price,
                "状态": t.status.value,
            }
            for t in sorted(trades, key=lambda x: x.date, reverse=True)
        ]
        tx_df = pd.DataFrame(tx_rows)
        if not tx_df.empty and q:
            tx_df = tx_df[tx_df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
        st.dataframe(tx_df.head(500), use_container_width=True, height=260)

    with t2:
        qh = st.text_input("搜索历史平仓", value="")
        hist_df = pd.DataFrame(history)
        if not hist_df.empty and qh:
            hist_df = hist_df[hist_df.astype(str).apply(lambda x: x.str.contains(qh, case=False)).any(axis=1)]
        st.dataframe(hist_df.head(500), use_container_width=True, height=260)
        st.metric("累计实现盈亏", f"{total_realized:,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='panel'><div class='panel-title'>📊 数据可视化 + 复盘导出</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if positions:
            abs_pos = pd.DataFrame(positions).copy()
            abs_pos["abs_qty"] = abs_pos["quantity"].abs()
            pie_df = abs_pos.groupby("product", as_index=False)["abs_qty"].sum()
            st.bar_chart(pie_df, x="product", y="abs_qty", height=220)
        else:
            st.caption("暂无持仓结构图")
    with c2:
        if history:
            curve = pd.DataFrame(history).sort_values("date")
            curve["cum_realized"] = curve["realized_pl"].cumsum() + initial_realized
            st.line_chart(curve.set_index("date")["cum_realized"], height=220)
        else:
            st.caption("暂无累计盈亏曲线")

    rec_text = f"App净值 = 实现({total_realized:,.2f}) + 浮动({total_floating:,.2f}) - 基准({rec_base:,.2f}) - 调节({rec_other:,.2f}) = {reconciled_net:,.2f}"
    st.info(rec_text)

    history_csv = pd.DataFrame(history).to_csv(index=False).encode("utf-8") if history else b""
    st.download_button("导出历史CSV", data=history_csv, file_name="history.csv")

    ai_text = build_ai_context_text(positions, history, total_realized)
    st.download_button("🤖 生成AI语料(.txt)", data=ai_text.encode("utf-8"), file_name="trading_context_for_ai.txt")
    st.markdown("</div>", unsafe_allow_html=True)

st.caption(f"dundunke©️ | 更新时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
