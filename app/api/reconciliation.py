from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import datetime

from ..database import get_db
from ..models.trade import Trade, TradeStatus
from ..models.settings import Settings
from ..models.market_data import MarketData
from ..core.engine import PositionEngine
from ..core.pnl import PNLCalculator

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])

@router.get("/")
def get_reconciliation_data(
    filter_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取对账数据
    对应JS的openReconcileModal()和calcReconcile()
    """
    # 获取设置
    settings_record = db.query(Settings).filter(Settings.id == "default").first()
    settings_dict = settings_record.to_dict() if settings_record else {}
    
    rec_settings = settings_dict.get('reconciliation', {})
    
    # 获取所有active交易
    query = db.query(Trade).filter(Trade.status == TradeStatus.ACTIVE)
    
    if filter_date:
        filter_dt = datetime.fromisoformat(filter_date)
        query = query.filter(Trade.date >= filter_dt)
    
    trades = query.order_by(Trade.date).all()
    
    # 计算持仓和历史
    engine = PositionEngine(ttf_multiplier=settings_dict.get('ttfMultiplier', 3412))
    positions, history = engine.calculate_positions(trades, settings_dict)
    
    # 计算实现盈亏
    realized_total = PNLCalculator.calculate_realized_total(
        history,
        settings_dict.get('initialRealizedPL', 0) if not filter_date else 0,
        filter_date
    )
    
    # 获取市场行情
    market_prices = {}
    market_data = db.query(MarketData).all()
    for md in market_data:
        key = f"{md.product}::{md.contract}"
        market_prices[key] = md.price
    
    # 计算浮动盈亏
    floating_total = engine.calculate_total_floating(positions, market_prices, settings_dict)
    
    # 计算对账净值
    net_value = realized_total + floating_total - rec_settings.get('base', 0) - rec_settings.get('other', 0)
    
    # 持仓明细
    position_details = []
    for pos in positions:
        scoped_key = f"{pos['product']}::{pos['contract']}"
        mtm = market_prices.get(scoped_key, pos['avg_price'])
        floating = engine.calculate_floating_pnl(pos, mtm, settings_dict)
        
        position_details.append({
            "contract": pos['contract'],
            "product": pos['product'],
            "quantity": pos['quantity'],
            "avg_price": pos['avg_price'],
            "mtm": mtm,
            "floating_pnl": floating
        })
    
    return {
        "realized_total": realized_total,
        "floating_total": floating_total,
        "reconciliation_base": rec_settings.get('base', 0),
        "reconciliation_other": rec_settings.get('other', 0),
        "net_value": net_value,
        "position_details": position_details,
        "settings": rec_settings
    }

@router.post("/check")
def check_reconciliation(
    statement_value: float,
    filter_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    核对水单金额
    对应JS的calcReconcile()
    """
    data = get_reconciliation_data(filter_date, db)
    
    diff = statement_value - data['net_value']
    
    return {
        "statement_value": statement_value,
        "net_value": data['net_value'],
        "diff": diff,
        "is_match": abs(diff) < 1,
        "status": "✅ 账目吻合" if abs(diff) < 1 else "❌ 存在差异"
    }