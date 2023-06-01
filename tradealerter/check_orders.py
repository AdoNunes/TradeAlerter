import os.path as op
import time
import json
import pandas as pd
import re
import queue
from tradealerter.brokerages.eTrade_api import eTrade
from tradealerter.configurator import cfg

class orders_check():
    def __init__(self, 
                 queue=queue.Queue(maxsize=10),
                 order_fname = op.join(cfg['paths']['data'], "orders.json"),
                 port_fname = op.join(cfg['paths']['data'], "portfolio.csv"),
                 bksession=None
                 ):
        self.order_fname = order_fname
        if op.exists(self.order_fname):    
            with open(self.order_fname, 'r') as f:
                self.orders = json.load(f)
        else:
            self.orders = []
        self.port_fname = port_fname
        if op.exists(self.port_fname):    
            self.port = pd.read_csv(self.port_fname)
        else:
            self.port = pd.DataFrame(columns=['date','symbol', "isopen", "broker", 'qty', 'avged', 
                                              'fills', 'price', 'ordID', "STC-price", "STC-date", 
                                              "STC-ordID", "STC-fills", "STC-qty", 
                                              "avg_date", "avg_qty", "avg_price", "avg_ordID"])
        
        if bksession is None:
            self.bksession =  eTrade()
        else:
            self.bksession = bksession()
        self.bksession.get_session()
        self.queue = queue

    def check_orders(self, refresh_rate=1,
                     dev=False,
                     alert_sufix=cfg['alert_configs']['string_add_to_alert']):
        "Pool filled orders, generate alert and push it with date to queue"
        if dev:
            self.orders = []
        while True:
            et_orders = self.bksession.get_orders('FILLED')
            for eto in et_orders[-1::-1]:                
                if not len(self.orders) or eto['order_id'] not in [o['order_id'] for o in self.orders]:
                    print(eto)
                    alert = f"{self.make_alert(eto)} {alert_sufix}"
                    self.queue.put([alert, eto['closeTime']])
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
                symb_str = f"{act} {qty} {symbol} {strike}{type} {date[:2]}/{date[2:4]} @{round(price,2)}"
        else:
            act = order['action'].replace('BUY', 'BTO').replace('SELL', 'STC')
            symb_str= f"{act} {qty} {order['symbol']} @{price}"
        return symb_str


    def track_portfolio(self, order):
        "Track portfolio, update portfolio.csv"

        if order['status'] != 'FILLED':
            print("order not filled")
            return
        open_trade = (self.port['symbol'] == order['symbol']) & \
                     (self.port['isopen'] == 1) & \
                     (self.port['broker'] == order['broker'])
        if open_trade.any():
            isopen, trade_ix = open_trade.any(), open_trade.idxmax()
        else:
            isopen, trade_ix = False, None
            
        # track portfolio
        if order['action'].startswith('BUY') and not isopen:
            msg = self.do_BTO(order)
        elif order['action'].startswith('BUY') and isopen:
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
        new_trade = {'date': order['closeTime'],
             'isopen': 1,
             'symbol': order['symbol'],
             'broker': order['broker'],
             'qty': order['quantity'],
             'fills': order['filledQuantity'],
             'price': order['price'],
             'ordID': order['order_id']
             }
        self.port = pd.concat([self.port, pd.DataFrame(new_trade, index=[0])], ignore_index=True)
        return "New BTO order added to portfolio"

    def do_BTO_avg(self, order, trade_ix):
        "Make BUY order in portfolio"
        trade = self.port.loc[trade_ix]
        
        n_avg = 0  if pd.isna(trade['avged']) else trade['avged']
        n_fills = int(0 if pd.isna(trade['fills']) else trade['fills'])
        qty = 0 if pd.isna(trade['qty']) else trade['qty']
        if n_fills != qty:
            print(f"Trade {order['symbol']} not filled yet but new avg added")
        price = (trade['price'] * trade['fills'] + order['price'] * order['filledQuantity'])/(trade['fills'] + order['filledQuantity'])
        price = round(price, 2)
        
        avg_dates = f"{trade['date']}," if pd.isna(trade['avg_date']) else trade['avg_date'] + ","
        avg_qty = f"{trade['qty']}," if pd.isna(trade['avg_qty']) else trade['avg_qty'] + ","
        avg_prices = f"{trade['price']}," if pd.isna(trade['avg_price']) else trade['avg_price'] + ","
        avg_orders = f"{trade['ordID']}," if pd.isna(trade['avg_ordID']) else trade['avg_ordID'] + ","
        new_trade = {
                    'avged': int(n_avg + 1),
                    'avg_date': avg_dates + order['closeTime'],
                    'avg_qty': avg_qty + f"{int(order['filledQuantity'])}",  
                    "avg_price": avg_prices + f"{order['price']}", 
                    "avg_ordID": avg_orders + f"{order['order_id']}",                             
                    'qty': qty + order['quantity'],
                    'fills': n_fills + int(order['filledQuantity']), 
                    'price': price, 
                    'ordID': order['order_id']
                    }
        for k, v in new_trade.items():
            self.port.loc[trade_ix, k] = v
        
        return "New BTO avg order added to portfolio"