from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, List
import json

from ..database import get_db
from ..models.market_data import MarketData, ExternalMarketData
from ..services.market_data import MarketDataService

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("/prices")
def get_market_prices(
    product: Optional[str] = None,
    contract: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    获取市场行情
    """
    query = db.query(MarketData)
    
    if product:
        query = query.filter(MarketData.product == product)
    if contract:
        query = query.filter(MarketData.contract == contract)
    
    prices = query.all()
    
    return {
        "count": len(prices),
        "prices": [p.to_dict() for p in prices]
    }

@router.post("/prices/import")
async def import_mtm_prices(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    导入MTM价格
    对应JS的importMtmData()
    """
    content = await file.read()
    data = json.loads(content)
    
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="文件格式错误，需要JSON对象")
    
    count = MarketDataService.import_mtm_data(db, data)
    
    return {"message": f"成功导入 {count} 条价格数据"}

@router.post("/daily/import")
async def import_daily_package(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    导入日报数据包
    对应JS的importDailyDataPackage()
    """
    content = await file.read()
    data = json.loads(content)
    
    try:
        package = MarketDataService.import_daily_package(db, data)
        return {
            "message": f"成功导入日报数据 {package.date}",
            "date": package.date
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/daily/latest")
def get_latest_daily_package(db: Session = Depends(get_db)):
    """
    获取最新日报数据
    对应JS的renderExternalMarketSnapshot()
    """
    package = MarketDataService.get_latest_daily_package(db)
    
    if not package:
        return {"message": "暂无日报数据"}
    
    return package