from strategy_engine import BaseStrategy
import logging
log = logging.getLogger(__name__)

class MeanReversionStrategy(BaseStrategy):
    def evaluate(self, m5, h1, h4, d1):
        if not m5 or len(m5) < 20:
            return None
        
        closes = [c['close'] for c in m5]
        sma = sum(closes[-20:]) / 20
        std = (sum((c - sma) ** 2 for c in closes[-20:]) / 20) ** 0.5
        
        if std == 0:
            return None
        
        z_score = (closes[-1] - sma) / std
        
        if z_score < -2.0:
            return {
                "direction": "CALL",
                "confidence": 0.70,
                "score": 14,
                "reason": f"Mean reversion: z-score {z_score:.2f}",
                "signal_type": "MEAN_REVERSION"
            }
        
        if z_score > 2.0:
            return {
                "direction": "PUT",
                "confidence": 0.70,
                "score": 14,
                "reason": f"Mean reversion: z-score {z_score:.2f}",
                "signal_type": "MEAN_REVERSION"
            }
        
        return None
