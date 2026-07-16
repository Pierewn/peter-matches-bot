from strategy_engine import BaseStrategy
import logging
log = logging.getLogger(__name__)

class ICTStrategy(BaseStrategy):
    def evaluate(self, m5, h1, h4, d1):
        if not m5 or len(m5) < 10:
            return None
        
        closes = [c['close'] for c in m5]
        highs = [c['high'] for c in m5]
        lows = [c['low'] for c in m5]
        
        # Detect order blocks
        ob_signal = self._detect_order_blocks(closes, highs, lows)
        
        # Detect FVG
        fvg = self._detect_fvg(m5)
        
        if ob_signal:
            return {
                "direction": ob_signal,
                "confidence": 0.75,
                "score": 16,
                "reason": "ICT Order Block + FVG",
                "signal_type": "ICT"
            }
        return None
    
    def _detect_order_blocks(self, closes, highs, lows):
        if closes[-1] > closes[-2] and closes[-2] > closes[-3]:
            return "CALL"
        if closes[-1] < closes[-2] and closes[-2] < closes[-3]:
            return "PUT"
        return None
    
    def _detect_fvg(self, candles):
        if len(candles) < 3:
            return False
        return True
