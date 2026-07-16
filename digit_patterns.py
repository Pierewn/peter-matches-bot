"""
Pattern recognition for Deriv Digit Matches.
Detects sequences, Markov chains, and repeating patterns.
"""

from collections import defaultdict, deque
from typing import Dict, List, Tuple
import numpy as np


class DigitPatternEngine:
    def __init__(self, history_size: int = 500):
        self.history = deque(maxlen=history_size)
        self.transition_counts = defaultdict(lambda: defaultdict(int))
        self.sequence_patterns = defaultdict(int)
        self.update_count = 0

    def update(self, digit: int) -> None:
        """
        Add new digit and update patterns.
        """
        if self.history:
            prev_digit = self.history[-1]
            self.transition_counts[prev_digit][digit] += 1

        self.history.append(digit)
        self.update_count += 1

        if len(self.history) >= 3:
            seq = (self.history[-3], self.history[-2], self.history[-1])
            self.sequence_patterns[seq] += 1

    def get_next_digit_markov(self, current_digit: int) -> Dict[int, float]:
        """
        Markov chain: P(next_digit | current_digit)
        """
        if current_digit not in self.transition_counts:
            return {i: 0.1 for i in range(10)}

        transitions = self.transition_counts[current_digit]
        if not transitions:
            return {i: 0.1 for i in range(10)}

        total = sum(transitions.values())
        return {
            digit: (transitions.get(digit, 0) / total if total > 0 else 0.1)
            for digit in range(10)
        }

    def get_sequence_probability(self, seq: Tuple[int, int, int]) -> float:
        """
        How often does this 3-digit sequence appear?
        """
        if not self.sequence_patterns:
            return 0.0

        count = self.sequence_patterns.get(seq, 0)
        total = sum(self.sequence_patterns.values())

        return (count / total) if total > 0 else 0.0

    def detect_repeating_sequences(self, min_repetitions: int = 2) -> List[Tuple[Tuple, int, float]]:
        """
        Find sequences that repeat frequently.
        """
        if not self.sequence_patterns:
            return []

        total = sum(self.sequence_patterns.values())
        repeating = []

        for seq, count in self.sequence_patterns.items():
            if count >= min_repetitions:
                prob = count / total if total > 0 else 0
                repeating.append((seq, count, prob))

        repeating.sort(key=lambda x: x[1], reverse=True)
        return repeating[:10]

    def get_pattern_strength(self) -> float:
        """
        Overall strength of patterns (0-1). Higher = more predictable.
        """
        if len(self.history) < 50:
            return 0.0

        if not self.sequence_patterns:
            return 0.0

        total = sum(self.sequence_patterns.values())
        entropy = 0.0

        for count in self.sequence_patterns.values():
            prob = count / total
            if prob > 0:
                entropy -= prob * np.log2(prob)

        max_entropy = np.log2(min(1000, len(self.sequence_patterns)))
        if max_entropy == 0:
            return 0.0

        normalized_entropy = entropy / max_entropy
        return max(0.0, 1.0 - normalized_entropy)

    def predict_next_digit(self, recent_digits: List[int] = None) -> Tuple[int, float]:
        """
        Predict next digit based on patterns.
        Returns (predicted_digit, confidence).
        """
        if recent_digits is None:
            if len(self.history) < 1:
                return 5, 0.1
            recent_digits = list(self.history)[-3:] if len(self.history) >= 3 else list(self.history)

        if len(recent_digits) < 1:
            return 5, 0.1

        current_digit = recent_digits[-1]
        markov_probs = self.get_next_digit_markov(current_digit)
        markov_best = max(range(10), key=lambda d: markov_probs[d])
        markov_confidence = markov_probs[markov_best]

        sequence_best = None
        sequence_confidence = 0.0

        if len(recent_digits) >= 2 and len(self.history) >= 2:
            seq = (recent_digits[-3], recent_digits[-2], recent_digits[-1]) if len(recent_digits) >= 3 else (0, recent_digits[-2], recent_digits[-1])
            matching_sequences = [
                (s, c) for s, c in self.sequence_patterns.items()
                if s[1:] == (recent_digits[-2], recent_digits[-1])
            ]

            if matching_sequences:
                next_digits = defaultdict(int)
                for seq_match, count in matching_sequences:
                    next_digits[seq_match[2]] += count

                sequence_best = max(next_digits.keys(), key=lambda d: next_digits[d])
                total = sum(next_digits.values())
                sequence_confidence = next_digits[sequence_best] / total if total > 0 else 0

        if sequence_best is not None and sequence_confidence > markov_confidence:
            return sequence_best, sequence_confidence
        else:
            return markov_best, markov_confidence

    def get_pattern_report(self) -> Dict:
        """
        Comprehensive pattern analysis report.
        """
        return {
            'ticks_analyzed': len(self.history),
            'pattern_strength': self.get_pattern_strength(),
            'top_sequences': self.detect_repeating_sequences(min_repetitions=1),
            'unique_transitions': len(self.transition_counts),
            'unique_sequences': len(self.sequence_patterns),
        }
