from sqlalchemy import Column, String, Float, DateTime, Enum, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum
import uuid

Base = declarative_base()

class TradeStatus(str, enum.Enum):
    ACTIVE = "active"
    REVERSED = "reversed"

class TradeType(str, enum.Enum):
    REGULAR = "regular"
    ADJUSTMENT = "adjustment"

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    trader = Column(String(10), nullable=False)
    product = Column(String(50), nullable=False)
    contract = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.ACTIVE)
    type = Column(Enum(TradeType), default=TradeType.REGULAR)
    
    def to_dict(self):
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "trader": self.trader,
            "product": self.product,
            "contract": self.contract,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "type": self.type.value
        }