from typing import Dict, Optional

class FeeCalculator:
    """费用计算器"""
    
    @staticmethod
    def calculate_trade_fee(product: str, 
                           quantity: float, 
                           price: float,
                           multiplier: float,
                           fee_rate: float) -> float:
        """
        计算单笔交易费用
        """
        return abs(quantity) * multiplier * fee_rate
    
    @staticmethod
    def calculate_round_trip_fee(product: str,
                                 quantity: float,
                                 multiplier: float,
                                 fee_rate: float) -> float:
        """
        计算双边交易费用
        """
        return abs(quantity) * multiplier * 2 * fee_rate
    
    @staticmethod
    def get_landed_cost(product: str,
                       avg_price: float,
                       exchange_rate: float = 7.13) -> float:
        """
        计算到岸价 (元/吉焦)
        对应JS中的landed计算逻辑
        """
        if product == 'Brent':
            # Brent: (avg * 0.134 + 0.46) * rmb / 28.3
            return (avg_price * 0.134 + 0.46) * exchange_rate / 28.3
        elif product == 'Henry Hub':
            # Henry Hub: (avg * 1.15 + 4.5) * rmb / 28.3
            return (avg_price * 1.15 + 4.5) * exchange_rate / 28.3
        else:
            return 0.0