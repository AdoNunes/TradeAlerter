import unittest
from unittest.mock import MagicMock
import pandas as pd
import os
import os.path as op
import queue
from datetime import datetime, timedelta
from tradealerter import check_orders
from tradealerter.brokerages.eTrade_api import eTrade

root_dir  =  os.path.abspath(os.path.dirname(__file__))

class TestCheckOrders(unittest.TestCase):
    
    def setUp(self):
        self.queue = queue.Queue(maxsize=10)
        self.order_fname = op.join(root_dir, "data", "orders.json")
        self.port_fname = op.join(root_dir, "data", "portfolio.csv")
        if os.path.exists(self.port_fname):
            os.remove(self.port_fname)
        self.bksession = MagicMock(spec=eTrade)
        self.check_orders = check_orders.orders_check(queue=self.queue,
                                                      order_fname=self.order_fname,
                                                      port_fname=self.port_fname,
                                                      bksession=self.bksession)
        print("setup")
        
    def test_make_alerts(self):       
        orders = self.check_orders.orders
        
        order_buy = orders[0]
        alert = self.check_orders.make_alert(order_buy)
        self.assertEqual('BTO 2 TSLA 195P 06/02 @3.1', alert)
        
        order_sell = orders[3]
        alert = self.check_orders.make_alert(order_sell)
        self.assertEqual('STC 3 TSLA 195P 06/02 @3.73', alert)
    
    def test_track_portfolio(self):
        # Test BTO
        order_buy = self.check_orders.orders[0]   
        self.check_orders.track_portfolio(order_buy)
        expected_1 = {'date': order_buy['closeTime'],
                    'symbol': order_buy['symbol'],
                    'isopen': True,
                    'broker': 'etrade',
                    'qty': order_buy['quantity'],
                    'fills': order_buy['filledQuantity'],
                    "ordID": order_buy['order_id']
                    }

        # assert expected values
        trade = self.check_orders.port.loc[0]
        for exp, val in expected_1.items():
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)

        # Test BTO average
        order_buy_avg = self.check_orders.orders[1] 
        self.check_orders.track_portfolio(order_buy_avg)  
        exp_price = round((order_buy['price']*order_buy['quantity'] + \
            order_buy_avg['price']*order_buy_avg['quantity'])/ \
            (order_buy['quantity']+order_buy_avg['quantity']), 2)
        
        expected_2 = {
                    'avged': 1,
                    'avg_date': f"{order_buy['closeTime']},{order_buy_avg['closeTime']}",
                    'avg_qty': f"{order_buy['quantity']},{order_buy_avg['quantity']}", 
                    "avg_price": f"{order_buy['price']},{order_buy_avg['price']}",
                    "avg_ordID": f"{order_buy['order_id']},{order_buy_avg['order_id']}",                           
                    'qty': order_buy['quantity'] + order_buy_avg['quantity'],
                    'fills': order_buy['filledQuantity'] + order_buy_avg['filledQuantity'], 
                    'price': exp_price, 
                    'ordID': order_buy_avg['order_id']
                    }
        # assert expected values
        trade = self.check_orders.port.loc[0]
        for exp, val in expected_2.items():
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)

        # Test BTO avg 2
        order_buy_avg2 = self.check_orders.orders[2] 
        self.check_orders.track_portfolio(order_buy_avg2)  
        exp_price = round((order_buy['price']*order_buy['quantity'] + \
            order_buy_avg['price']*order_buy_avg['quantity']+ \
            order_buy_avg2['price']*order_buy_avg2['quantity'])/ \
            (order_buy['quantity']+order_buy_avg['quantity']+order_buy_avg2['quantity']), 2)
        
        expected_3 = {
                    'avged': 2,
                    'avg_date':  f"{expected_2['avg_date']},{order_buy_avg2['closeTime']}",
                    'avg_qty': f"{expected_2['avg_qty']},{order_buy_avg2['quantity']}", 
                    "avg_price": f"{expected_2['avg_price']},{order_buy_avg2['price']}",
                    "avg_ordID": f"{expected_2['avg_ordID']},{order_buy_avg2['order_id']}",                           
                    'qty': expected_2['qty'] + order_buy_avg2['quantity'],
                    'fills': expected_2['fills'] + order_buy_avg2['filledQuantity'], 
                    'price': exp_price, 
                    'ordID': order_buy_avg2['order_id']
                    }
        # assert expected values
        trade = self.check_orders.port.loc[0]
        for exp, val in expected_3.items():
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)

        # Test STC
        order_stc = self.check_orders.orders[3] 
        self.check_orders.track_portfolio(order_stc)
        trade = self.check_orders.port.loc[0]
        
        pnl = (order_stc['price'] - trade['price'])/trade['price']*100
        mult = 1 if trade['asset']=='option' else .1
        pnldollars = round(pnl*order_stc['filledQuantity']*trade['price']*mult, 2)
        
        expected_4 = {
            "STC-price": order_stc['price'],
            "STC-date": order_stc['closeTime'],
            "STC-ordID": order_stc['order_id'],
            "STC-fills": order_stc['filledQuantity'],
            "STC-qty": order_stc['quantity'],
            "PnL": round(pnl,2),
            'PnL$': pnldollars,
        }
        # assert expected values
        trade = self.check_orders.port.loc[0]
        for exp, val in expected_4.items():
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)

        # Test STC
        order_stc2 = self.check_orders.orders[4] 
        self.check_orders.track_portfolio(order_stc2)
        trade = self.check_orders.port.loc[0]
        
        exp_price = round((order_stc['price']*order_stc['filledQuantity'] + \
            order_stc2['price']*order_stc2['filledQuantity'])/ \
            (order_stc['filledQuantity']+order_stc2['filledQuantity']), 2)
        
        pnl2 = (order_stc2['price'] - trade['price'])/trade['price']*100
        pnldollars2 = round(pnl2*order_stc2['filledQuantity']*trade['price']*mult, 2)
        
        pnl_avg = (pnl*order_stc['filledQuantity'] + round(pnl2,2)*order_stc2['filledQuantity'])/\
                    (order_stc['filledQuantity']+order_stc2['filledQuantity'])  
        expected_5 = {
            "STC-price": exp_price,
            "STC-date": order_stc2['closeTime'],
            "STC-ordID": order_stc2['order_id'],
            "STC-fills": order_stc['filledQuantity'] + order_stc2['filledQuantity'],
            "STC-qty": order_stc['quantity'] + order_stc2['quantity'],
            "PnL": round(pnl_avg,2),
            'PnL$': pnldollars+pnldollars2,
            "STCs-price": f"{order_stc['price']},{order_stc2['price']}",
            "STCs-ordID": f"{order_stc['order_id']},{order_stc2['order_id']}",
            "STCs-fills": f"{order_stc['filledQuantity']},{order_stc2['filledQuantity']}",
            "STCs-qty": f"{order_stc['quantity']},{order_stc2['quantity']}",
        }
        # assert expected values
        trade = self.check_orders.port.loc[0]
        for exp, val in expected_5.items():
            if isinstance(trade[exp], float):
                self.assertAlmostEqual(trade[exp], val, places=2)
            else:
                self.assertEqual(trade[exp], val)
                

    def tearDown(self):
        if os.path.exists(self.port_fname):
            os.remove(self.port_fname)

if __name__ == '__main__':
    unittest.main()
