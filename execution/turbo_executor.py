from execution.base_executor import BaseExecutor
import logging
log = logging.getLogger(__name__)

class TurboExecutor(BaseExecutor):
    async def execute(self, signal, stake, asset):
        if not signal or not signal.get('direction'):
            return {"contract_id": None, "status": "NO_SIGNAL"}
        
        try:
            direction = signal['direction']
            contract_type = "PUT" if direction == "PUT" else "CALL"
            
            result = await self.buy_fn(
                symbol=asset['symbol'],
                contract_type=contract_type,
                stake=stake,
                barrier='0.1',
                duration=60
            )
            
            contract_id = result.get('buy', {}).get('contract_id')
            return {
                "contract_id": contract_id,
                "status": "PLACED" if contract_id else "FAILED",
                "type": "turbo"
            }
        except Exception as e:
            log.error(f"Turbo execute failed: {e}")
            return {"contract_id": None, "status": "FAILED"}
