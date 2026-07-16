"""
Multi-factor confidence scoring for Digit Matches predictions.
Combines frequency analysis, patterns, volatility, and recent performance.
"""

from dataclasses import dataclass
from typing import Dict, Tuple
from digit_analyzer import DigitAnalyzer
from digit_patterns import DigitPatternEngine


@dataclass
class ConfidenceScore:
    predicted_digit: int
    confidence: float
    frequency_score: float
    pattern_score: float
    volatility_adjustment: float
    recommendation: str


class DigitConfidenceScorer:
    def __init__(self, high_confidence_threshold: float = 0.65, low_confidence_threshold: float = 0.35):
        self.analyzer = DigitAnalyzer(max_history=500)
        self.pattern_engine = DigitPatternEngine(history_size=500)

        self.high_threshold = high_confidence_threshold
        self.low_threshold = low_confidence_threshold

        self.digit_win_rate = {i: 0.5 for i in range(10)}
        self.digit_trades = {i: 0 for i in range(10)}
        self.update_count = 0

    def update_tick(self, tick_price: float) -> None:
        """
        Process new tick.
        """
        self.analyzer.update(tick_price)
        last_digit = int(str(tick_price).split('.')[-1][-1]) % 10
        self.pattern_engine.update(last_digit)
        self.update_count += 1

    def record_trade_result(self, predicted_digit: int, won: bool) -> None:
        """
        Learn from trade outcomes.
        """
        self.digit_trades[predicted_digit] += 1
        if won:
            self.digit_win_rate[predicted_digit] = (
                (self.digit_win_rate[predicted_digit] * (self.digit_trades[predicted_digit] - 1) + 1)
                / self.digit_trades[predicted_digit]
            )
        else:
            self.digit_win_rate[predicted_digit] = (
                (self.digit_win_rate[predicted_digit] * (self.digit_trades[predicted_digit] - 1) + 0)
                / self.digit_trades[predicted_digit]
            )

    def get_frequency_score(self) -> Tuple[int, float]:
        """
        Score based on GreenBar dominance and trend.
        Returns (greenbar_digit, frequency_score).
        """
        greenbar, redbar, gb_freq, rb_freq = self.analyzer.get_greenbar_redbar()
        trend = self.analyzer.get_greenbar_trend()

        frequency_dominance = gb_freq - (1.0 / 10)
        max_dominance = 0.9

        base_score = frequency_dominance / max_dominance
        base_score = max(0.0, min(1.0, base_score))

        trend_boost = (trend + 1.0) / 2.0 * 0.2

        final_score = min(1.0, base_score + trend_boost)

        return greenbar, final_score

    def get_pattern_score(self) -> Tuple[int, float]:
        """
        Score based on pattern recognition.
        Returns (predicted_digit, pattern_score).
        """
        predicted_digit, markov_confidence = self.pattern_engine.predict_next_digit()
        pattern_strength = self.pattern_engine.get_pattern_strength()

        pattern_score = (markov_confidence + pattern_strength) / 2.0

        return predicted_digit, pattern_score

    def get_volatility_adjustment(self) -> float:
        """
        Adjust confidence based on market volatility.
        High volatility = less predictable = lower confidence.
        """
        stats = self.analyzer.get_digit_stats()

        freqs = [stats[d].avg_frequency for d in range(10)]
        mean_freq = sum(freqs) / len(freqs)
        variance = sum((f - mean_freq) ** 2 for f in freqs) / len(freqs)
        std_dev = variance ** 0.5

        if mean_freq == 0:
            return 0.8

        coeff_variation = std_dev / mean_freq
        adjustment = min(1.0, max(0.5, coeff_variation))

        return adjustment

    def calculate_confidence(self) -> ConfidenceScore:
        """
        Multi-factor confidence scoring.
        """
        health = self.analyzer.get_health_check()
        if not health['window_100_full']:
            return ConfidenceScore(
                predicted_digit=5,
                confidence=0.1,
                frequency_score=0.0,
                pattern_score=0.0,
                volatility_adjustment=1.0,
                recommendation="SKIP"
            )

        greenbar, freq_score = self.get_frequency_score()
        pattern_digit, pattern_score = self.get_pattern_score()
        vol_adjustment = self.get_volatility_adjustment()

        if freq_score > pattern_score:
            predicted = greenbar
            primary_score = freq_score
        else:
            predicted = pattern_digit
            primary_score = pattern_score

        combined_score = primary_score * vol_adjustment

        if self.digit_trades[predicted] > 5:
            historical_confidence = self.digit_win_rate[predicted]
            combined_score = (combined_score * 0.7) + (historical_confidence * 0.3)

        combined_score = max(0.0, min(1.0, combined_score))

        # Always use DIGITMATCH (8.93x payout) when confidence is decent
        # Never use DIGITDIFF (lower payout)
        if combined_score >= self.low_threshold:
            recommendation = "DIGITMATCH"
        else:
            recommendation = "SKIP"

        return ConfidenceScore(
            predicted_digit=predicted,
            confidence=combined_score,
            frequency_score=freq_score,
            pattern_score=pattern_score,
            volatility_adjustment=vol_adjustment,
            recommendation=recommendation
        )

    def get_analysis_report(self) -> Dict:
        """
        Comprehensive analysis report.
        """
        confidence = self.calculate_confidence()

        return {
            'updates': self.update_count,
            'prediction': confidence.predicted_digit,
            'confidence': round(confidence.confidence, 3),
            'recommendation': confidence.recommendation,
            'frequency_score': round(confidence.frequency_score, 3),
            'pattern_score': round(confidence.pattern_score, 3),
            'volatility_adjustment': round(confidence.volatility_adjustment, 3),
            'analyzer_health': self.analyzer.get_health_check(),
            'pattern_health': self.pattern_engine.get_pattern_report(),
        }
