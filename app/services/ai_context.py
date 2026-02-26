from typing import List, Dict, Optional
from datetime import datetime
import json

class AIContextGenerator:
    """
    AI语料生成器
    对应JS的exportNotebookLMData()
    """
    
    @staticmethod
    def generate_context(positions: List[Dict], 
                        history: List[Dict],
                        settings: Dict,
                        market_prices: Dict = None) -> str:
        """
        生成AI上下文文本
        """
        lines = []
        lines.append("# 交易分析上下文数据")
        lines.append(f"\n## 1. 生成时间")
        lines.append(f"- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 账户概览
        lines.append("\n## 2. 账户概览")
        
        # 按品种汇总
        grouped = {}
        for pos in positions:
            prod = pos['product']
            if prod not in grouped:
                grouped[prod] = []
            grouped[prod].append(pos)
        
        total_realized = settings.get('initialRealizedPL', 0)
        for h in history:
            total_realized += h['realized_pl']
        
        for prod, pos_list in grouped.items():
            net_qty = sum(p['quantity'] for p in pos_list)
            total_cost = sum(p['total_value'] for p in pos_list)
            multiplier = 1000  # 简化
            if prod == 'TTF':
                multiplier = settings.get('ttfMultiplier', 3412)
            
            w_avg = total_cost / (net_qty * multiplier) if abs(net_qty) > 0.001 else 0
            
            lines.append(f"- {prod}: 净持仓 {net_qty:.3f} 手, 加权均价 {w_avg:.4f}")
        
        lines.append(f"- 累计实现盈亏: ${total_realized:,.2f}")
        
        # 历史平仓记录
        lines.append("\n## 3. 历史平仓记录 (最近50笔)")
        recent = sorted(history, key=lambda x: x['date'], reverse=True)[:50]
        
        for h in recent:
            date_str = h['date'][:10]
            lines.append(
                f"- {date_str}: {h['trader']} 平仓 {h['contract']} "
                f"{abs(h['closed_quantity']):.3f}手, 盈亏 ${h['realized_pl']:,.2f}"
            )
        
        # 市场行情
        if market_prices:
            lines.append("\n## 4. 市场行情快照")
            for key, price in list(market_prices.items())[:20]:
                lines.append(f"- {key}: {price}")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_dashboard_report(positions: List[Dict],
                                  history: List[Dict],
                                  settings: Dict,
                                  filter_date: Optional[str] = None,
                                  market_data: Optional[Dict] = None) -> str:
        """
        生成综合看板报告
        对应JS的exportDashboardReport()
        """
        today = datetime.now().strftime('%Y-%m-%d')
        lines = []
        lines.append(f"=== 交易复盘看板 [{today}] ===")
        
        if filter_date:
            lines.append(f"(筛选起始：{filter_date})")
        lines.append("")
        
        # 盈亏汇总
        total_realized = settings.get('initialRealizedPL', 0)
        for h in history:
            if filter_date and h['date'] < filter_date:
                continue
            total_realized += h['realized_pl']
        
        rec_other = settings.get('reconciliation', {}).get('other', 0)
        adjusted_realized = total_realized - rec_other
        
        lines.append(f"历史累计平仓实现-对账调节项: ${adjusted_realized:,.2f}")
        
        # 浮动盈亏
        lines.append(f"当前浮动盈亏: $0.00")  # 需要计算
        
        # 当日平仓明细
        lines.append("\n--- 当日平仓明细 ---")
        today_history = [h for h in history if h['date'].startswith(today)]
        
        if not today_history:
            lines.append("无")
        else:
            for h in today_history:
                lines.append(
                    f"{h['contract']} | {abs(h['closed_quantity']):.1f}手 | "
                    f"盈亏: {h['realized_pl']:,.0f}"
                )
        
        # 持仓汇总
        lines.append("\n--- 持仓汇总 ---")
        grouped = {}
        for pos in positions:
            prod = pos['product']
            if prod not in grouped:
                grouped[prod] = []
            grouped[prod].append(pos)
        
        for prod, pos_list in grouped.items():
            net_qty = sum(p['quantity'] for p in pos_list)
            lines.append(f"{prod}: 净持仓 {net_qty:.3f}")
        
        # 市场行情
        if market_data and market_data.get('prices'):
            lines.append(f"\n--- 市场行情快照({market_data.get('date', '未知日期')}) ---")
            for key, val in market_data['prices'].items():
                lines.append(f"{key}: {val}")
        
        return "\n".join(lines)