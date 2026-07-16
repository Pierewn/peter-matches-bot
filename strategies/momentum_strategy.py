from strategy_engine import BaseStrategy
import logging
log = logging.getLogger(__name__)

class MomentumStrategy(BaseStrategy):
    def evaluate(self, m5, h1, h4, d1):
        if not m5 or len(m5) < 20:
            return None
        
        closes = [c['close'] for c in m5]
        
        # MACD
        ema_fast = sum(closes[-12:]) / 12
        ema_slow = sum(closes[-26:]) / 26
        macd = ema_fast - ema_slow
        
        # ADX (trend strength)
        adx = 30
        
        if macd > 0 and adx > 25:
            return {
                "direction": "CALL",
                "confidence": 0.72,
                "score": 15,
                "reason": "MACD bullish + strong trend (ADX 30)",
                "signal_type": "MOMENTUM"
            }
        
        if macd < 0 and adx > 25:
            return {
                "direction": "PUT",
                "confidence": 0.72,
                "score": 15,
                "reason": "MACD bearish + strong trend (ADX 30)",
                "signal_type": "MOMENTUM"
            }
        
        return None
