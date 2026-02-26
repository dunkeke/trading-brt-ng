from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime

from ..database import get_db
from ..models.trade import Trade, TradeStatus
from ..models.settings import Settings
from ..models.market_data import MarketData
from ..core.engine import PositionEngine
from ..services.market_data import MarketDataService
from ..schemas.position import PositionResponse, PositionUpdate

router = APIRouter(prefix="/api/positions", tags=["positions"])

@router.get("/")
def get_positions(
    filter_date: Optional[str] = Query(None, description="筛选起始日期 YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    """
    获取当前持仓
    对应JS的renderPositions()和rebuildStateFromLogs()
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
    
    # 计算持仓
    engine = PositionEngine(ttf_multiplier=settings_dict.get('ttfMultiplier', 3412))
    positions, history = engine.calculate_positions(trades, settings_dict)
    
    # 获取市场行情
    market_prices = {}
    market_data = db.query(MarketData).all()
    for md in market_data:
        key = f"{md.product}::{md.contract}"
        market_prices[key] = md.price
    
    # 计算浮动盈亏
    total_floating = 0
    positions_with_pnl = []
    
    for pos in positions:
        # 获取MTM价格
        scoped_key = f"{pos['product']}::{pos['contract']}"
        mtm = market_prices.get(scoped_key)
        
        if mtm is None:
            # 尝试通用合约
            generic_key = f"GENERIC::{pos['contract']}"
            mtm = market_prices.get(generic_key)
        
        if mtm is None:
            # 默认使用持仓均价
            mtm = pos['avg_price']
        
        # 计算浮动盈亏
        floating = engine.calculate_floating_pnl(pos, mtm, settings_dict)
        total_floating += floating
        
        # 计算到岸价 (如果需要)
        landed = 0
        if pos['product'] in ['Brent', 'Henry Hub']:
            exchange_rate = settings_dict.get('exchangeRateRMB', 7.13)
            if pos['product'] == 'Brent':
                landed = (pos['avg_price'] * 0.134 + 0.46) * exchange_rate / 28.3
            else:  # Henry Hub
                landed = (pos['avg_price'] * 1.15 + 4.5) * exchange_rate / 28.3
        
        positions_with_pnl.append({
            **pos,
            "mtm": mtm,
            "floating_pnl": floating,
            "landed_cost": landed
        })
    
    # 按品种分组统计
    grouped = {}
    for pos in positions_with_pnl:
        prod = pos['product']
        if prod not in grouped:
            grouped[prod] = {
                "product": prod,
                "positions": [],
                "total_quantity": 0,
                "total_floating": 0
            }
        grouped[prod]["positions"].append(pos)
        grouped[prod]["total_quantity"] += pos['quantity']
        grouped[prod]["total_floating"] += pos['floating_pnl']
    
    return {
        "positions": positions_with_pnl,
        "grouped": list(grouped.values()),
        "total_floating": total_floating,
        "total_quantity": sum(p['quantity'] for p in positions),
        "count": len(positions)
    }

@router.put("/mtm")
def update_mtm_price(update: PositionUpdate, db: Session = Depends(get_db)):
    """
    更新MTM价格
    对应JS的updateMtmPrice()
    """
    MarketDataService.set_mtm_price(
        db, 
        update.product, 
        update.contract, 
        update.price
    )
    
    return {"status": "updated", "key": f"{update.product}::{update.contract}"}