from execution.base_executor import BaseExecutor
import logging
log = logging.getLogger(__name__)

class BinaryExecutor(BaseExecutor):
    async def execute(self, signal, stake, asset):
        if not signal or not signal.get('direction'):
            return {"contract_id": None, "status": "NO_SIGNAL"}
        
        try:
            direction = signal['direction']
            contract_type = "PUT" if direction == "PUT" else "CALL"
            
            # Call existing place_binary or buy_fn
            result = await self.buy_fn(
                symbol=asset['symbol'],
                contract_type=contract_type,
                stake=stake,
                duration=1,
                duration_unit='m'
            )
            
            contract_id = result.get('buy', {}).get('contract_id')
            return {
                "contract_id": contract_id,
                "status": "PLACED" if contract_id else "FAILED"
            }
        except Exception as e:
            log.error(f"Binary execute failed: {e}")
            return {"contract_id": None, "status": "FAILED"}
