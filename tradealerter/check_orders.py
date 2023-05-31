import os.path as op
import time
import json
import re
import queue
from tradealerter.brokerages.eTrade_api import eTrade
from tradealerter.configurator import cfg

class orders_check():
    def __init__(self, queue=queue.Queue(maxsize=10)):
        self.order_fname = op.join(cfg['paths']['data'], "orders.json")
        if op.exists(self.order_fname):    
            with open(self.order_fname, 'r') as f:
                self.orders = json.load(f)
        else:
            self.orders = []
        self.bksession =  eTrade()
        self.bksession.get_session()
        self.queue = queue

    def check_orders(self, refresh_rate=1):
        "Pool filled orders, generate alert and push it with date to queue"
        while True:
            et_orders = self.bksession.get_orders('FILLED')
            for eto in et_orders[-1::-1]:                
                if not len(self.orders) or eto['order_id'] not in [o['order_id'] for o in self.orders]:
                    print(eto)
                    alert = f"{self.make_alert(eto)} {cfg['alert_configs']['string_add_to_alert']}"
                    self.queue.put([alert, eto['enteredTime']])
                    self.orders.append(eto)
                    print('found order')
            # save pushed orders
            if len(self.orders):
                with open(self.order_fname, 'w') as f:
                    json.dump(self.orders, f)
            time.sleep(refresh_rate)
    
    def make_alert(self, order:dict)->str:
        """ From order makes alert with format BTO|STC Qty Symbol [Strike] [Date] @ Price"""
        qty = order['quantity']
        price = order['price']
        if "_" in order['symbol']:
            # option
            act = order['action'].replace('BUY_OPEN', 'BTO').replace('SELL_CLOSE', 'STC')
            exp = r"(\w+)_(\d{6})([CP])([\d.]+)"        
            match = re.search(exp, order['symbol'], re.IGNORECASE)
            if match:
                symbol, date, type, strike = match.groups()
                symb_str = f"{act} {qty} {symbol} {strike}{type} {date[:2]}/{date[2:4]} @{price}"
        else:
            act = order['action'].replace('BUY', 'BTO').replace('SELL', 'STC')
            symb_str= f"{act} {qty} {order['symbol']} @{price}"
        return symb_str




