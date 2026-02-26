import os
from pydantic_settings import BaseSettings
from typing import Dict, List

class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "sqlite:///./trade_analytics.db"
    
    # 合约配置
    CONTRACT_MULTIPLIERS: Dict[str, int] = {
        "Brent": 1000,
        "Henry Hub": 10000,
        "JKM": 10000,
        "TTF": 10000  # 基础乘数，实际需要乘以ttf_multiplier
    }
    
    # 默认合约列表
    CONTRACTS: Dict[str, List[str]] = {
        "Brent": ['2602','2603','2604','2605','2606','2607','2608','2609','2610','2611','2612','2701','2702','2703','26Q4','27Q1'],
        "Henry Hub": ['HH2511','HH2512','HH2601','HH2607'],
        "JKM": ['2602','2603','2604','2605','2606','2607','2608','2609','2610','2611','2612','2701','2702','2703','26Q4','27Q1'],
        "TTF": ['2602','2603','2604','2605','2606','2607','2608','2609','2610','2611','2612','2701','2702','2703','26Q4','27Q1']
    }
    
    # 交易员列表
    TRADERS: List[str] = ['W', 'L', 'Z', 'D']
    
    # 品种颜色
    COLORS: Dict[str, str] = {
        'Brent': 'badge-brent',
        'Henry Hub': 'badge-hh',
        'JKM': 'badge-jkm',
        'TTF': 'badge-ttf'
    }
    
    # 默认设置
    DEFAULT_SETTINGS: Dict = {
        "fees": {
            "brentPerBbl": 0,
            "hhPerMMBtu": 0
        },
        "exchangeRateRMB": 7.13,
        "initialRealizedPL": 0,
        "reconciliation": {
            "base": 156170,
            "other": 45800
        },
        "ttfMultiplier": 3412
    }
    
    class Config:
        env_file = ".env"

settings = Settings()