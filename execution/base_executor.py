from abc import ABC, abstractmethod

class BaseExecutor(ABC):
    def __init__(self):
        self.ws = None
        self.buy_fn = None
    
    @abstractmethod
    async def execute(self, signal, stake, asset):
        pass
