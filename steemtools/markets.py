from decimal import Decimal
from pprint import pprint

import numpy as np
import requests
import time
from steemtools.helpers import parse_payout
from steemtools.node import Node
import grequests


class Tickers(object):
    @staticmethod
    def btc_usd_ticker(verbose=False):
        prices = {}
        urls = [
            "https://api.bitfinex.com/v1/pubticker/BTCUSD",
            "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
            "https://www.okcoin.com/api/v1/ticker.do?symbol=btc_usd",
            "https://www.bitstamp.net/api/v2/ticker/btcusd/",
            "https://btc-e.com/api/2/btc_usd/ticker",
        ]
        rs = (grequests.get(u, timeout=2) for u in urls)
        responses = list(grequests.map(rs, exception_handler=lambda x, y: ""))

        for r in [x for x in responses if hasattr(x, "status_code") and x.status_code == 200]:
            if "bitfinex" in r.url:
                data = r.json()
                prices['bitfinex'] = {'price': float(data['last_price']), 'volume': float(data['volume'])}
            elif "coinbase" in r.url:
                data = r.json()
                prices['coinbase'] = {'price': float(data['price']), 'volume': float(data['volume'])}
            elif "okcoin" in r.url:
                data = r.json()["ticker"]
                prices['okcoin'] = {'price': float(data['last']), 'volume': float(data['vol'])}
            elif "bitstamp" in r.url:
                data = r.json()
                prices['bitstamp'] = {'price': float(data['last']), 'volume': float(data['volume'])}
            elif "btce"in r.url:
                data = r.json()["ticker"]
                prices['btce'] = {'price': float(data['avg']), 'volume': float(data['vol_cur'])}

        if verbose:
            pprint(prices)

        if len(prices) == 0:
            raise Exception("Obtaining BTC/USD prices has failed from all sources.")

        # vwap
        return np.average([x['price'] for x in prices.values()], weights=[x['volume'] for x in prices.values()])

    @staticmethod
    def steem_btc_ticker():
        prices = {}
        try:
            r = requests.get("https://poloniex.com/public?command=returnTicker", timeout=2).json()["BTC_STEEM"]
            prices['poloniex'] = {'price': float(r['last']), 'volume': float(r['baseVolume'])}
        except:
            pass
        try:
            r = requests.get("https://bittrex.com/api/v1.1/public/getticker?market=BTC-STEEM", timeout=2).json()["result"]
            price = (r['Bid'] + r['Ask']) / 2
            prices['bittrex'] = {'price': price, 'volume': 0}
        except:
            pass

        return np.mean([x['price'] for x in prices.values()])

    @staticmethod
    def sbd_btc_ticker(verbose=False):
        prices = {}
        try:
            r = requests.get("https://poloniex.com/public?command=returnTicker", timeout=2).json()["BTC_SBD"]
            if verbose:
                print("Spread on Poloniex is %.2f%%" % Tickers.calc_spread(r['highestBid'], r['lowestAsk']))
            prices['poloniex'] = {'price': float(r['last']), 'volume': float(r['baseVolume'])}
        except:
            pass
        try:
            r = requests.get("https://bittrex.com/api/v1.1/public/getticker?market=BTC-SBD", timeout=2).json()["result"]
            if verbose:
                print("Spread on Bittrex is %.2f%%" % Tickers.calc_spread(r['Bid'], r['Ask']))
            price = (r['Bid'] + r['Ask']) / 2
            prices['bittrex'] = {'price': price, 'volume': 0}
        except:
            pass

        return np.mean([x['price'] for x in prices.values()])

    @staticmethod
    def calc_spread(bid, ask):
        return (1 - (Decimal(bid) / Decimal(ask))) * 100


class Markets(Tickers):
    def __init__(self, cache_timeout=60, steem=None):
        if not steem:
            steem = Node().default()
        self.steem = steem

        self._cache_timeout = cache_timeout
        self._cache_timer = time.time()
        self._btc_usd = None
        self._steem_btc = None
        self._sbd_btc = None

    def _has_cache_expired(self):
        if self._cache_timer + self._cache_timeout < time.time():
            self._cache_timer = time.time()
            return True
        return False

    def btc_usd(self):
        if (self._btc_usd is None) or self._has_cache_expired():
            self._btc_usd = self.btc_usd_ticker()
        return self._btc_usd

    def steem_btc(self):
        if (self._steem_btc is None) or self._has_cache_expired():
            self._steem_btc = self.steem_btc_ticker()
        return self._steem_btc

    def sbd_btc(self):
        if (self._sbd_btc is None) or self._has_cache_expired():
            self._sbd_btc = self.sbd_btc_ticker()
        return self._sbd_btc

    def steem_sbd_implied(self):
        return self.steem_btc() / self.sbd_btc()

    def steem_usd_implied(self):
        return self.steem_btc() * self.btc_usd()

    def sbd_usd_implied(self):
        return self.sbd_btc() * self.btc_usd()

    def avg_witness_price(self, take=10):
        price_history = self.steem.rpc.get_feed_history()['price_history']
        return np.mean([parse_payout(x['base']) for x in price_history[-take:]])
