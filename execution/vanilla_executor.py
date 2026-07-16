from execution.base_executor import BaseExecutor
import logging
log = logging.getLogger(__name__)

class VanillaExecutor(BaseExecutor):
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
                barrier_offset='0.002',
                duration=3600
            )
            
            contract_id = result.get('buy', {}).get('contract_id')
            return {
                "contract_id": contract_id,
                "status": "PLACED" if contract_id else "FAILED",
                "type": "vanilla"
            }
        except Exception as e:
            log.error(f"Vanilla execute failed: {e}")
            return {"contract_id": None, "status": "FAILED"}
