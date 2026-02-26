from sqlalchemy import Column, String, Float, Integer, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Settings(Base):
    __tablename__ = "settings"
    
    id = Column(String, primary_key=True, default="default")
    fees = Column(JSON, default={"brentPerBbl": 0, "hhPerMMBtu": 0})
    exchange_rate_rmb = Column(Float, default=7.13)
    initial_realized_pl = Column(Float, default=0)
    reconciliation_base = Column(Float, default=156170)
    reconciliation_other = Column(Float, default=45800)
    ttf_multiplier = Column(Float, default=3412)
    
    def to_dict(self):
        return {
            "fees": self.fees,
            "exchangeRateRMB": self.exchange_rate_rmb,
            "initialRealizedPL": self.initial_realized_pl,
            "reconciliation": {
                "base": self.reconciliation_base,
                "other": self.reconciliation_other
            },
            "ttfMultiplier": self.ttf_multiplier
        }