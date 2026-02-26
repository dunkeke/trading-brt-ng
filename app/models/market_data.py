from sqlalchemy import Column, String, Float, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class MarketData(Base):
    __tablename__ = "market_data"
    
    id = Column(String, primary_key=True)
    product = Column(String(50), nullable=False)
    contract = Column(String(20), nullable=False)
    price = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "key": f"{self.product}::{self.contract}",
            "product": self.product,
            "contract": self.contract,
            "price": self.price,
            "updated_at": self.updated_at.isoformat()
        }

class ExternalMarketData(Base):
    __tablename__ = "external_market_data"
    
    id = Column(String, primary_key=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    prices = Column(JSON, nullable=False)
    news_text = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            "date": self.date,
            "prices": self.prices,
            "news_text": self.news_text,
            "created_at": self.created_at.isoformat()
        }