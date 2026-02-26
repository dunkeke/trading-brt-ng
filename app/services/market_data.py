from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from ..models.market_data import MarketData, ExternalMarketData
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketDataService:
    """市场数据服务"""
    
    @staticmethod
    def get_mtm_price(db: Session, product: str, contract: str) -> Optional[float]:
        """
        获取MTM价格
        对应JS的getMtmPrice()
        """
        # 先尝试获取产品+合约的组合
        market_data = db.query(MarketData).filter(
            MarketData.product == product,
            MarketData.contract == contract
        ).first()
        
        if market_data:
            return market_data.price
        
        # 如果没有，尝试获取纯合约价格
        market_data = db.query(MarketData).filter(
            MarketData.product == "GENERIC",
            MarketData.contract == contract
        ).first()
        
        return market_data.price if market_data else None
    
    @staticmethod
    def set_mtm_price(db: Session, product: str, contract: str, price: float):
        """
        设置MTM价格
        对应JS的setMtmPrice()
        """
        market_data = db.query(MarketData).filter(
            MarketData.product == product,
            MarketData.contract == contract
        ).first()
        
        if market_data:
            market_data.price = price
            market_data.updated_at = datetime.utcnow()
        else:
            market_data = MarketData(
                id=f"{product}::{contract}",
                product=product,
                contract=contract,
                price=price
            )
            db.add(market_data)
        
        db.commit()
        return market_data
    
    @staticmethod
    def import_mtm_data(db: Session, data: Dict):
        """
        批量导入MTM数据
        对应JS的importMtmData()
        """
        count = 0
        for key, value in data.items():
            if isinstance(value, dict):
                # 格式: {"Brent": {"2605": 85.5, ...}}
                for contract, price in value.items():
                    MarketDataService.set_mtm_price(db, key, contract, float(price))
                    count += 1
            elif '::' in key:
                # 格式: "Brent::2605": 85.5
                product, contract = key.split('::')
                MarketDataService.set_mtm_price(db, product, contract, float(value))
                count += 1
            else:
                # 格式: "2605": 85.5 (通用合约)
                MarketDataService.set_mtm_price(db, "GENERIC", key, float(value))
                count += 1
        
        return count
    
    @staticmethod
    def import_daily_package(db: Session, data: Dict):
        """
        导入日报数据包
        对应JS的importDailyDataPackage()
        """
        if not data.get('date') or not data.get('prices'):
            raise ValueError("缺少必要的date或prices字段")
        
        # 创建新记录
        package = ExternalMarketData(
            id=f"daily_{data['date']}",
            date=data['date'],
            prices=data['prices'],
            news_text=data.get('news_text', '')
        )
        
        # 删除同日期旧数据
        db.query(ExternalMarketData).filter(
            ExternalMarketData.date == data['date']
        ).delete()
        
        db.add(package)
        db.commit()
        
        return package
    
    @staticmethod
    def get_latest_daily_package(db: Session) -> Optional[Dict]:
        """
        获取最新的日报数据包
        """
        package = db.query(ExternalMarketData).order_by(
            ExternalMarketData.created_at.desc()
        ).first()
        
        return package.to_dict() if package else None