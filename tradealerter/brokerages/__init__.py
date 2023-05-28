from abc import ABC, abstractmethod
from configurator import cfg

class BaseBroker(ABC):
    order_filled = 'FILLED'
    order_working = 'WORKING'
    @abstractmethod
    def __init__(self, api_key, secret_key, passphrase):
        pass

    @abstractmethod
    def get_session(self):
        pass

    @abstractmethod
    def get_orders(self):
        pass

    @abstractmethod
    def get_portfolio(self):
        pass
