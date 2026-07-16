"""
Digit Matches trading strategy.
Uses digit frequency analysis + pattern recognition + confidence scoring.
"""

import sys
sys.path.insert(0, '.')

from digit_confidence import DigitConfidenceScorer, ConfidenceScore


class DigitMatchStrategy:
    def __init__(self, initial_stake: float = 1.0, max_stake: float = 8.0,
                 target_profit: float = 100.0, stop_loss: float = -50.0,
                 max_consecutive_losses: int = 3):
        self.scorer = DigitConfidenceScorer(
            high_confidence_threshold=0.65,
            low_confidence_threshold=0.35
        )

        # Martingale escalation config (from Block Builder bot)
        self.initial_stake = initial_stake
        self.current_stake = initial_stake
        self.max_stake = max_stake
        self.consecutive_losses = 0
        self.max_consecutive_losses = max_consecutive_losses

        # Profit tracking
        self.total_profit = 0.0
        self.target_profit = target_profit
        self.stop_loss = stop_loss

        # Trade history
        self.trades_executed = 0
        self.trades_won = 0
        self.last_prediction = None

    def analyze_tick(self, tick_price: float) -> ConfidenceScore:
        """
        Analyze new tick and generate prediction.
        """
        self.scorer.update_tick(tick_price)
        confidence = self.scorer.calculate_confidence()
        self.last_prediction = confidence
        return confidence

    def should_trade(self, confidence: ConfidenceScore) -> bool:
        """
        Determine if we should execute a trade.
        """
        return confidence.recommendation in ["DIGITMATCH", "DIGITDIFF"]

    def get_trade_details(self, confidence: ConfidenceScore) -> dict:
        """
        Return trade parameters for executor.
        """
        if not self.should_trade(confidence):
            return None

        return {
            'contract_type': confidence.recommendation,
            'barrier': str(confidence.predicted_digit),
            'amount': self.calculate_stake(confidence),
            'symbol': 'R_75',
            'duration': 5,
            'duration_unit': 't',
            'confidence': confidence.confidence,
            'predicted_digit': confidence.predicted_digit,
        }

    def calculate_stake(self, confidence: ConfidenceScore) -> float:
        """
        Martingale escalation (from Block Builder "Dollar Printer PRO v2").
        - Start at initial_stake ($1)
        - After LOSS: escalate stake (up to max_stake $8)
        - After WIN: reset to initial_stake
        - Payout: 8.93x, so winning trade recovers all losses + profit
        """
        if confidence.recommendation == "SKIP":
            return 0.0

        # Return current stake (already escalated if needed)
        return self.current_stake

    def escalate_stake_after_loss(self) -> None:
        """
        Martingale escalation: double the stake (capped at max_stake).
        With 8.93x payout, doubling recovers previous loss + profit.
        """
        self.current_stake = min(self.current_stake * 2.0, self.max_stake)

    def reset_stake_after_win(self) -> None:
        """
        Reset to initial stake after a win (Martingale reset).
        """
        self.current_stake = self.initial_stake

    def record_outcome(self, predicted_digit: int, won: bool, pnl: float = None) -> None:
        """
        Record trade result and update martingale state.
        pnl: profit/loss from the trade (used for total_profit tracking)
        """
        self.scorer.record_trade_result(predicted_digit, won)
        self.trades_executed += 1

        if won:
            self.trades_won += 1
            # Winning trade: reset stake to initial
            self.reset_stake_after_win()
            self.consecutive_losses = 0
            # Add profit (payout - stake)
            if pnl is not None:
                self.total_profit += pnl
            else:
                # Payout = stake * 8.93, Profit = Payout - Stake = (8.93 - 1) * stake
                self.total_profit += self.current_stake * 7.93
        else:
            # Losing trade: escalate stake
            self.consecutive_losses += 1
            self.escalate_stake_after_loss()
            # Subtract loss
            if pnl is not None:
                self.total_profit += pnl  # pnl is already negative
            else:
                self.total_profit -= self.current_stake

    def should_continue_trading(self) -> tuple:
        """
        Check if trading should continue based on Block Builder logic.
        Returns (should_continue: bool, reason: str)
        """
        # Check target profit
        if self.total_profit >= self.target_profit:
            return False, f"Target profit reached: ${self.total_profit:.2f} >= ${self.target_profit:.2f}"

        # Check stop loss
        if self.total_profit <= self.stop_loss:
            return False, f"Stop loss hit: ${self.total_profit:.2f} <= ${self.stop_loss:.2f}"

        # Check max consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, f"Max consecutive losses: {self.consecutive_losses} >= {self.max_consecutive_losses}"

        return True, "Continue trading"

    def get_win_rate(self) -> float:
        """
        Historical win rate.
        """
        if self.trades_executed == 0:
            return 0.0
        return self.trades_won / self.trades_executed

    def get_report(self) -> dict:
        """
        Strategy performance and analysis report (includes martingale state).
        """
        should_continue, reason = self.should_continue_trading()

        return {
            # Trade history
            'trades_executed': self.trades_executed,
            'trades_won': self.trades_won,
            'win_rate': self.get_win_rate(),

            # Martingale state
            'current_stake': self.current_stake,
            'max_stake': self.max_stake,
            'consecutive_losses': self.consecutive_losses,
            'total_profit': self.total_profit,
            'target_profit': self.target_profit,
            'stop_loss': self.stop_loss,

            # Exit status
            'should_continue': should_continue,
            'exit_reason': reason,

            # Analysis
            'analysis': self.scorer.get_analysis_report(),
            'last_prediction': self.last_prediction,
        }
