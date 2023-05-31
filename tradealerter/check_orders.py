import os.path as op
import time
import json
import pandas as pd
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
        self.port_fname = op.join(cfg['paths']['data'], "portfolio.csv")
        if op.exists(self.port_fname):    
            self.port = pd.read_csv(self.port_fname)
        else:
            self.port = pd.DataFrame(columns=['date','symbol', "isopen", "broker", 'qty', 'avg', 
                                              'fills', 'price', 'ordID', "STC-price", "STC-date", 
                                              "STC-ordID", "STC-fills", "STC-qty", 
                                              "avg_dates", "avg_qty", "avg_prices"])
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


    def track_portfolio(self, order):
        "Track portfolio, update portfolio.csv"

        if order['status'] != 'FILLED':
            print("order not filled")
            return
        open_trade = self.port['symbol'] == order['symbol'] and self.port['isopen'] == 1 and self.port['broker'] == order['broker']
        isopen, trade_ix = open_trade.any(), open_trade.idxmax()
        # track portfolio
        if order['action'] == 'BUY' and not isopen:
            msg = self.do_BTO(order)
        elif order['action'] == 'BUY' and isopen:
            msg = self.do_BTO_avg(order, trade_ix)
        elif order['action'] == 'SELL':
            # find the corresponding BUY order
            buy_order = self.port[(self.port['symbol'] == order['symbol']) & (self.port['qty'] == order['quantity']) & (self.port['broker'] == order['broker']) & (self.port['STC-price'].isna())]
            if len(buy_order):
                self.port.loc[buy_order.index, 'STC-price'] = order['price']
                self.port.loc[buy_order.index, 'STC-date'] = order['enteredTime']
                self.port.loc[buy_order.index, 'STC-ordID'] = order['order_id']
                self.port.loc[buy_order.index, 'STC-fills'] = order['filledQuantity']
                self.port.loc[buy_order.index, 'STC-qty'] = order['quantity']
            else:
                print(f"Can't find corresponding BUY order for {order['symbol']}")
        # save pushed orders
        if len(self.orders):
            with open(self.order_fname, 'w') as f:
                json.dump(self.orders, f)
        time.sleep(5)

    def do_BTO(self, order):
        "Make BUY order in portfolio"
        self.port = self.port.append({'date': order['enteredTime'], 
                                      'isopen':1,
                                      'symbol': order['symbol'],
                                      'broker': order['broker'], 
                                      'qty': order['quantity'],
                                      'fills': order['filledQuantity'], 
                                      'price': order['price'], 
                                      'ordID': order['order_id']
                                      }, ignore_index=True)
        return "New BTO order added to portfolio"

    def do_BTO_avg(self, order, trade_ix):
        "Make BUY order in portfolio"
        trade = self.port.loc[trade_ix]
        
        n_avg = 0 if trade['avg'] is None else trade['avg']
        n_fills = 0 if trade['fills'] is None else trade['fills']
        qty = 0 if trade['qty'] is None else trade['qty']
        if n_fills != qty:
            print(f"Trade {order['symbol']} not filled yet but new avg added")
        price = (trade['price'] * trade['fills'] + order['price'] * order['filledQuantity'])/(trade['fills'] + order['filledQuantity'])
        
        avg_dates = "" if trade['avg_dates'] is None else trade['avg_dates'] + ","
        avg_qty = str(trade['fills']) if trade['avg_qty'] is None else trade['avg_qty'] + ","
        avg_prices = str(trade['price']) if trade['avg_prices'] is None else trade['avg_prices'] + ","
        
        self.port = self.port.append({'avg_dates': avg_dates + order['enteredTime'], 
                                      'n_avg': n_avg + 1,                                  
                                      'qty': qty + order['quantity'],
                                      'fills': n_fills + order['filledQuantity'], 
                                      'price': order['price'], 
                                      'ordID': order['order_id']
                                      }, ignore_index=True)
        return "New BTO avg order added to portfolio"