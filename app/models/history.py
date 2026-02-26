from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ..database import get_db
from ..models.trade import Trade, TradeStatus
from ..models.settings import Settings
from ..core.engine import PositionEngine
from ..core.pnl import PNLCalculator

router = APIRouter(prefix="/api/history", tags=["history"])

@router.get("/")
def get_history(
    filter_date: Optional[str] = Query(None, description="筛选起始日期 YYYY-MM-DD"),
    limit: int = Query(500, description="返回条数"),
    db: Session = Depends(get_db)
):
    """
    获取历史平仓记录
    对应JS的renderHistory()
    """
    # 获取设置
    settings_record = db.query(Settings).filter(Settings.id == "default").first()
    settings_dict = settings_record.to_dict() if settings_record else {}
    
    # 获取所有active交易
    query = db.query(Trade).filter(Trade.status == TradeStatus.ACTIVE)
    
    if filter_date:
        filter_dt = datetime.fromisoformat(filter_date)
        query = query.filter(Trade.date >= filter_dt)
    
    trades = query.order_by(Trade.date).all()
    
    # 计算持仓和历史
    engine = PositionEngine(ttf_multiplier=settings_dict.get('ttfMultiplier', 3412))
    positions, history = engine.calculate_positions(trades, settings_dict)
    
    # 按日期倒序排序
    history.sort(key=lambda x: x['date'], reverse=True)
    
    # 计算累计盈亏
    total_realized = PNLCalculator.calculate_realized_total(
        history,
        settings_dict.get('initialRealizedPL', 0) if not filter_date else 0,
        filter_date
    )
    
    # 每日汇总
    daily_pnl = PNLCalculator.get_daily_pnl(history)
    
    # 交易员汇总
    trader_pnl = PNLCalculator.get_trader_pnl(history)
    
    # 品种汇总
    product_pnl = PNLCalculator.get_product_pnl(history)
    
    return {
        "history": history[:limit],
        "total_realized": total_realized,
        "daily_pnl": daily_pnl,
        "trader_pnl": trader_pnl,
        "product_pnl": product_pnl,
        "count": len(history)
    }