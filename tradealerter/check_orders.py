import os.path as op
import sys
import time
import json
import pandas as pd
from datetime import datetime
import re
import queue
from tradealerter.configurator import cfg
from tradealerter.brokerages import get_brokerage


class orders_check():
    def __init__(self, 
                 queue=queue.Queue(maxsize=10),
                 order_fname = op.join(cfg['paths']['data'], "orders.json"),
                 port_fname = op.join(cfg['paths']['data'], "portfolio.csv"),
                 bksession=None
                 ):
        # load orders
        self.order_fname = order_fname
        if op.exists(self.order_fname):    
            with open(self.order_fname, 'r') as f:
                self.orders = json.load(f)
        else:
            self.orders = []
        
        # load portfolio
        self.port_fname = port_fname
        if op.exists(self.port_fname):    
            self.port = pd.read_csv(self.port_fname)
        else:
            self.port = pd.DataFrame(columns=[
                'date','symbol', "isopen", "broker", 'qty', 'avged', 'fills', 'price', 'ordID', 
                'PnL', "PnL$", "PnLs", "PnLs$", "asset",
                "STC-price", "STC-date", "STC-ordID", "STC-fills", "STC-qty", 
                "STCs-price", "STCs-date", "STCs-ordID", "STCs-fills", "STCs-qty",
                "avg_date", "avg_qty", "avg_price", "avg_ordID", 'BTO-n', 'STC-n', 'BTOs-sent', 'STCs-sent'])
        
        if bksession is None:
            self.bksession =  get_brokerage()
        else:
            self.bksession = bksession()
        self.queue = queue
        
        # load previous orders, dont send them
        if not cfg['alert_configs'].getboolean('DEV'):
            self._read_orders(False, False)

    def check_orders(self, refresh_rate=1,
                     dev=False,                     
                     alert=True):
        "Pool filled orders, generate alert and push it with date and inx to queue"
        n_errors = 0
        if dev:
            self.orders = []
        with open(op.join(cfg['paths']['data'],'webull_getorders_ts.txt'), 'a') as file:
            while True:
                try:
                    t0 = datetime.now().strftime("%m/%d %H:%M:%S")
                    self._read_orders(dev, alert)
                    t1 = datetime.now().strftime("%m/%d %H:%M:%S")
                    iout = f'{t0},{t1}\n'                    
                except Exception as e:
                    n_errors += 1
                    print(f"Cauguth error num {n_errors}:", e)
                    t1 = datetime.now().strftime("%m/%d %H:%M:%S")
                    iout = f',{t1},error{n_errors}\n'
                time.sleep(refresh_rate)
                file.write(iout)
                file.flush()

    
    def _read_orders(self, dev, alert):
        et_orders = self.bksession.get_orders('FILLED')
        for eto in et_orders[-1::-1]:                
            if not len(self.orders) or eto['order_id'] not in [o['order_id'] for o in self.orders]:
                _, trade_ix = self.track_portfolio(eto)                
                if alert:
                    alert = f"{self.make_alert(eto)}"
                    self.queue.put([alert, eto['closeTime'], trade_ix])
                self.orders.append(eto)
                if dev:
                    time.sleep(5)
        # save pushed orders
        if len(self.orders):
            with open(self.order_fname, 'w') as f:
                json.dump(self.orders, f)

    def make_alert(self, order:dict)->str:
        """ From order makes alert with format BTO|STC Qty Symbol [Strike] [Date] @ Price"""
        qty = order['quantity']
        price = order['price']
        timestamp = int(order['orders'][0]['updateTime0'])/1000
        closeTime = datetime.fromtimestamp(timestamp).strftime("%m/%d %H:%M:%S")
        if "_" in order['symbol']:
            # option
            act = order['action'].replace('BUY_OPEN', 'BTO').replace('SELL_CLOSE', 'STC').replace('BUY', 'BTO').replace('SELL', 'STC')
            exp = r"(\w+)_(\d{6})([CP])([\d.]+)"        
            match = re.search(exp, order['symbol'], re.IGNORECASE)
            if match:
                symbol, date, type, strike = match.groups()
                symb_str = f"{act} {qty} {symbol} {strike}{type} {date[:2]}/{date[2:4]} @{round(price,2)} - filled at {closeTime}"
        else:
            act = order['action'].replace('BUY', 'BTO').replace('SELL', 'STC')
            symb_str= f"{act} {qty} {order['symbol']} @{price} - filled at {closeTime}"
        return symb_str

    def extra_info_from_port():
        return
    
    def get_trade_ix(self, order):
        open_trade = (self.port['symbol'] == order['symbol']) & \
                     (self.port['isopen'] == 1) & \
                     (self.port['broker'] == order['broker'])
        if open_trade.any():
            isopen, trade_ix = open_trade.any(), open_trade.idxmax()
        else:
            isopen, trade_ix = False, None
        return isopen, trade_ix
    
    def track_portfolio(self, order):
        "Track portfolio, update portfolio.csv"

        if order['status'].upper() != 'FILLED':
            print("order not filled")
            return
        
        isopen, trade_ix = self.get_trade_ix(order)
        # track portfolio
        if order['action'].startswith('BUY') and not isopen:
            port_info = self.do_BTO(order)
            isopen, trade_ix = self.get_trade_ix(order)
        elif order['action'].startswith('BUY') and isopen:
            port_info = self.do_BTO_avg(order, trade_ix)
            port_info["index"] = trade_ix
        elif order['action'].startswith('SELL') and isopen:
            port_info = self.do_STC(order, trade_ix)
            port_info["index"] = trade_ix
        elif order['action'].startswith('SELL') and not isopen:
            port_info = {"message":"STC order without BTO"}
            trade_ix = None
        # save portfolio
        if port_info.get('message') != "STC order without BTO":
            self.save_portfolio()
        
        return port_info, trade_ix

    def save_portfolio(self):
        self.port.to_csv(self.port_fname, index=False)
        
    def do_BTO(self, order):
        "Make BUY order in portfolio"
        new_trade = {'date': order['closeTime'],
             'isopen': 1,
             'symbol': order['symbol'],
             'asset': order['asset'],
             'broker': order['broker'],
             'qty': order['quantity'],
             'fills': order['filledQuantity'],
             'price': order['price'],
             'ordID': order['order_id'],
             'BTO-n' : 1,
             'BTOs-sent':0,
             'STCs-sent':0,
             }
        self.port = pd.concat([self.port, pd.DataFrame(new_trade, index=[0])], ignore_index=True)
        return new_trade

    def do_BTO_avg(self, order, trade_ix):
        "Make BUY order in portfolio"
        trade = self.port.loc[trade_ix]
        
        n_avg = 0  if pd.isna(trade['avged']) else trade['avged']
        n_fills = int(0 if pd.isna(trade['fills']) else trade['fills'])
        qty = 0 if pd.isna(trade['qty']) else trade['qty']
        assert  n_fills == qty, f"Trade {order['symbol']} not filled yet but new avg added"
        price = (trade['price'] * trade['fills'] + order['price'] * order['filledQuantity'])/\
                    (trade['fills'] + order['filledQuantity'])
        
        avg_trade = {
                    'avged': int(n_avg + 1),
                    'avg_date': self.combine_prevs(trade_ix, order['closeTime'], 'date', 'avg_date'),
                    'avg_qty':  self.combine_prevs(trade_ix, order['quantity'], 'qty', 'avg_qty'),
                    "avg_price": self.combine_prevs(trade_ix, order['price'], 'price', 'avg_price'),
                    "avg_ordID": self.combine_prevs(trade_ix, order['order_id'], 'ordID', 'avg_ordID'),
                    'qty': qty + order['quantity'],
                    'fills': n_fills + int(order['filledQuantity']), 
                    'price': round(price, 2), 
                    'ordID': order['order_id'],
                    'BTO-n' : trade['BTO-n'] + 1,
                    }
        for k, v in avg_trade.items():
            self.port.loc[trade_ix, k] = v
        
        return avg_trade

    def do_STC(self, order, trade_ix):
        "Make SELL order in portfolio"
        trade = self.port.loc[trade_ix]

        stc_price = order['price']
        stc_date = order['closeTime']
        stc_fills = order['filledQuantity']
        stc_qty = order['quantity']
        pnlq_mult = 1 if trade['asset'] == 'option' else .1

        if pd.isna(trade['STC-price']):
            # First STC for the trade
            stc_trade = {
                'STC-price': stc_price,
                'STC-date': stc_date,
                'STC-ordID': order['order_id'],
                'STC-fills': stc_fills,
                'STC-qty': stc_qty 
                }
            for k, v in stc_trade.items():
                self.port.loc[trade_ix, k] = v

            # Calculate PnL
            trade = self.port.loc[trade_ix]
            pnl_perc = (trade['STC-price'] - trade['price']) / trade['price'] * 100
            pnl_dollar = round(pnl_perc* trade['price'] * trade['STC-qty']*pnlq_mult, 2)
            stc_trade['PnL'] = round(pnl_perc, 2)
            stc_trade['PnL$'] = pnl_dollar
            stc_trade['STC-n'] = 1
            self.port.loc[trade_ix, 'PnL'] = stc_trade['PnL']
            self.port.loc[trade_ix, 'PnL$'] = stc_trade['PnL$']
            self.port.loc[trade_ix, 'STC-n'] = stc_trade['STC-n']
            
        else:
            # Multiple STCs for the trade, calculate average values
            prev_stc_price = trade['STC-price']
            prev_stc_fills = trade['STC-fills']
            prev_stc_qty = trade['STC-qty']
            tot_fills = prev_stc_fills + stc_fills
            avg_price = (prev_stc_price * prev_stc_fills + stc_price * stc_fills) / tot_fills
            curr_pnl = (stc_price - trade['price'])/trade['price'] * 100            
            curr_pnlq = curr_pnl * trade['price'] * stc_qty * pnlq_mult
            pnl = (avg_price - trade['price'])/trade['price'] * 100 
            # save multiple stcs values
            stc_trade = {
                'STCs-date':self.combine_prevs(trade_ix, stc_date, 'STC-date', 'STCs-date'),
                'STCs-qty': self.combine_prevs(trade_ix, stc_qty, 'STC-qty', 'STCs-qty'),
                'STCs-price': self.combine_prevs(trade_ix, stc_price, 'STC-price', 'STCs-price'),
                'STCs-ordID': self.combine_prevs(trade_ix, order['order_id'],'STC-ordID', 'STCs-ordID'),
                'STCs-fills': self.combine_prevs(trade_ix, order['filledQuantity'],'STC-fills', 'STCs-fills'),
                'PnLs': self.combine_prevs(trade_ix, round(curr_pnl,2),'PnL', 'PnLs'),
                'PnLs$': self.combine_prevs(trade_ix, round(curr_pnlq,2),'PnL$', 'PnLs$'),    
                'STC-price': avg_price,
                'STC-date': stc_date,
                'STC-ordID': order['order_id'],
                'STC-fills': tot_fills,
                'STC-qty': prev_stc_qty + stc_qty,   
                'PnL': round(pnl,2),
                'PnL$': round(pnl * trade['price'] * (prev_stc_qty + stc_qty) * pnlq_mult,2),
                'STC-n': trade['STC-n'] + 1  
                }
            for k, v in stc_trade.items():
                self.port.loc[trade_ix, k] = v

        return stc_trade
    
    
    def combine_prevs(self, trade_ix:int, new_val, col_main:str, col_cum:str)->str:
        """Combine previous values in portfolio when multiple bto/stc

        Parameters
        ----------
        trade_ix : int
            index of trade in portfolio
        new_val : str|numeric
            new value to be added
        col_main : str
            column name with avergaed values
        col_cum : str
            column name with cummulative values

        Returns
        -------
        str
            combined values
        """

        trade = self.port.loc[trade_ix]
        if pd.isna(trade[col_cum]):
            return f"{trade[col_main]},{new_val}"
        else:
            return f"{trade[col_cum]},{new_val}"
            
        
