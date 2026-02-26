from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid
import random

from ..database import get_db
from ..models.trade import Trade, TradeStatus, TradeType
from ..models.settings import Settings
from ..core.engine import PositionEngine
from ..services.parser import TradeParser
from ..schemas.trade import (
    TradeCreate, TradeResponse, TradeBatch,
    TradeParseRequest, TradeParseResponse
)

router = APIRouter(prefix="/api/trades", tags=["trades"])
parser = TradeParser()

@router.post("/", response_model=TradeResponse)
def create_trade(trade: TradeCreate, db: Session = Depends(get_db)):
    """
    创建单笔交易
    对应JS的handleTradeSubmit()
    """
    # 生成唯一ID
    trade_id = f"{datetime.utcnow().timestamp()}-{random.random()}"
    
    db_trade = Trade(
        id=trade_id,
        date=datetime.utcnow(),
        trader=trade.trader,
        product=trade.product,
        contract=trade.contract,
        quantity=trade.quantity,
        price=trade.price,
        status=TradeStatus.ACTIVE,
        type=trade.type or TradeType.REGULAR
    )
    
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    
    return db_trade

@router.post("/batch", response_model=List[TradeResponse])
def batch_create_trades(batch: TradeBatch, db: Session = Depends(get_db)):
    """
    批量创建交易
    对应JS的batchSubmitTrades()
    """
    trades = []
    
    for trade_data in batch.trades:
        trade_id = f"{datetime.utcnow().timestamp()}-{random.random()}"
        
        db_trade = Trade(
            id=trade_id,
            date=datetime.utcnow(),
            trader=trade_data.trader,
            product=trade_data.product,
            contract=trade_data.contract,
            quantity=trade_data.quantity,
            price=trade_data.price,
            status=TradeStatus.ACTIVE,
            type=trade_data.type or TradeType.REGULAR
        )
        
        db.add(db_trade)
        trades.append(db_trade)
    
    db.commit()
    
    for trade in trades:
        db.refresh(trade)
    
    return trades

@router.post("/parse", response_model=TradeParseResponse)
def parse_trades(request: TradeParseRequest):
    """
    解析交易文本
    对应JS的parseImportText()
    """
    parsed = parser.parse_text(request.text)
    
    return TradeParseResponse(
        count=len(parsed),
        trades=parsed,
        valid_count=sum(1 for t in parsed if t.is_valid)
    )

@router.post("/parse-and-create")
def parse_and_create(request: TradeParseRequest, db: Session = Depends(get_db)):
    """
    解析文本并创建交易
    对应JS的batchSubmitTrades()
    """
    parsed = parser.parse_text(request.text)
    
    created = []
    for p in parsed:
        if p.is_valid and p.quantity != 0 and p.price != 0:
            trade_id = f"{datetime.utcnow().timestamp()}-{random.random()}"
            
            db_trade = Trade(
                id=trade_id,
                date=datetime.utcnow(),
                trader=p.trader,
                product=p.product,
                contract=p.contract,
                quantity=p.quantity,
                price=p.price,
                status=TradeStatus.ACTIVE,
                type=TradeType.REGULAR
            )
            
            db.add(db_trade)
            created.append(db_trade)
    
    db.commit()
    
    return {
        "count": len(created),
        "parsed_count": len(parsed),
        "message": f"成功创建 {len(created)} 条交易"
    }

@router.delete("/{trade_id}")
def reverse_trade(trade_id: str, db: Session = Depends(get_db)):
    """
    撤销交易（软删除）
    对应JS的reverseTrade()
    """
    trade = db.query(Trade).filter(Trade.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="交易不存在")
    
    trade.status = TradeStatus.REVERSED
    db.commit()
    
    return {"status": "reversed", "id": trade_id}

@router.get("/", response_model=List[TradeResponse])
def get_trades(
    skip: int = 0,
    limit: int = 500,
    status: Optional[str] = None,
    filter_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取交易列表
    对应JS的renderLogs()
    """
    query = db.query(Trade)
    
    if status:
        query = query.filter(Trade.status == status)
    
    if filter_date:
        filter_dt = datetime.fromisoformat(filter_date)
        query = query.filter(Trade.date >= filter_dt)
    
    trades = query.order_by(Trade.date.desc()).offset(skip).limit(limit).all()
    
    return trades