"""
Real-time digit frequency analysis for Deriv Digit Matches.
Tracks last digit probabilities across multiple time windows.
"""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Tuple
import time


@dataclass
class DigitStats:
    digit: int
    frequency_50: float
    frequency_100: float
    frequency_200: float
    avg_frequency: float
    is_greenbar: bool
    is_redbar: bool
    overdue_ticks: int
    trend_momentum: float


class DigitAnalyzer:
    def __init__(self, max_history: int = 500):
        self.max_history = max_history
        self.tick_history = deque(maxlen=max_history)
        self.last_digit_history = deque(maxlen=max_history)

        self.windows = {
            50: deque(maxlen=50),
            100: deque(maxlen=100),
            200: deque(maxlen=200),
            500: deque(maxlen=500),
        }

        self.digit_first_seen = {}
        self.update_count = 0

    def update(self, tick_price: float) -> None:
        """
        Process new tick and extract last digit.
        """
        self.tick_history.append(tick_price)
        last_digit = int(str(tick_price).split('.')[-1][-1]) % 10
        self.last_digit_history.append(last_digit)

        for window in self.windows.values():
            window.append(last_digit)

        self.update_count += 1

    def get_frequency_distribution(self, window_size: int = 100) -> Dict[int, float]:
        """
        Get probability distribution for digits in specified window.
        """
        if window_size not in self.windows:
            window_size = 100

        window = self.windows[window_size]
        if not window:
            return {i: 0.1 for i in range(10)}

        counts = defaultdict(int)
        for digit in window:
            counts[digit] += 1

        return {
            digit: counts[digit] / len(window)
            for digit in range(10)
        }

    def get_greenbar_redbar(self) -> Tuple[int, int, float, float]:
        """
        Returns (greenbar_digit, redbar_digit, greenbar_freq, redbar_freq)
        """
        freq = self.get_frequency_distribution(window_size=100)
        greenbar = max(range(10), key=lambda d: freq[d])
        redbar = min(range(10), key=lambda d: freq[d])

        return greenbar, redbar, freq[greenbar], freq[redbar]

    def get_greenbar_trend(self, window: int = 100) -> float:
        """
        Calculate GreenBar trend momentum (-1 to 1).
        Positive = GreenBar getting stronger
        Negative = GreenBar getting weaker
        """
        if len(self.last_digit_history) < window:
            return 0.0

        recent_50 = list(self.windows[50])
        if len(recent_50) < 25:
            return 0.0

        greenbar_50, _, freq_50, _ = self.get_greenbar_redbar()

        # Check frequency in older part (50-100 range)
        older_slice = list(self.last_digit_history)[-100:-50]
        if older_slice:
            older_freq = sum(1 for d in older_slice if d == greenbar_50) / len(older_slice)
            trend = freq_50 - older_freq
            return max(-1.0, min(1.0, trend * 2))  # Normalize to [-1, 1]

        return 0.0

    def get_overdue_digits(self) -> Dict[int, int]:
        """
        For each digit, how many ticks since it last appeared.
        High = overdue (might be due to appear).
        """
        if not self.last_digit_history:
            return {i: 0 for i in range(10)}

        overdue = {}
        current_idx = len(self.last_digit_history) - 1

        for digit in range(10):
            # Find last occurrence
            last_idx = -1
            for i in range(current_idx, -1, -1):
                if self.last_digit_history[i] == digit:
                    last_idx = i
                    break

            if last_idx == -1:
                overdue[digit] = current_idx + 1
            else:
                overdue[digit] = current_idx - last_idx

        return overdue

    def get_digit_stats(self) -> Dict[int, DigitStats]:
        """
        Comprehensive stats for all digits.
        """
        greenbar, redbar, gb_freq, rb_freq = self.get_greenbar_redbar()
        trend = self.get_greenbar_trend()
        overdue = self.get_overdue_digits()

        freq_50 = self.get_frequency_distribution(50)
        freq_100 = self.get_frequency_distribution(100)
        freq_200 = self.get_frequency_distribution(200)

        stats = {}
        for digit in range(10):
            avg_freq = (freq_50[digit] + freq_100[digit] + freq_200[digit]) / 3

            stats[digit] = DigitStats(
                digit=digit,
                frequency_50=freq_50[digit],
                frequency_100=freq_100[digit],
                frequency_200=freq_200[digit],
                avg_frequency=avg_freq,
                is_greenbar=(digit == greenbar),
                is_redbar=(digit == redbar),
                overdue_ticks=overdue[digit],
                trend_momentum=trend if digit == greenbar else 0.0
            )

        return stats

    def get_health_check(self) -> Dict[str, any]:
        """
        Status of analyzer.
        """
        return {
            'ticks_collected': len(self.last_digit_history),
            'updates_processed': self.update_count,
            'window_50_full': len(self.windows[50]) == 50,
            'window_100_full': len(self.windows[100]) == 100,
            'window_200_full': len(self.windows[200]) == 200,
        }
