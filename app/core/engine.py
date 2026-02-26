from typing import List, Dict, Tuple, Optional
from ..models.trade import TradeStatus, TradeType
from ..config import settings
import logging

logger = logging.getLogger(__name__)


class PositionEngine:
    """持仓计算引擎 - 从交易流水重建持仓和历史平仓。"""

    def __init__(self, fee_calculator=None, ttf_multiplier: float = 3412):
        self.fee_calculator = fee_calculator
        self.ttf_multiplier = ttf_multiplier

    def calculate_positions(
        self,
        trades: List,
        settings_dict: Optional[Dict] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """从交易流水重建持仓和历史平仓。"""
        active_trades = [t for t in trades if getattr(t, "status", None) == TradeStatus.ACTIVE]
        active_trades.sort(key=lambda x: x.date)

        temp_positions = {}
        history = []

        settings_data = settings_dict or {}
        fees = settings_data.get("fees", {})
        ttf_mult = settings_data.get("ttfMultiplier", self.ttf_multiplier)

        for trade in active_trades:
            key = f"{trade.trader}-{trade.product}-{trade.contract}"

            if key not in temp_positions:
                temp_positions[key] = {
                    "key": key,
                    "trader": trade.trader,
                    "product": trade.product,
                    "contract": trade.contract,
                    "quantity": 0.0,
                    "total_value": 0.0,
                    "last_update": trade.date,
                }

            pos = temp_positions[key]
            multiplier = self._get_contract_multiplier(trade.product, ttf_mult)

            if pos["quantity"] != 0 and (pos["quantity"] * trade.quantity) < 0:
                close_qty = min(abs(pos["quantity"]), abs(trade.quantity))
                direction = 1 if pos["quantity"] > 0 else -1
                avg_price = pos["total_value"] / pos["quantity"] if pos["quantity"] != 0 else 0

                if trade.type == TradeType.REGULAR:
                    gross = (trade.price - avg_price) * close_qty * direction * multiplier
                    fee_rate = self._get_fee_rate(trade.product, fees)
                    fee = close_qty * multiplier * 2 * fee_rate
                    net_pl = gross - fee

                    history.append(
                        {
                            "date": trade.date.isoformat(),
                            "trader": trade.trader,
                            "product": trade.product,
                            "contract": trade.contract,
                            "closed_quantity": close_qty * direction * -1,
                            "open_price": avg_price,
                            "close_price": trade.price,
                            "realized_pl": net_pl,
                            "multiplier": multiplier,
                            "fee": fee,
                        }
                    )

                    if abs(pos["quantity"]) - close_qty > 0.0001:
                        fraction = (abs(pos["quantity"]) - close_qty) / abs(pos["quantity"])
                        pos["total_value"] *= fraction
                    else:
                        pos["total_value"] = 0

                    pos["quantity"] += trade.quantity
                else:
                    pos["total_value"] += trade.quantity * trade.price
                    pos["quantity"] += trade.quantity
            else:
                pos["total_value"] += trade.quantity * trade.price
                pos["quantity"] += trade.quantity

        positions = [
            {
                "key": data["key"],
                "trader": data["trader"],
                "product": data["product"],
                "contract": data["contract"],
                "quantity": data["quantity"],
                "total_value": data["total_value"],
                "avg_price": data["total_value"] / data["quantity"] if abs(data["quantity"]) > 0.0001 else 0,
            }
            for data in temp_positions.values()
            if abs(data["quantity"]) > 0.0001
        ]

        logger.info("计算完成: %s 个持仓, %s 条历史", len(positions), len(history))
        return positions, history

    def _get_contract_multiplier(self, product: str, ttf_multiplier: float) -> float:
        base_mult = settings.CONTRACT_MULTIPLIERS.get(product, 1000)
        if product == "TTF":
            return base_mult * ttf_multiplier
        return base_mult

    def _get_fee_rate(self, product: str, fees: Dict) -> float:
        if product == "Brent":
            return fees.get("brentPerBbl", 0)
        return fees.get("hhPerMMBtu", 0)

    def calculate_floating_pnl(self, position: Dict, mtm_price: float, settings_dict: Optional[Dict] = None) -> float:
        settings_data = settings_dict or {}
        fees = settings_data.get("fees", {})
        ttf_mult = settings_data.get("ttfMultiplier", self.ttf_multiplier)

        multiplier = self._get_contract_multiplier(position["product"], ttf_mult)
        gross = (mtm_price * position["quantity"] - position["total_value"]) * multiplier
        fee_rate = self._get_fee_rate(position["product"], fees)
        unrealized_fee = abs(position["quantity"]) * multiplier * fee_rate
        return gross - unrealized_fee

    def calculate_total_floating(self, positions: List[Dict], market_prices: Dict, settings_dict: Optional[Dict] = None) -> float:
        total = 0.0
        for pos in positions:
            scoped_key = f"{pos['product']}::{pos['contract']}"
            mtm = market_prices.get(scoped_key)
            if mtm is None:
                mtm = pos["total_value"] / pos["quantity"] if pos["quantity"] != 0 else 0
            total += self.calculate_floating_pnl(pos, mtm, settings_dict)
        return total
