import re
import time
from datetime import datetime
from webull import webull, paper_webull
from tradealerter.configurator import cfg
from tradealerter.brokerages import BaseBroker


class weBull:
    def __init__(self, paper_trading: bool = False) -> None:
        self._webull = paper_webull() if (paper_trading) else webull()
        self._loggedin = False
        self.name = 'webull'
        self.option_ids = {}

    def get_session(self, use_workaround: bool = True) -> bool:
        wb = self._webull
        if (use_workaround):
            wb._set_did(cfg["webull"]['SECURITY_DID'])

        wb.login(username=cfg["webull"]['LOGIN_EMAIL'],
                password=cfg["webull"]['LOGIN_PWD'],
                device_name=cfg["webull"]['DEVICE_ID']
                )

        self.success = wb.get_trade_token(cfg["webull"]['TRADING_PIN'])
        self.session = wb
        if self.success: 
            print(f"Logging into webull: Success!")
        else:
            print(f"Logging into webull: Failed!")
        return self.success

    def get_account_info(self):
        """
        Call portfolio API to retrieve a list of positions held in the specified account
        """
        data = self.session.get_account()       

        acc_inf ={
            'securitiesAccount':{   
                'positions':[],
                'accountId' : str(data['secAccountId']),
                'currentBalances':{
                    'liquidationValue': data.get('netLiquidation'),
                    'cashBalance': data['accountMembers'][1]['value'],
                    'availableFunds': data['accountMembers'][2]['value'],
                    },
        }}
        positions = data['positions']
        for position in positions:
            pos = {
                "longQuantity" : eval(position['position']),
                "symbol": position['ticker']["symbol"],
                "marketValue": eval(position['marketValue']),
                "assetType": position['assetType'],
                "averagePrice": eval(position['costPrice']),
                "currentDayProfitLoss": eval(position['unrealizedProfitLoss']),
                "currentDayProfitLossPercentage": float(eval(position['unrealizedProfitLoss']))/100,
                'instrument': {'symbol': position['ticker']["symbol"],
                                'assetType': position['assetType'],
                                }
            }
            acc_inf['securitiesAccount']['positions'].append(pos)
        if not len(positions):
            acc_inf['securitiesAccount']['positions'] = []
            print("No portfolio")

        # get orders and add them to acc_inf
        orders = self.session.get_history_orders(count=10)
        orders_inf =[]  
        if isinstance(orders, dict) and orders.get('success') is False:
            raise ValueError("Order entpoint obsolete, go to webull/endpoints.py (actual webull package) line 144 and remove '&startTime=1970-0-1'")
        
        for order in orders:
            order_status = order['status'].upper()
            if order_status in ['CANCELLED', 'FAILED']:
                continue
            orders_inf.append(self.format_order(order))
        acc_inf['securitiesAccount']['orderStrategies'] = orders_inf
        return acc_inf

    def get_order_info(self, order_id): 
        """ Get order info from order_id, mimicks the order_info from TDA API"""
        orders = self.session.get_history_orders()      
        for order in orders:
            if order['orders'][0]['orderId'] == order_id:
                order_status = order['status'].upper().replace("CANCELLED", "CANCELED")
                order_info = self.format_order(order)         
                return order_status, order_info
        return None, None

    def format_order(self, order:dict):
        """ output format for order_response. Order, mimicks the order_info from TDA API"""
        stopPrice= order['orders'][0].get('stpPrice')
        
        price = order['orders'][0].get('avgFilledPrice')
        if price is None:
            price = order['orders'][0].get('lmtPrice')
            
        timestamp = int(order['orders'][0]['createTime0'])/1000

        enteredTime = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')
        timestamp = int(order['orders'][0]['updateTime0'])/1000
        closeTime = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')
        asset = order['orders'][0]['tickerType'].lower()
        if asset == 'option':            
            yer, mnt, day = order['orders'][0]['optionExpireDate'].split("-")
            otype = order['orders'][0]['optionType'][0].upper()
            symbol = f"{order['orders'][0]['symbol']}_{mnt}{day}{yer[2:]}{otype}{order['orders'][0]['optionExercisePrice']}".replace(".00","")
            symbol = self.fix_symbol(symbol, "in")
            orderStrategyType = order['optionStrategy'].upper()
        else:
            symbol = order['orders'][0]['symbol']
            orderStrategyType= 'SINGLE'
        status = order['status'].upper()
        order_info = {
            'status': status,
            'action': order['orders'][0]['action'],
            'asset': asset,
            'symbol' : symbol,      
            'quantity': eval(order['orders'][0]['totalQuantity']),
            'filledQuantity': eval(order['orders'][0]['filledQuantity']),
            'price': float(price) if price else float(order['auxPrice']),
            'orderStrategyType': orderStrategyType,
            "order_id" : order['orders'][0]['orderId'],
            "orderId": order['orders'][0]['orderId'],
            "stopPrice": stopPrice if stopPrice else None,
            'orderType':  order['orders'][0]['orderType'],
            'enteredTime': enteredTime,
            "closeTime": closeTime,
            'broker' : "weBull",
            'orderLegCollection':[{
                'instrument':{'symbol': symbol},
                'instruction': order['orders'][0]['action'],
                'quantity': eval(order['filledQuantity']),
            }]             
        }    
        return order_info

    def format_option(self, opt_ticker:str)->dict:
        """From ticker_monthdayyear[callput]strike to dict {ticker, year-month-day,optionType,strikePrice"""
        exp = r"(\w+)_(\d{2})(\d{2})(\d{2})([CP])([\d.]+)"        
        match = re.search(exp, opt_ticker, re.IGNORECASE)
        if match:
            symbol, mnt, day, yer, type, strike = match.groups()
            type = 'call' if type.lower() == 'c' else 'put'
            opt_info = {
                'ticker': symbol,
                'date': f"20{yer}-{mnt}-{day}",
                'direction': type,
                'strike': strike
                }
            return opt_info
        else:
            print('No format_option match for', opt_ticker)

    def reformat_option(self, opt_info:dict)->str:
        "From dict to standard option format ticker_monthdayyear[callput]strike"      
        yer, mnt, day = opt_info['date'].split("-")
        otype = opt_info['direction'][0].upper()
        return f"{opt_info['ticker']}_{mnt}{day}{yer[2:]}{otype}{opt_info['strike']}"

    def get_option_id(self, symb:str):
        "Get option id from option symb with standard format"
        if self.option_ids.get(symb) is None:
            opt_info = self.format_option(symb)
            if opt_info:
                options_data = self.session.get_options(stock=opt_info['ticker'],
                                                        direction=opt_info['direction'], 
                                                        expireDate=opt_info['date'])
                filtered_options_data = [option for option in options_data if option['strikePrice'] == opt_info['strike'] and \
                    option[opt_info['direction']]['expireDate'] == opt_info['date']]
                option_id = filtered_options_data[0][opt_info['direction']]['tickerId']
                self.option_ids[symb] = str(option_id)
                return option_id
            else:
                return None
        else:
            return self.option_ids[symb]

    def fix_symbol(self, symbol:str, direction:str):
        "Fix symbol for options, direction in or out of webull format"
        if direction == 'in':
            return symbol.replace("SPXW", "SPX")
        elif direction == 'out':
            return symbol.replace("SPX", "SPXW")

    def get_quotes(self, symbol:list) -> dict:  
        resp = {}
        for symb in symbol:        
            if "_" in symb:
                symb = self.fix_symbol(symb, "in")
                opt_info = self.format_option(symb)
                if opt_info:
                    try:
                        option_id = self.get_option_id(symb)
                        quote = self.session.get_option_quote(stock=opt_info['ticker'], optionId=option_id)
                        
                        ts = quote['data'][0]['tradeStamp']
                        ask = eval(quote['data'][0]['askList'][0]['price'])
                        bid = eval(quote['data'][0]['bidList'][0]['price'])
                        ticker = self.fix_symbol(self.reformat_option(opt_info), 'out')
                        
                        resp[ticker] = {
                                        'symbol' : ticker,
                                        'description': option_id,
                                        'askPrice': ask,  
                                        'bidPrice': bid,    
                                        'quoteTimeInLong': ts
                                        }
                    except Exception as e:
                        sym_out = self.fix_symbol(symb, "out")
                        print("Error getting quote for",  sym_out, e)
                        resp[sym_out] = {'symbol': sym_out,
                                        'description':'Symbol not found'
                                        }
            else:
                quote = self.session.get_quote(symb)
                if quote and quote['template']=='stock':                
                    resp[symb] = {
                                'symbol' : quote['symbol'],
                                'description': quote['disSymbol'],
                                'askPrice': eval(quote['askList'][0]['price']),
                                'bidPrice': eval(quote['bidList'][0]['price']),
                                'quoteTimeInLong': round(time.time()*1000),
                            }
                else:
                    print(symb, "not found", quote['template'])
                    resp[symb] = {'symbol' :symb,
                                    'description':'Symbol not found'
                                    }
        return resp

    def get_orders(self, status:str='ALL'):
        orders = self.session.get_history_orders()
        if isinstance(orders, dict) and orders.get('success') is False:
            raise ValueError("Order entpoint obsolete, go to webull/endpoints.py (actual webull package) line 144 and remove '&startTime=1970-0-1'")
        
        orders_all  = []
        for order in orders:
            if status != "ALL" and order['status'].upper() != status:
                continue
            orders_all.append(self.format_order(order))
        return orders_all

if 0:
    self = weBull()
    self.get_session()
    self.get_account_info()
    self.get_quotes(["AAuPL_062323C180", "AAPL_062323C190"])
    optid = self.get_option_id("AAPL_062323C180")
   
