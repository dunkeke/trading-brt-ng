from typing import List, Dict, Tuple, Optional
from datetime import datetime
from ..models.trade import Trade, TradeStatus, TradeType
from ..models.position import Position
from ..models.history import HistoryEntry
from ..config import settings
import logging

logger = logging.getLogger(__name__)

class PositionEngine:
    """持仓计算引擎 - 完整移植自JavaScript的rebuildStateFromLogs"""
    
    def __init__(self, fee_calculator=None, ttf_multiplier: float = 3412):
        self.fee_calculator = fee_calculator
        self.ttf_multiplier = ttf_multiplier
    
    def calculate_positions(self, 
                           trades: List[Trade], 
                           settings_dict: Optional[Dict] = None) -> Tuple[List[Dict], List[Dict]]:
        """
        从交易流水重建持仓和历史平仓
        完全对应JS的rebuildStateFromLogs()
        
        Args:
            trades: 交易列表
            settings_dict: 设置字典，包含fees, ttfMultiplier等
            
        Returns:
            (positions, history)
        """
        # 只处理active状态的交易
        active_trades = [t for t in trades if t.status == TradeStatus.ACTIVE]
        active_trades.sort(key=lambda x: x.date)
        
        # 临时持仓字典 {key: position_data}
        temp_positions = {}
        history = []
        
        # 获取设置
        settings = settings_dict or {}
        fees = settings.get('fees', {})
        ttf_mult = settings.get('ttfMultiplier', self.ttf_multiplier)
        
        for trade in active_trades:
            key = f"{trade.trader}-{trade.product}-{trade.contract}"
            
            if key not in temp_positions:
                temp_positions[key] = {
                    'key': key,
                    'trader': trade.trader,
                    'product': trade.product,
                    'contract': trade.contract,
                    'quantity': 0.0,
                    'total_value': 0.0,
                    'last_update': trade.date
                }
            
            pos = temp_positions[key]
            
            # 获取合约乘数
            multiplier = self._get_contract_multiplier(trade.product, ttf_mult)
            
            # 处理平仓逻辑 (当现有持仓与新交易方向相反)
            if pos['quantity'] != 0 and (pos['quantity'] * trade.quantity) < 0:
                # 计算可平仓数量
                close_qty = min(abs(pos['quantity']), abs(trade.quantity))
                direction = 1 if pos['quantity'] > 0 else -1
                
                # 计算开仓均价
                avg_price = pos['total_value'] / pos['quantity'] if pos['quantity'] != 0 else 0
                
                # 如果是常规交易，计算盈亏
                if trade.type == TradeType.REGULAR:
                    # 毛盈亏 (平仓价 - 开仓价) * 数量 * 方向 * 乘数
                    gross = (trade.price - avg_price) * close_qty * direction * multiplier
                    
                    # 费用计算 (双边)
                    fee_rate = self._get_fee_rate(trade.product, fees)
                    fee = close_qty * multiplier * 2 * fee_rate
                    
                    # 净盈亏
                    net_pl = gross - fee
                    
                    # 记录历史平仓
                    history.append({
                        'date': trade.date.isoformat(),
                        'trader': trade.trader,
                        'product': trade.product,
                        'contract': trade.contract,
                        'closed_quantity': close_qty * direction * -1,  # 正数为平空，负数为平多
                        'open_price': avg_price,
                        'close_price': trade.price,
                        'realized_pl': net_pl,
                        'multiplier': multiplier,
                        'fee': fee
                    })
                    
                    # 更新持仓
                    if abs(pos['quantity']) - close_qty > 0.0001:
                        # 部分平仓，按比例减少total_value
                        fraction = (abs(pos['quantity']) - close_qty) / abs(pos['quantity'])
                        pos['total_value'] *= fraction
                    else:
                        # 完全平仓，清空
                        pos['total_value'] = 0
                    
                    pos['quantity'] += trade.quantity
                    
                else:
                    # 调整类型交易，不产生盈亏，直接更新成本
                    pos['total_value'] += trade.quantity * trade.price
                    pos['quantity'] += trade.quantity
            else:
                # 开仓或同向加仓
                pos['total_value'] += trade.quantity * trade.price
                pos['quantity'] += trade.quantity
        
        # 过滤零持仓 (数量绝对值小于0.0001)
        positions = [
            {
                'key': data['key'],
                'trader': data['trader'],
                'product': data['product'],
                'contract': data['contract'],
                'quantity': data['quantity'],
                'total_value': data['total_value'],
                'avg_price': data['total_value'] / data['quantity'] if abs(data['quantity']) > 0.0001 else 0
            }
            for data in temp_positions.values()
            if abs(data['quantity']) > 0.0001
        ]
        
        logger.info(f"计算完成: {len(positions)} 个持仓, {len(history)} 条历史")
        return positions, history
    
    def _get_contract_multiplier(self, product: str, ttf_multiplier: float) -> float:
        """获取合约乘数"""
        base_mult = settings.CONTRACT_MULTIPLIERS.get(product, 1000)
        
        if product == 'TTF':
            return base_mult * ttf_multiplier
        return base_mult
    
    def _get_fee_rate(self, product: str, fees: Dict) -> float:
        """获取费率"""
        if product == 'Brent':
            return fees.get('brentPerBbl', 0)
        else:
            return fees.get('hhPerMMBtu', 0)
    
    def calculate_floating_pnl(self, 
                              position: Dict, 
                              mtm_price: float,
                              settings_dict: Optional[Dict] = None) -> float:
        """
        计算单个持仓的浮动盈亏
        对应JS中的浮动盈亏计算逻辑
        """
        settings = settings_dict or {}
        fees = settings.get('fees', {})
        ttf_mult = settings.get('ttfMultiplier', self.ttf_multiplier)
        
        multiplier = self._get_contract_multiplier(position['product'], ttf_mult)
        
        # 毛浮动盈亏 (MTM * 数量 - 成本) * 乘数
        gross = (mtm_price * position['quantity'] - position['total_value']) * multiplier
        
        # 未实现费用 (持仓部分)
        fee_rate = self._get_fee_rate(position['product'], fees)
        unrealized_fee = abs(position['quantity']) * multiplier * fee_rate
        
        # 净浮动盈亏
        net = gross - unrealized_fee
        
        return net
    
    def calculate_total_floating(self, 
                                positions: List[Dict],
                                market_prices: Dict,
                                settings_dict: Optional[Dict] = None) -> float:
        """
        计算总浮动盈亏
        """
        total = 0.0
        for pos in positions:
            # 获取MTM价格
            scoped_key = f"{pos['product']}::{pos['contract']}"
            mtm = market_prices.get(scoped_key)
            
            if mtm is None:
                # 如果没有MTM，使用持仓均价
                mtm = pos['total_value'] / pos['quantity'] if pos['quantity'] != 0 else 0
            
            total += self.calculate_floating_pnl(pos, mtm, settings_dict)
        
        return total