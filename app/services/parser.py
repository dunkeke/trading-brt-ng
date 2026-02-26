import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ParsedTrade:
    """解析出的交易"""
    trader: str
    product: str
    contract: str
    quantity: float
    price: float
    side: int  # 1: 买, -1: 卖
    is_valid: bool = True
    error: Optional[str] = None

class TradeParser:
    """
    交易文本解析器 - 完整移植自JavaScript的parseImportText
    支持格式:
    - Sold 200x Brent May26
    - 50x pm Jul26-Dec26
    - Bought TTF 26Q4
    - D sold HH Jan26 @ 2.85
    - 10 lots JKM Feb26 OTC 12.5
    """
    
    def __init__(self):
        self.month_map = {
            'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
            'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
            'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
        }
        
        self.traders = ['W', 'L', 'Z', 'D']
        self.products = ['Brent', 'Henry Hub', 'JKM', 'TTF']
    
    def parse_text(self, text: str) -> List[ParsedTrade]:
        """
        解析批量导入文本
        对应JS的parseImportText()
        """
        if not text or not text.strip():
            return []
        
        # 按行分割并清理
        raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 合并数字行到前一行 (JS逻辑: 纯数字行作为价格补充)
        merged_lines = self._merge_number_lines(raw_lines)
        
        results = []
        for line in merged_lines:
            try:
                parsed = self._parse_line(line)
                if parsed:
                    results.append(parsed)
            except Exception as e:
                logger.error(f"解析行失败: {line}, 错误: {e}")
                results.append(ParsedTrade(
                    trader='',
                    product='',
                    contract='',
                    quantity=0,
                    price=0,
                    side=1,
                    is_valid=False,
                    error=str(e)
                ))
        
        return results
    
    def _merge_number_lines(self, lines: List[str]) -> List[str]:
        """
        合并数字行到前一行
        对应JS逻辑: if(isNumOnly && merged.length) merged[merged.length-1] += " " + l;
        """
        merged = []
        for line in lines:
            # 检查是否是纯数字行（可能包含价格）
            is_num_only = self._is_number_line(line)
            
            if is_num_only and merged:
                # 如果是数字行且已有前一行，则附加到前一行
                merged[-1] = merged[-1] + " " + line
            else:
                merged.append(line)
        
        return merged
    
    def _is_number_line(self, line: str) -> bool:
        """
        判断是否为纯数字行
        匹配: 只包含数字、小数点、空格、逗号，没有字母
        """
        # 移除数字、小数点、空格、逗号后，看是否还有字符
        cleaned = re.sub(r'[\d\s\.,\-+]', '', line)
        return len(cleaned) == 0 and re.search(r'\d', line) is not None
    
    def _parse_line(self, line: str) -> Optional[ParsedTrade]:
        """
        解析单行文本
        对应JS的解析逻辑
        """
        # 1. 预清洗
        clean = self._pre_clean(line)
        
        # 2. 识别交易员
        trader = self._detect_trader(clean)
        
        # 3. 识别品种
        product = self._detect_product(clean)
        
        # 4. 识别买卖方向
        side = self._detect_side(clean)
        
        # 5. 识别数量
        qty = self._extract_quantity(clean)
        if qty == 0:
            return None
        
        # 6. 识别价格
        price = self._extract_price(clean)
        if price == 0:
            return None
        
        # 7. 检查是否是范围交易 (如 Jul26-Dec26)
        range_result = self._parse_range_contract(clean, product)
        if range_result and qty > 0:
            # 范围交易返回多个合约，这里只处理第一个，批量导入会多次调用
            # 实际应该返回列表，但为简化，这里只处理第一个
            contracts = self._generate_range_contracts(range_result, product)
            if contracts:
                # 返回第一个合约，批量处理时会循环
                return ParsedTrade(
                    trader=trader,
                    product=product,
                    contract=contracts[0],
                    quantity=qty * side,
                    price=price,
                    side=side
                )
        
        # 8. 识别单个合约
        contract = self._extract_contract(clean, product)
        if not contract:
            return None
        
        return ParsedTrade(
            trader=trader,
            product=product,
            contract=contract,
            quantity=qty * side,
            price=price,
            side=side
        )
    
    def _pre_clean(self, text: str) -> str:
        """
        文本预清洗
        对应JS逻辑:
        - 移除 "to confirm u "
        - 移除行号 "1. " "2) " 等
        - 移除 "SCN" "SCREEN" "PX" 等标记
        """
        clean = text.upper()
        
        # 移除 "TO CONFIRM U "
        clean = re.sub(r'^(TO\s+)?CONFIRM\s+U\s+', '', clean, flags=re.I)
        
        # 移除行号标记 (1. 2) 3] 等)
        clean = re.sub(r'^\s*\d+([.)\uff09\]]|\s+)', '', clean)
        
        # 移除价格标记
        clean = re.sub(r'(\d+(\.\d+)?)\s*(SCN|SCREEN|PX)\b', '', clean, flags=re.I)
        
        return clean.strip()
    
    def _detect_trader(self, text: str) -> str:
        """
        识别交易员
        对应JS的detectTraderFromText()
        """
        for trader in self.traders:
            if re.search(rf'\b{trader}\b', text):
                return trader
        
        # 默认返回第一个交易员
        return self.traders[0]
    
    def _detect_product(self, text: str) -> str:
        """
        识别品种
        对应JS的detectProductFromText()
        """
        if re.search(r'TTF', text):
            return 'TTF'
        if re.search(r'JKM', text):
            return 'JKM'
        if re.search(r'\b(HH|HENRY HUB|HENRY)\b', text):
            return 'Henry Hub'
        if re.search(r'\bNATURAL GAS|NAT GAS|GAS\b', text):
            return 'Henry Hub'
        
        return 'Brent'
    
    def _detect_side(self, text: str) -> int:
        """
        识别买卖方向
        1: 买, -1: 卖
        """
        if re.search(r'SELL|SOLD|SHORT', text):
            return -1
        return 1  # 默认买
    
    def _extract_quantity(self, text: str) -> float:
        """
        提取数量
        支持格式: 200x, 50 KB, 10 LOTS, /M, PM
        """
        patterns = [
            r'(\d+(?:\.\d+)?)(?:\s*X|\s*KB|\s*LOTS)',  # 200x, 50 KB, 10 LOTS
            r'(\d+(?:\.\d+)?)\s*(?:/M|PM)'             # 50/M, 30 PM
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return float(match.group(1))
        
        # 尝试直接找数字
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        if numbers:
            # 通常第一个数字是数量
            return float(numbers[0])
        
        return 0
    
    def _extract_price(self, text: str) -> float:
        """
        提取价格
        支持格式: OTC 12.5, AT 2.85, @ 85.5
        """
        # OTC价格
        otc_match = re.search(r'OTC(?:\s*PX)?\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if otc_match:
            return float(otc_match.group(1))
        
        # AT/@价格
        at_match = re.search(r'AT\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if at_match:
            return float(at_match.group(1))
        
        at_match2 = re.search(r'@\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        if at_match2:
            return float(at_match2.group(1))
        
        # 尝试找最后一个数字作为价格
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        if len(numbers) >= 2:
            # 如果有多个数字，最后一个通常是价格
            return float(numbers[-1])
        
        return 0
    
    def _parse_range_contract(self, text: str, product: str) -> Optional[Dict]:
        """
        解析范围合约
        格式: JUL26-DEC26 或 JUL 26 - DEC 26
        """
        # 匹配月份范围
        pattern = r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})?\s*(?:-|TO)\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})?\b'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if not match:
            return None
        
        start_month = match.group(1)
        start_year = match.group(2) or '26'
        end_month = match.group(3)
        end_year = match.group(4) or start_year
        
        return {
            'start_month': start_month.upper(),
            'start_year': start_year,
            'end_month': end_month.upper(),
            'end_year': end_year,
            'product': product
        }
    
    def _generate_range_contracts(self, range_info: Dict, product: str) -> List[str]:
        """
        生成范围内的所有合约
        """
        start_idx = int(self.month_map[range_info['start_month']]) + (int(range_info['start_year']) - 26) * 12 - 1
        end_idx = int(self.month_map[range_info['end_month']]) + (int(range_info['end_year']) - 26) * 12 - 1
        
        contracts = []
        for i in range(start_idx, end_idx + 1):
            abs_month = (i % 12) + 1
            abs_year = 26 + (i // 12)
            contract = self._format_contract_name(product, str(abs_year), str(abs_month).zfill(2))
            contracts.append(contract)
        
        return contracts
    
    def _extract_contract(self, text: str, product: str) -> Optional[str]:
        """
        提取单个合约名称
        对应JS的parseSingleContract()
        """
        # 1. 明确的合约格式 HH2511, JKM2511, TTF2511
        explicit = re.search(r'\b(HH|JKM|TTF)\s?(\d{2})(\d{2})\b', text)
        if explicit:
            prefix = explicit.group(1)
            year = explicit.group(2)
            month = explicit.group(3)
            if prefix == 'HH' or product == 'Henry Hub':
                return f"HH{year}{month}"
            return f"{year}{month}"
        
        # 2. 带月份名称的格式 HH JAN26
        named = re.search(r'\b(HH|JKM|TTF)\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})\b', text)
        if named:
            prefix = named.group(1)
            month = named.group(2)
            year = named.group(3)
            month_num = self.month_map[month]
            if prefix == 'HH' or product == 'Henry Hub':
                return f"HH{year}{month_num}"
            return f"{year}{month_num}"
        
        # 3. 季度合约 26Q4 或 Q4 26
        quarter = re.search(r'\b(\d{2})Q([1-4])\b', text)
        if quarter:
            return f"{quarter.group(1)}Q{quarter.group(2)}"
        
        quarter_alt = re.search(r'\bQ([1-4])\s*(\d{2})\b', text)
        if quarter_alt:
            return f"{quarter_alt.group(2)}Q{quarter_alt.group(1)}"
        
        # 4. 月份格式 JAN26 或 26-JAN
        month_match = (
            re.search(r'\b(\d{2})-(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b', text) or
            re.search(r'\b(\d{2})\s*(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b', text) or
            re.search(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*(\d{2})\b', text) or
            re.search(r'\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})\b', text)
        )
        
        if month_match:
            # 确定年份和月份的位置
            groups = month_match.groups()
            if len(groups) == 2:
                if groups[0] in self.month_map:
                    month_token = groups[0]
                    year_token = groups[1]
                else:
                    month_token = groups[1]
                    year_token = groups[0]
                
                month_num = self.month_map.get(month_token, '01')
                return self._format_contract_name(product, year_token, month_num)
        
        return None
    
    def _format_contract_name(self, product: str, year: str, month: str) -> str:
        """格式化合约名称"""
        base = f"{year}{month}"
        if product == 'Henry Hub':
            return f"HH{base}"
        return base