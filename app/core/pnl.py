from typing import List, Dict, Optional
from datetime import datetime, date
from ..models.history import HistoryEntry

class PNLCalculator:
    """盈亏计算器 - 各种统计功能"""
    
    @staticmethod
    def calculate_realized_total(history: List[Dict], 
                                 initial_pl: float = 0,
                                 filter_date: Optional[str] = None) -> float:
        """
        计算累计实现盈亏
        对应JS中的历史盈亏合计逻辑
        """
        total = initial_pl
        
        for h in history:
            if filter_date:
                if h['date'] >= filter_date:
                    total += h['realized_pl']
            else:
                total += h['realized_pl']
        
        return total
    
    @staticmethod
    def get_daily_pnl(history: List[Dict], days: int = 30) -> Dict[str, float]:
        """
        获取每日盈亏汇总
        """
        daily = {}
        
        for h in history:
            day = h['date'][:10]  # YYYY-MM-DD
            daily[day] = daily.get(day, 0) + h['realized_pl']
        
        # 排序并限制天数
        sorted_days = sorted(daily.items(), key=lambda x: x[0], reverse=True)[:days]
        return dict(sorted_days)
    
    @staticmethod
    def get_trader_pnl(history: List[Dict]) -> Dict[str, float]:
        """
        按交易员统计盈亏
        """
        result = {}
        for h in history:
            result[h['trader']] = result.get(h['trader'], 0) + h['realized_pl']
        return result
    
    @staticmethod
    def get_product_pnl(history: List[Dict]) -> Dict[str, float]:
        """
        按品种统计盈亏
        """
        result = {}
        for h in history:
            result[h['product']] = result.get(h['product'], 0) + h['realized_pl']
        return result