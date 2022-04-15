from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.express as px
import scipy.stats as stats
import matplotlib.pyplot as plt
import json

pd.options.mode.chained_assignment = None  # default='warn'


today = datetime.today().date()

def get_stock_price(ticker):
    stock = yf.Ticker(ticker)
    price = stock.info['regularMarketPrice']
    return price
  
def options_chain(symbol):
    tk = yf.Ticker(symbol)
    # Expiration dates
    exps = tk.options

    options = pd.DataFrame()
    for e in exps:
        opt = tk.option_chain(e)
        opt = pd.DataFrame().append(opt.calls).append(opt.puts)
        opt['expirationDate'] = e
        options = options.append(opt, ignore_index=True)

    options['expirationDate'] = pd.to_datetime(options['expirationDate'])
#     + timedelta(days = 1)
    options['dte'] = (options['expirationDate'] - datetime.today()).dt.days / 365
    
    # Boolean column if the option is a CALL
    options['CALL'] = options['contractSymbol'].str[4:].apply(
        lambda x: "C" in x)
    
    options[['bid', 'ask', 'strike']] = options[['bid', 'ask', 'strike']].apply(pd.to_numeric)
    options['mark'] = (options['bid'] + options['ask']) / 2 # Calculate the midpoint of the bid-ask
    
    # Drop unnecessary and meaningless columns
    options = options.drop(columns = ['contractSize', 'currency', 'change', 'percentChange', 'lastTradeDate', 'lastPrice'])

    return options

def closest_value(input_list, input_value):
    difference = lambda input_list : abs(input_list - input_value)
    res = min(input_list, key=difference)
    return res

def bid_ask_result(ticker,input_list, expiry_date):
    opt = options_chain(ticker)
    layer1 = opt.loc[(opt['inTheMoney'] == False) & (opt['expirationDate'] == expiry_date)]
    all_strikes = layer1.strike.tolist()
    all_strikes = [int(x) for x in all_strikes]

    result = []
    chose_strike = []
    bid_ask_list = []

    for i in input_list:
        if i in all_strikes:
            layer2 = layer1.loc[(layer1['strike']==i)]
            bid_ask = round(((float(layer2.bid.values) + float(layer2.ask.values))/2),2)
            chose_strike.append(i)
            bid_ask_list.append(bid_ask)
        else:
            closest = closest_value(all_strikes,i)
#             print (i, closest)
            layer2 = layer1.loc[(layer1['strike']==closest)]
            bid_ask = round(((float(layer2.bid.values) + float(layer2.ask.values))/2),2)
            chose_strike.append(closest)
            bid_ask_list.append(bid_ask)
    result.append(chose_strike)
    result.append(bid_ask_list)
    return result

def option_bet(ticker,select_period, expiry_date):
    hist_price = yf.download(ticker, 
                             period='3y',
                             interval='1d',
                             auto_adjust=True)[['Close']]
    yf_info = yf.Ticker(ticker)

    hist_price['return_perc'] = hist_price.pct_change(periods=select_period,fill_method='ffill')
    hist_price = hist_price.dropna().round(decimals=4)
    hist_price['return_perc'] = hist_price['return_perc']*100
    hist_return = hist_price['return_perc']

    def describe_df():
        data = hist_return
        current_price = float(yf_info.info['regularMarketPrice'])
        print ("{0} price : {1}".format(ticker, current_price))
        describe = data.describe(percentiles = [.001,.01,.05,.1,.15,.25,.5,.75,.85,.90,.95,.99,.999])
        describe_df = describe.to_frame()
        numbers = describe_df['return_perc'].tolist()

        result = []
        for i in numbers:
            cal = current_price * (1+float(i)/100)
            result.append(cal)

        describe_df['price'] = result
        describe_df['price_int'] = describe_df['price'].astype(int)
        return describe_df

    price_return_data = describe_df()
    price_input_list = price_return_data.price_int.tolist()
    checked_result = bid_ask_result(ticker,price_input_list,expiry_date)
    chose_strike = checked_result[0]
    chose_bid_ask = checked_result[1]

    price_return_data['chose_strike'] = chose_strike
    price_return_data['bid_ask'] = chose_bid_ask

    return price_return_data

def p_select(ticker,p_value, select_period, expiry_date):
    opt_data = option_bet(ticker, select_period, expiry_date)
    opt = opt_data.loc[['mean','std', p_value]]
#     .bid_ask.values[0]
    return opt


def plot_histogram(df):
    fig = px.histogram(df, x="return_perc", marginal='box',
                       opacity=0.8,
                       log_y = False, # represent bars with log scale
                       hover_data=df.columns, 
                       text_auto=False,
                       nbins=100) # can try violin, rug or box.nbins means how many bars we want it aggregate to
    fig.show()
