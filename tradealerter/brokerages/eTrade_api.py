
import webbrowser
import pyetrade
import re
from datetime import datetime
import time
import json
import os
import functools

from tradealerter.configurator import cfg
from tradealerter.brokerages import BaseBroker


def retry_on_exception(retries=3, do_raise=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, retries+1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    print(f"Exception occurred: {e}. Retrying... (Attempt {attempt}/{retries})")
            if do_raise:
                raise Exception(f"Method {func.__name__} failed after {retries} retries.")
            else:
                print(f"Method {func.__name__} failed after {retries} retries. Returning...")
        return wrapper
    return decorator

class eTrade(BaseBroker):
    def __init__(self, account_n=0, accountId=None):
        self.base_url = cfg["etrade"]["PROD_BASE_URL"]
        self.accountId = accountId
        self.account_n = account_n
        self.consumer_key = cfg["etrade"]["CONSUMER_KEY"]
        self.consumer_secret = cfg["etrade"]["CONSUMER_SECRET"]
        self.token_fname = os.path.join(cfg['paths']['data'], "tokens.json")
        self.portfolio = []
        self.orders = []

    def get_session(self):
        """Get token and sessions, will try several times and sleep for a second between each try"""
        for ix in range(5):
            try:
                return self._get_session()
            except:
                print(ix,"Could not get session, trying again")
                time.sleep(1)
        raise Exception("Could not get session")

    def _get_access_token(self, oauth,verifier_code):
        """Gets access token and tries 3 times before giving up"""        
        for ix in range(3):
            try:
                request_token = oauth.get_access_token(verifier_code)
                return request_token                
            except:
                print(f"Could not get token, trying again {ix}/3")
                time.sleep(1)
        raise Exception("Could not get token")

    def _get_session(self):
        """Allows user authorization for the sample application with OAuth 1"""
        def sessions():
            # get sessions
            kwargs = {
                'client_key': self.consumer_key,
                'client_secret': self.consumer_secret,
                'resource_owner_key': self.tokens['oauth_token'],
                'resource_owner_secret': self.tokens['oauth_token_secret'],
                'dev': False
                }
            self.account_session = pyetrade.ETradeAccounts(**kwargs)
            self.market_session = pyetrade.ETradeMarket(**kwargs)     
            self.order_session = pyetrade.ETradeOrder(**kwargs)
            self._get_account()
            return True

        # if tokens saved try getting session
        if os.path.exists(self.token_fname):
            with open(self.token_fname, "r") as f:
                self.tokens = json.load(f)   
            try:
                return sessions()  
            except:
                print("Loaded tokens expired, requesting new tokens")
                os.remove(self.token_fname)  

        # if tokens not valid, get new ones
        oauth = pyetrade.ETradeOAuth(self.consumer_key, self.consumer_secret)
        if cfg['etrade'].getboolean('WITH_BROWSER'):
            webbrowser.open(oauth.get_request_token())
        else:
            print("Please open the following URL in your browser:")
            print(oauth.get_request_token())
        verifier_code = input("Please accept agreement and enter verification code from browser: ")
        self.tokens = self._get_access_token(oauth, verifier_code)
        with open(self.token_fname, "w") as f:
            json.dump(self.tokens, f)
        return sessions() 

    retry_on_exception()
    def _get_account(self):
        """
        Calls account list API to retrieve a list of the user's E*TRADE accounts
        """
        data = self.account_session.list_accounts(resp_format='json')
        self.accounts_list = data["AccountListResponse"]["Accounts"]["Account"]        
        
        if self.accountId is not None:
            self.accountIdKey = [self.accounts_list[i]['accountIdKey'] for i in range(len(self.accounts_list)) 
                                 if self.accounts_list[i]['accountId'] == self.accountId][0]
        else:
            self.accountIdKey = self.accounts_list[self.account_n]['accountIdKey']
            self.accountId = self.accounts_list[self.account_n]['accountId']
        self.account = self.accounts_list[self.account_n]

    def renew_access_token(self):
        print("Renewing access token...")
        self.access_token, self.access_token_secret = self.oauth.renew_access_token()
        print("Access token renewed.")

    retry_on_exception()
    def check_orders(self):
        print("Checking orders...")
        accounts = self.account_session.list_accounts()
        new_orders = self.account_session.list_transactions(accounts)
        for order in new_orders:
            if order["orderId"] not in self.orders and order["status"] == "EXECUTED":
                print("Order filled:")
                print(json.dumps(order, indent=2))
                self.orders.append(order["orderId"])

    retry_on_exception()
    def get_portfolio(self):
        print("Checking portfolio...")
        resp = self.account_session.get_account_portfolio(self.accountIdKey)        
        new_portfolio = resp["PortfolioResponse"]["AccountPortfolio"]["Position"]
        new_portfolio = self.format_portfolio(new_portfolio)
        
        if self.portfolio != new_portfolio:
            for symbol in new_portfolio:
                if symbol not in self.portfolio:
                    print(f"New stock purchased: {symbol} for ${new_portfolio[symbol]['costBasis']}")
                elif self.portfolio[symbol]['quantity'] != new_portfolio[symbol]['quantity']:
                    if self.portfolio[symbol]['quantity'] > new_portfolio[symbol]['quantity']:
                        print(f"Stock sold: {symbol} for ${new_portfolio[symbol]['price']}")
                    else:
                        print(f"New stock purchased: {symbol} for ${new_portfolio[symbol]['costBasis']}")
            self.portfolio = new_portfolio

    def format_portfolio(self, portfolio:list)->list:
        return portfolio

    def format_option(self, opt_ticker:str)->str:
        """From ticker_monthdayyear[callput]strike to ticker:year:month:day:optionType:strikePrice"""
        exp = r"(\w+)_(\d{2})(\d{2})(\d{2})([CP])([\d.]+)"        
        match = re.search(exp, opt_ticker, re.IGNORECASE)
        if match:
            symbol, mnt, day, yer, type, strike = match.groups()
            if type.lower() == 'c':
                type = 'Call'
            converted_code = f"{symbol}:20{yer}:{mnt}:{day}:{type}:{strike}"
            return converted_code
        else:
            print('No format_option match for', opt_ticker)

    def format_order(self, order:dict)->dict:
        """Make order format standard"""
        stopPrice= order['OrderDetail'][0]['Instrument'][0].get('stopPrice')
        timestamp = int(order['OrderDetail'][0]['placedTime'])
        enteredTime = datetime.fromtimestamp(timestamp/1000).strftime("%Y-%m-%d %H:%M:%S.%f")
        if 'executedTime' in order['OrderDetail'][0]:
            timestamp = int(order['OrderDetail'][0]['executedTime'])/1000
            closeTime = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")
        else:
            closeTime = enteredTime
        status = order['OrderDetail'][0]['status'].upper().replace('EXECUTED', 'FILLED').replace('OPEN',"WORKING")
        symbol = order['OrderDetail'][0]['Instrument'][0]['Product']['symbol']
        asset = 'stock' if order['orderType']=='EQ' else 'option' if order['orderType']=='OPTN' else "N/A"
        if asset == 'option':
            prod =  order['OrderDetail'][0]['Instrument'][0]['Product']
            opty = prod['callPut'][0].upper().replace('CALL','C').replace('PUT','P')
            symbol = f"{prod['symbol']}_{prod['expiryMonth']:02d}{prod['expiryDay']:02d}{str(prod['expiryYear'])[2:]}{opty}{str(prod['strikePrice']).replace('.0','')}"

        order_info = {
            'symbol': symbol,
            'asset': asset,
            'action': order['OrderDetail'][0]['Instrument'][0]['orderAction'],
            'status': status,
            'quantity': order['OrderDetail'][0]['Instrument'][0]['orderedQuantity'],
            'filledQuantity': order['OrderDetail'][0]['Instrument'][0]['filledQuantity'],
            'price': order['OrderDetail'][0]['Instrument'][0].get('averageExecutionPrice'),
            "order_id": order['orderId'],
            "stopPrice": stopPrice if stopPrice else None,
            'orderType':  order['OrderDetail'][0]['priceType'],
            'enteredTime': enteredTime,
            "closeTime": closeTime,
            "broker": "etrade"
            }
        return order_info

    retry_on_exception()
    def get_orders(self, status:str='ALL'):
        "status: ALL, WORKING, FILLED"
        assert status.upper() in ['ALL', 'WORKING', 'FILLED'], 'status must be ALL, WORKING, or FILLED'
        resp = self.order_session.list_orders(self.accountIdKey, resp_format='json')
        orders = []
        for order in resp['OrdersResponse']['Order']:
            order_info = self.format_order(order)
            if status.upper() == 'ALL':
                orders.append(order_info)
            elif status.upper() == 'WORKING' and  order_info['status'] == 'WORKING':
                orders.append(order_info)
            elif status.upper() == 'FILLED' and order_info['status'] == 'FILLED':
                orders.append(order_info)
        return orders



if __name__ == "__main__":
    rt = eTrade()
    rt.get_session()
    print(rt.get_orders('FILLED'))
    