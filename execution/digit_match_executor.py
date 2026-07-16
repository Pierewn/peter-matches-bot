"""
Executor for Deriv Digit Matches/Differs contracts.
Handles proposal, buying, and monitoring of digit contracts.
"""

from typing import Dict, Optional, Tuple


class DigitMatchExecutor:
    def __init__(self, api_client, contract_type: str = "DIGITMATCH"):
        """
        Initialize executor.
        contract_type: "DIGITMATCH" or "DIGITDIFF"
        """
        self.api = api_client
        self.contract_type = contract_type
        self.active_contracts = {}
        self.contract_history = []

    def get_proposal(
        self,
        symbol: str,
        barrier: str,
        amount: float,
        duration: int = 5,
        duration_unit: str = 't'
    ) -> Optional[Dict]:
        """
        Request contract proposal from Deriv API.
        barrier: digit 0-9 as string
        """
        try:
            proposal_request = {
                "proposal": 1,
                "subscribe": 1,
                "contract_type": self.contract_type,
                "currency": "USD",
                "symbol": symbol,
                "duration": duration,
                "duration_unit": duration_unit,
                "barrier": barrier,
                "amount": amount,
            }

            response = self.api.send(proposal_request)

            if response.get("error"):
                print(f"Proposal error: {response['error']}")
                return None

            return response.get("proposal")

        except Exception as e:
            print(f"Proposal exception: {e}")
            return None

    def buy_contract(
        self,
        symbol: str,
        barrier: str,
        amount: float,
        duration: int = 5,
        duration_unit: str = 't',
        contract_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Buy a digit match contract.
        """
        try:
            proposal = self.get_proposal(symbol, barrier, amount, duration, duration_unit)
            if not proposal:
                return None

            proposal_id = proposal.get("id")

            buy_request = {
                "buy": proposal_id,
                "price": proposal.get("ask_price"),
            }

            response = self.api.send(buy_request)

            if response.get("error"):
                print(f"Buy error: {response['error']}")
                return None

            result = response.get("buy")
            if result:
                contract_id = result.get("contract_id")
                self.active_contracts[contract_id] = {
                    'symbol': symbol,
                    'contract_type': self.contract_type,
                    'barrier': barrier,
                    'amount': amount,
                    'payout': result.get("payout"),
                    'stake': result.get("buy_price"),
                    'status': 'open',
                }

            return result

        except Exception as e:
            print(f"Buy exception: {e}")
            return None

    def check_contract_status(self, contract_id: str) -> Optional[Dict]:
        """
        Check status and outcome of contract.
        """
        try:
            status_request = {
                "proposal_open_contract": 1,
                "contract_id": contract_id,
            }

            response = self.api.send(status_request)

            if response.get("error"):
                return None

            contract = response.get("proposal_open_contract")
            if contract:
                self.active_contracts[contract_id]['status'] = contract.get("status")
                if contract.get("status") == "closed":
                    self.active_contracts[contract_id]['result'] = {
                        'profit_loss': contract.get("profit"),
                        'is_win': contract.get("profit", 0) > 0,
                    }

            return contract

        except Exception as e:
            print(f"Status check exception: {e}")
            return None

    def close_contract(self, contract_id: str) -> Optional[Dict]:
        """
        Close contract early.
        """
        try:
            close_request = {
                "sell": contract_id,
            }

            response = self.api.send(close_request)

            if response.get("error"):
                print(f"Close error: {response['error']}")
                return None

            result = response.get("sell")
            if result and contract_id in self.active_contracts:
                self.active_contracts[contract_id]['status'] = 'closed_early'

            return result

        except Exception as e:
            print(f"Close exception: {e}")
            return None

    def get_contract_outcome(self, contract_id: str) -> Tuple[bool, float]:
        """
        Get final outcome: (won, pnl)
        """
        contract = self.active_contracts.get(contract_id)
        if not contract:
            return False, 0.0

        if contract['status'] == 'closed':
            result = contract.get('result', {})
            return result.get('is_win', False), result.get('profit_loss', 0.0)

        return False, 0.0

    def get_active_count(self) -> int:
        """
        Number of open contracts.
        """
        return sum(1 for c in self.active_contracts.values() if c['status'] == 'open')

    def get_performance_summary(self) -> Dict:
        """
        Summary of contract performance.
        """
        closed_contracts = [
            c for c in self.active_contracts.values()
            if c['status'] in ['closed', 'closed_early']
        ]

        if not closed_contracts:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0,
                'avg_pnl_per_trade': 0.0,
            }

        wins = sum(1 for c in closed_contracts if c.get('result', {}).get('is_win', False))
        losses = len(closed_contracts) - wins
        total_pnl = sum(c.get('result', {}).get('profit_loss', 0.0) for c in closed_contracts)

        return {
            'total_trades': len(closed_contracts),
            'winning_trades': wins,
            'losing_trades': losses,
            'win_rate': wins / len(closed_contracts) if closed_contracts else 0.0,
            'total_pnl': total_pnl,
            'avg_pnl_per_trade': total_pnl / len(closed_contracts) if closed_contracts else 0.0,
        }
