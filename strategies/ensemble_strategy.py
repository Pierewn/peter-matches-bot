from strategy_engine import BaseStrategy
from signal_fusion import SignalFusion
import logging
log = logging.getLogger(__name__)

class EnsembleStrategy(BaseStrategy):
    def __init__(self):
        self.fusion = SignalFusion()
    
    def evaluate(self, m5, h1, h4, d1):
        if not m5 or len(m5) < 5:
            return None
        
        closes_m5 = [c['close'] for c in m5]
        rsi = self._rsi(closes_m5, 14)
        macd_hist = self._macd(closes_m5, 12, 26, 9)
        adx = self._adx(m5, 14)
        bb_pct = self._bollinger_pct(closes_m5, 20)
        z_score = self._zscore(closes_m5, 20)
        fib_hit = self._fib_hit(m5)
        ema_aligned = self._ema_aligned(closes_m5)
        ob_signal = self._order_block_signal(m5, h1)
        
        result = self.fusion.evaluate(rsi, macd_hist, adx, bb_pct, z_score, fib_hit, ema_aligned, ob_signal)
        
        if result['direction']:
            return {
                "direction": result['direction'],
                "confidence": result['confidence'],
                "score": int(result['confidence'] * 20),
                "reason": f"Consensus: {', '.join(result['signals'][:3])}",
                "signal_type": "ENSEMBLE"
            }
        return None
    
    def _rsi(self, closes, period):
        if len(closes) < period + 1:
            return 50
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = sum(d for d in deltas if d > 0) / period
        losses = abs(sum(d for d in deltas if d < 0) / period)
        if losses == 0:
            return 100 if gains > 0 else 0
        rs = gains / losses
        return 100 - (100 / (1 + rs))
    
    def _macd(self, closes, fast=12, slow=26, signal=9):
        if len(closes) < slow:
            return 0
        ema_fast = sum(closes[-fast:]) / fast
        ema_slow = sum(closes[-slow:]) / slow
        return ema_fast - ema_slow
    
    def _adx(self, candles, period):
        if len(candles) < period:
            return 20
        return 25
    
    def _bollinger_pct(self, closes, period):
        if len(closes) < period:
            return 0.5
        sma = sum(closes[-period:]) / period
        std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        if upper == lower:
            return 0.5
        return max(0, min(1, (closes[-1] - lower) / (upper - lower)))
    
    def _zscore(self, closes, period):
        if len(closes) < period:
            return 0
        sma = sum(closes[-period:]) / period
        std = (sum((c - sma) ** 2 for c in closes[-period:]) / period) ** 0.5
        if std == 0:
            return 0
        return (closes[-1] - sma) / std
    
    def _fib_hit(self, candles):
        return False
    
    def _ema_aligned(self, closes):
        if len(closes) < 50:
            return False
        ema_fast = sum(closes[-12:]) / 12
        ema_slow = sum(closes[-26:]) / 26
        return ema_fast > ema_slow
    
    def _order_block_signal(self, m5, h1):
        return None
