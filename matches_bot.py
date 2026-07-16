"""
Deriv Digit Matches Bot
Autonomous trading bot for Digit Matches/Differs on synthetic indices.
Runs as a lane in multi_lane.py orchestration or standalone.
"""

import asyncio
import json
import os
import time
import urllib.request
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import websockets

from strategies.digit_match_strategy import DigitMatchStrategy
from execution.digit_match_executor import DigitMatchExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MatchesBot:
    def __init__(
        self,
        app_id: str,
        api_token: str,
        symbol: str = "R_75",
        trade_interval: int = 5,
        stake_amount: float = 1.0,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        supabase_client = None,
        account_id: Optional[str] = None,
    ):
        self.app_id = app_id
        self.api_token = api_token
        self.account_id = account_id
        self.symbol = symbol
        self.trade_interval = trade_interval
        self.stake_amount = stake_amount

        self.telegram_token = telegram_token
        self.telegram_chat_id = telegram_chat_id
        self.supabase = supabase_client

        self.ws = None
        self._recv_lock = asyncio.Lock()
        self._message_queue = asyncio.Queue()  # Central message dispatch queue
        self.strategy = DigitMatchStrategy()
        self.executor = None
        self.is_running = False
        self.tick_count = 0
        self.last_trade_time = 0
        self.balance = 0.0
        self.req_id = 0
        self.use_new_api = bool(app_id and account_id)

    def _get_next_req_id(self) -> int:
        """Generate unique request ID for Deriv API."""
        self.req_id += 1
        return self.req_id

    async def _get_ws_url(self) -> str:
        """Get WebSocket URL from Deriv (OTP-based or fallback to public)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_ws_url_sync)

    def _get_ws_url_sync(self) -> str:
        """Synchronous version for executor."""
        if self.app_id and self.account_id and self.api_token:
            try:
                # New API: Get OTP-authenticated URL
                req = urllib.request.Request(
                    f"https://api.derivws.com/trading/v1/options/accounts/{self.account_id}/otp",
                    data=b"",
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Deriv-App-ID": self.app_id,
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as r:
                    result = json.loads(r.read())
                ws_url = result["data"]["url"]
                logger.info(f"OTP obtained — new API WebSocket URL ready (account: {self.account_id})")
                return ws_url
            except Exception as e:
                logger.warning(f"OTP auth failed ({e}), trying direct new API connection")
                # Fallback: Try direct connection to new API (OTP in URL)
                try:
                    req = urllib.request.Request(
                        f"https://api.derivws.com/trading/v1/options/accounts/{self.account_id}/otp",
                        data=b"",
                        headers={
                            "Authorization": f"Bearer {self.api_token}",
                            "Deriv-App-ID": self.app_id,
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10) as r:
                        result = json.loads(r.read())
                    return result["data"]["url"]
                except Exception as e2:
                    logger.warning(f"Direct API also failed ({e2})")

        if self.app_id and self.api_token:
            # Old API fallback (for legacy tokens)
            logger.info("Using legacy Deriv API endpoint")
            return f"wss://ws.binaryws.com/websockets/v3?app_id={self.app_id}"

        # Emergency fallback
        return "wss://ws.binaryws.com/websockets/v3?app_id=1089"

    async def connect(self) -> bool:
        """Connect to Deriv API via websockets."""
        try:
            ws_url = await self._get_ws_url()
            self.ws = await websockets.connect(
                ws_url,
                ping_interval=60,
                ping_timeout=30,
                close_timeout=10,
            )
            logger.info("Connected to Deriv!")

            # Initialize executor with self (for send/recv)
            self.executor = DigitMatchExecutor(self, contract_type="DIGITMATCH")

            # Authorize connection
            if not await self._authorize():
                logger.error("Authorization failed")
                return False

            logger.info(f"✅ MatchesBot authorized | Balance: ${self.balance:.2f}")
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}", exc_info=True)
            return False

    async def _authorize(self) -> bool:
        """Authorize and get account balance."""
        try:
            if self.use_new_api:
                # New API: OTP already authenticated, just fetch balance
                await self.send({"balance": 1})
                res = await self.recv()
                if "error" in res:
                    logger.error(f"Auth error: {res['error']['message']}")
                    return False
                bal_data = res.get("balance", {})
                self.balance = float(bal_data.get("balance", 0))
                logger.info(f"Authorised! DEMO | ${self.balance:.2f}")
                return True
            else:
                # Old API: token auth
                await self.send({"authorize": self.api_token})
                res = await self.recv()
                if "error" in res:
                    logger.error(f"Auth error: {res['error']['message']}")
                    return False
                auth = res.get("authorize", {})
                self.balance = float(auth.get("balance", 0))
                acct_type = "DEMO" if auth.get("is_virtual") else "LIVE"
                logger.info(f"Authorised! {acct_type} | ${self.balance:.2f}")
                return True

        except Exception as e:
            logger.error(f"Authorization exception: {e}", exc_info=True)
            return False

    async def send(self, payload: Dict[str, Any]) -> None:
        """Send message via websocket."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")
        await self.ws.send(json.dumps(payload))

    async def recv(self) -> Dict[str, Any]:
        """Receive message from websocket with lock to prevent concurrent reads."""
        if not self.ws:
            raise RuntimeError("WebSocket not connected")

        async with self._recv_lock:
            msg = await self.ws.recv()
            return json.loads(msg)

    async def disconnect(self) -> None:
        """Disconnect from Deriv API."""
        if self.ws:
            try:
                await self.ws.close()
                logger.info("MatchesBot disconnected")
            except Exception as e:
                logger.warning(f"Disconnect error: {e}")

    async def _message_reader(self) -> None:
        """Central message reader - reads from websocket and queues messages."""
        while self.is_running:
            try:
                response = await asyncio.wait_for(self.recv(), timeout=5.0)
                await self._message_queue.put(response)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message reader error: {e}")
                await asyncio.sleep(1)

    async def _keepalive_loop(self) -> None:
        """Monitor connection health and detect stale connections."""
        while self.is_running:
            try:
                await asyncio.sleep(30)
                # Check if connection is closed using close_code (None = open)
                if self.ws and self.ws.close_code is not None:
                    logger.error("Connection died, reconnecting...")
                    if not await self.connect():
                        logger.error("Reconnection failed, stopping bot")
                        self.is_running = False
                        break
            except Exception as e:
                logger.warning(f"Keepalive loop error: {e}")
                await asyncio.sleep(1)

    async def stream_ticks(self) -> None:
        """
        Subscribe to live ticks and process them.
        """
        try:
            # Subscribe to ticks
            req_id = self._get_next_req_id()
            await self.send({
                "ticks": self.symbol,
                "subscribe": 1,
                "req_id": req_id,
            })
            logger.info(f"Subscribed to ticks for {self.symbol}")

            # Listen for tick updates from message queue
            while self.is_running:
                try:
                    response = await asyncio.wait_for(self._message_queue.get(), timeout=5.0)

                    if "error" in response:
                        logger.error(f"Tick error: {response.get('error', {}).get('message')}")
                        continue

                    if "tick" in response:
                        await self.process_tick(response["tick"])
                    elif "balance" in response:
                        # Keep balance updated
                        self.balance = float(response["balance"].get("balance", self.balance))
                    # Other message types (proposal, buy, etc.) will be handled by their respective waiters

                except asyncio.TimeoutError:
                    logger.debug("Tick stream timeout (normal)")
                    continue

        except Exception as e:
            logger.error(f"Tick stream exception: {e}", exc_info=True)

    async def process_tick(self, tick: dict) -> None:
        """
        Process new tick: analyze, decide, execute.
        """
        try:
            quote = tick.get("quote")
            if not quote:
                return

            self.tick_count += 1

            confidence = self.strategy.analyze_tick(quote)

            if self.tick_count % 50 == 0:
                report = self.strategy.get_report()
                logger.info(
                    f"[{self.symbol}] Tick #{self.tick_count}: "
                    f"Prediction={report['analysis']['prediction']}, "
                    f"Confidence={report['analysis']['confidence']:.2f}"
                )

            if not self.strategy.should_trade(confidence):
                return

            current_time = time.time()
            if current_time - self.last_trade_time < self.trade_interval:
                return

            await self.execute_trade(confidence)
            self.last_trade_time = current_time

        except Exception as e:
            logger.error(f"Tick processing exception: {e}")

    async def execute_trade(self, confidence) -> None:
        """
        Execute a trade via Deriv websockets.
        """
        try:
            trade_details = self.strategy.get_trade_details(confidence)
            if not trade_details:
                return

            barrier = trade_details['barrier']
            amount = trade_details['amount']
            contract_type = trade_details['contract_type']

            logger.info(
                f"🤖 Executing {contract_type} on digit {barrier} "
                f"(confidence={confidence.confidence:.2f}, stake=${amount:.2f})"
            )

            # Send contract proposal
            proposal_req_id = self._get_next_req_id()
            await self.send({
                "proposal": 1,
                "subscribe": 1,
                "contract_type": contract_type,
                "currency": "USD",
                "underlying_symbol": self.symbol,
                "duration": 1,
                "duration_unit": "t",
                "basis": "stake",
                "amount": amount,
                "barrier": str(barrier),
                "req_id": proposal_req_id,
            })

            # Wait for proposal response (with retry)
            proposal = None
            for attempt in range(2):
                try:
                    proposal = await asyncio.wait_for(
                        self._wait_for_proposal(proposal_req_id),
                        timeout=15.0
                    )
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"Proposal timeout (attempt {attempt+1}/2), retrying...")
                    if attempt < 1:
                        proposal_req_id = self._get_next_req_id()
                        await self.send({
                            "proposal": 1,
                            "subscribe": 1,
                            "contract_type": contract_type,
                            "currency": "USD",
                            "underlying_symbol": self.symbol,
                            "duration": 1,
                            "duration_unit": "t",
                            "basis": "stake",
                            "amount": amount,
                            "barrier": str(barrier),
                            "req_id": proposal_req_id,
                        })

            if not proposal:
                logger.error("Failed to get contract proposal after retries")
                return

            # Buy the contract
            buy_req_id = self._get_next_req_id()
            await self.send({
                "buy": 1,
                "price": proposal.get("ask_price"),
                "parameters": proposal.get("id"),
                "req_id": buy_req_id,
            })

            # Wait for buy confirmation
            buy_response = await asyncio.wait_for(
                self._wait_for_buy(buy_req_id),
                timeout=15.0
            )

            if buy_response and "buy" in buy_response:
                contract_id = buy_response["buy"].get("contract_id")
                logger.info(f"✅ Trade executed: {contract_id}")

                await self.send_telegram_notification(
                    f"🎯 **Matches Trade Opened**\n"
                    f"Type: {contract_type}\n"
                    f"Digit: {barrier}\n"
                    f"Stake: ${amount:.2f}\n"
                    f"ID: {contract_id}"
                )

                await self.monitor_contract(contract_id, barrier, stake_amount=amount)
            else:
                logger.error("Trade execution failed")

        except asyncio.TimeoutError:
            logger.error("Trade execution timeout")
        except Exception as e:
            logger.error(f"Trade execution exception: {e}", exc_info=True)

    async def _wait_for_proposal(self, req_id: int) -> Optional[Dict]:
        """Wait for proposal response with matching req_id from queue."""
        max_wait = 15.0
        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            try:
                response = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=max_wait - (time.time() - start_time)
                )

                # Check for errors first
                if "error" in response:
                    logger.error(f"API error in queue: {response.get('error', {}).get('message')}")
                    if response.get("req_id") == req_id:
                        return None  # Error response for our request
                    # Re-queue error for other handlers
                    await self._message_queue.put(response)
                    continue

                # Put non-proposal messages back for other consumers
                if response.get("req_id") == req_id and "proposal" in response:
                    logger.info(f"✅ Proposal received for req_id {req_id}")
                    return response.get("proposal")
                elif "proposal" in response:
                    logger.debug(f"Got proposal for req_id {response.get('req_id')}, not {req_id}")
                    # Re-queue for tick processor or other handlers
                    await self._message_queue.put(response)
                else:
                    # Not a proposal, re-queue
                    await self._message_queue.put(response)
            except asyncio.TimeoutError:
                logger.warning(f"Proposal timeout after {time.time() - start_time:.1f}s for req_id {req_id}")
                break
        return None

    async def _wait_for_buy(self, req_id: int) -> Optional[Dict]:
        """Wait for buy confirmation with matching req_id from queue."""
        max_wait = 15.0
        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            try:
                response = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=max_wait - (time.time() - start_time)
                )
                if response.get("req_id") == req_id and "buy" in response:
                    return response
                else:
                    await self._message_queue.put(response)
            except asyncio.TimeoutError:
                break
        return None

    async def monitor_contract(self, contract_id: str, barrier: str, timeout: int = 60, stake_amount: float = None) -> None:
        """
        Monitor contract until it closes via websockets.
        stake_amount: actual stake used for this trade (for correct PnL calculation)
        """
        if stake_amount is None:
            stake_amount = self.stake_amount

        start_time = time.time()
        payout = stake_amount * 8.93  # 8.93x payout for 1-tick duration
        win_profit = payout - stake_amount  # ~$7.93 profit per win

        while self.is_running and (time.time() - start_time) < timeout:
            try:
                # Listen for proposal_open_contract updates
                response = await asyncio.wait_for(self.recv(), timeout=2.0)

                if "proposal_open_contract" in response:
                    poc = response["proposal_open_contract"]
                    if str(poc.get("id")) == str(contract_id):
                        is_closed = poc.get("is_closed", False)

                        if is_closed:
                            # Contract closed - determine outcome
                            status = poc.get("status", "")
                            pnl = float(poc.get("profit", 0)) if status == "won" else -stake_amount

                            won = status == "won"
                            result_emoji = "✅ WIN" if won else "❌ LOSS"
                            logger.info(f"{result_emoji}: {contract_id} | PnL: ${pnl:.2f}")

                            # Record outcome with PnL for martingale tracking
                            self.strategy.record_outcome(int(barrier), won, pnl=pnl)

                            # Get updated report (includes martingale state)
                            report = self.strategy.get_report()

                            await self.send_telegram_notification(
                                f"🎰 **Matches Trade Closed**\n"
                                f"Result: {'✅ WIN' if won else '❌ LOSS'}\n"
                                f"PnL: ${pnl:.2f} | Total: ${report['total_profit']:.2f}\n"
                                f"Stake: ${report['current_stake']:.2f} | Losses: {report['consecutive_losses']}\n"
                                f"Win Rate: {self.strategy.get_win_rate():.1%}"
                            )

                            if self.supabase:
                                await self.log_trade_to_supabase(contract_id, barrier, won, pnl)

                            # Check if should continue trading
                            should_continue, reason = self.strategy.should_continue_trading()
                            if not should_continue:
                                logger.info(f"🛑 Trading stopped: {reason}")
                                await self.send_telegram_notification(
                                    f"🛑 **Session Ended**\n"
                                    f"{reason}\n"
                                    f"Final Profit: ${report['total_profit']:.2f}"
                                )
                                self.is_running = False

                            return

            except asyncio.TimeoutError:
                # No update yet, continue waiting
                pass
            except Exception as e:
                logger.error(f"Contract monitoring exception: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def send_telegram_notification(self, message: str) -> None:
        """
        Send Telegram notification.
        """
        if not (self.telegram_token and self.telegram_chat_id):
            logger.debug("Telegram not configured")
            return

        try:
            import requests
            import re
            # Convert markdown **text** to HTML <b>text</b>
            message_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", message)

            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.telegram_chat_id,
                "text": message_html,
                "parse_mode": "HTML",
            }
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, data=data, timeout=5)
            )
            if response.status_code == 200:
                logger.info("📱 Telegram notification sent ✓")
            else:
                logger.error(f"Telegram HTTP {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Telegram send error: {e}", exc_info=True)

    async def log_trade_to_supabase(
        self,
        contract_id: str,
        barrier: str,
        won: bool,
        pnl: float
    ) -> None:
        """
        Log trade to Supabase journal.
        """
        if not self.supabase:
            return

        try:
            self.supabase.table("trades").insert({
                "bot_type": "matches",
                "contract_id": contract_id,
                "symbol": self.symbol,
                "predicted_digit": int(barrier),
                "won": won,
                "pnl": pnl,
                "timestamp": datetime.utcnow().isoformat(),
            }).execute()

        except Exception as e:
            logger.error(f"Supabase log error: {e}")

    async def run(self) -> None:
        """
        Main bot loop.
        """
        if not await self.connect():
            logger.error("Failed to start MatchesBot")
            return

        self.is_running = True

        try:
            await self.send_telegram_notification(
                f"🚀 **MatchesBot Started**\n"
                f"Symbol: {self.symbol}\n"
                f"Stake: ${self.stake_amount}\n"
                f"Strategy: Digit Frequency + Patterns"
            )

            # Run message reader, tick stream, and keepalive monitor in parallel
            await asyncio.gather(
                self._message_reader(),
                self.stream_ticks(),
                self._keepalive_loop(),
                return_exceptions=True
            )

        except KeyboardInterrupt:
            logger.info("MatchesBot interrupted")
        except Exception as e:
            logger.error(f"Bot exception: {e}")
        finally:
            self.is_running = False
            await self.disconnect()

            await self.send_telegram_notification(
                f"🛑 **MatchesBot Stopped**\n"
                f"Final Win Rate: {self.strategy.get_win_rate():.1%}\n"
                f"Trades: {self.strategy.trades_executed}"
            )


async def main():
    """
    Standalone execution for testing.
    """
    app_id = os.getenv("DERIV_APP_ID", "")
    api_token = os.getenv("DERIV_TOKEN", "")
    account_id = os.getenv("DERIV_ACCOUNT_ID", "")
    telegram_token = os.getenv("TELEGRAM_TOKEN", "")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    bot = MatchesBot(
        app_id=app_id,
        api_token=api_token,
        account_id=account_id,
        symbol="R_75",
        telegram_token=telegram_token,
        telegram_chat_id=telegram_chat_id,
    )

    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
