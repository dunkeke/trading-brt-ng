from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from typing import Optional
import csv
import io
import json

from ..database import get_db
from ..models.trade import Trade, TradeStatus
from ..models.settings import Settings
from ..models.market_data import MarketData
from ..core.engine import PositionEngine
from ..core.pnl import PNLCalculator
from ..services.ai_context import AIContextGenerator

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/positions/csv")
def export_positions_csv(
    filter_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    导出持仓CSV
    对应JS的exportPositionsCSV()
    """
    # 获取设置
    settings_record = db.query(Settings).filter(Settings.id == "default").first()
    settings_dict = settings_record.to_dict() if settings_record else {}
    
    # 获取交易
    query = db.query(Trade).filter(Trade.status == TradeStatus.ACTIVE)
    trades = query.order_by(Trade.date).all()
    
    # 计算持仓
    engine = PositionEngine(ttf_multiplier=settings_dict.get('ttfMultiplier', 3412))
    positions, _ = engine.calculate_positions(trades, settings_dict)
    
    # 创建CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["合约", "交易员", "数量", "均价", "总价值"])
    
    for pos in positions:
        writer.writerow([
            pos['contract'],
            pos['trader'],
            f"{pos['quantity']:.3f}",
            f"{pos['avg_price']:.3f}",
            f"{pos['total_value']:.2f}"
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=positions.csv"}
    )

@router.get("/history/csv")
def export_history_csv(
    filter_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    导出历史平仓CSV
    对应JS的exportHistoryCSV()
    """
    # 获取设置
    settings_record = db.query(Settings).filter(Settings.id == "default").first()
    settings_dict = settings_record.to_dict() if settings_record else {}
    
    # 获取交易
    query = db.query(Trade).filter(Trade.status == TradeStatus.ACTIVE)
    trades = query.order_by(Trade.date).all()
    
    # 计算历史
    engine = PositionEngine(ttf_multiplier=settings_dict.get('ttfMultiplier', 3412))
    _, history = engine.calculate_positions(trades, settings_dict)
    
    # 创建CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", "交易员", "合约", "平仓量", "盈亏"])
    
    for h in history:
        writer.writerow([
            h['date'][:10],
            h['trader'],
            h['contract'],
            f"{h['closed_quantity']:.3f}",
            f"{h['realized_pl']:.2f}"
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=history.csv"}
    )

@router.get("/logs/csv")
def export_logs_csv(db: Session = Depends(get_db)):
    """
    导出交易日志CSV
    对应JS的exportLogCSV()
    """
    trades = db.query(Trade).filter(
        Trade.status == TradeStatus.ACTIVE
    ).order_by(Trade.date.desc()).limit(500).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["时间", "交易员", "合约", "数量", "价格", "类型"])
    
    for t in trades:
        writer.writerow([
            t.date.isoformat()[:19],
            t.trader,
            t.contract,
            f"{t.quantity:.3f}",
            f"{t.price:.3f}",
            t.type.value
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs.csv"}
    )

@router.get("/ledger/csv")
def export_ledger_csv(db: Session = Depends(get_db)):
    """
    导出逐日台账CSV
    对应JS的exportLedgerCSV()
    """
    # 简化版台账，实际需要更复杂的计算
    trades = db.query(Trade).filter(
        Trade.status == TradeStatus.ACTIVE
    ).order_by(Trade.date).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", "品种", "合约", "数量", "价格", "类型"])
    
    for t in trades:
        writer.writerow([
            t.date.isoformat()[:10],
            t.product,
            t.contract,
            f"{t.quantity:.3f}",
            f"{t.price:.3f}",
            t.type.value
        ])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ledger.csv"}
    )

@router.get("/ai-context/txt")
def export_ai_context(
    filter_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    导出AI语料
    对应JS的exportNotebookLMData()
    """
    # 获取设置
    settings_record = db.query(Settings).filter(Settings.id == "default").first()
    settings_dict = settings_record.to_dict() if settings_record else {}
    
    # 获取交易
    query = db.query(Trade).filter(Trade.status == TradeStatus.ACTIVE)
    trades = query.order_by(Trade.date).all()
    
    # 计算持仓和历史
    engine = PositionEngine(ttf_multiplier=settings_dict.get('ttfMultiplier', 3412))
    positions, history = engine.calculate_positions(trades, settings_dict)
    
    # 获取市场行情
    market_prices = {}
    market_data = db.query(MarketData).all()
    for md in market_data:
        key = f"{md.product}::{md.contract}"
        market_prices[key] = md.price
    
    # 生成上下文
    context = AIContextGenerator.generate_context(
        positions, history, settings_dict, market_prices
    )
    
    return Response(
        content=context,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=trading_context.txt"}
    )