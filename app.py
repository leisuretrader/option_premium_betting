import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import json
import pickle
from datetime import datetime, timedelta, date
pd.options.mode.chained_assignment = None  # default='warn'
pd.options.display.float_format = "{:,.2f}".format


def nearest_value(input_list, find_value):
    difference = lambda input_list : abs(input_list - find_value)
    res = min(input_list, key=difference)
    return res

def weekdays_calculator(end_str):
    today = datetime.today().date()
    end = datetime.strptime(end_str, '%Y-%m-%d').date()
    return np.busday_count(today, end)

def split_list(input_list, n):  #this will return generater, add list() to output as list
    for i in range(0, len(input_list), n): 
        yield input_list[i:i + n] 
        
# output = list(split_list(test_list, 3)) 
def yf_info(ticker):
    return yf.Ticker(ticker)

def current_price(ticker):
    return yf_info(ticker).info['regularMarketPrice']

def historical_data(ticker):
    hist_price = yf.download(ticker, 
                         period='3y',
                         interval='1d',
                         auto_adjust=True)[['Close']]
    return hist_price

def perc_change(ticker,horizon):
    data = historical_data(ticker)
    data['return_perc'] = data.pct_change(periods=horizon,fill_method='ffill').round(decimals=4)
    return data.dropna()

def latest_perc_change(ticker,horizon, past_days):
    historical = perc_change(ticker,horizon)
    r = historical.return_perc.values.tolist()
    return r[-past_days:]

def describe_perc_change(ticker,horizon):
    cur_price = current_price(ticker)
    data = perc_change(ticker,horizon)
    describe = data.describe(percentiles = [.001,.01,.05,.1,.15,.25,.5,.75,.85,.90,.95,.99,.999])
    
    describe['Close'] = cur_price
    describe['price'] = cur_price * (1+describe['return_perc'])
    describe['return_perc'] = describe['return_perc'] * 100
    describe['price_int'] = describe['price'].astype(int)
    return describe
    
def option_expiry_dates(ticker):
    return yf_info(ticker).options  #return expiry dates

def option_chain(ticker, expiry_date, call_or_put=None, in_or_out=None):
    result = yf_info(ticker).option_chain(expiry_date)
    if call_or_put is None:
        call = result.calls
        put = result.puts
        result = call.append(put, ignore_index=True)
    elif call_or_put not in ['call','put']:
        return 'please input call or put'
    else:
        result = result.calls if call_or_put=='call' else result.puts if call_or_put=='put' else result
        
    result = result.loc[result['inTheMoney'] == True] if in_or_out == 'in' else result.loc[result['inTheMoney'] == False] if in_or_out == 'out' else result
    return result
    
def perc_change_with_option(ticker, horizon, expiry_date, call_or_put=None, in_or_out=None):
    perc_change_data = describe_perc_change(ticker,horizon)
    price_int_l = perc_change_data['price_int'].values.tolist()
    opt_data = option_chain(ticker, expiry_date, call_or_put, in_or_out)
    all_strikes = opt_data.strike.tolist()
    
    chose_strike = []
    last_price = []
    for i in price_int_l:
        if i in all_strikes:
            lp = opt_data.loc[opt_data['strike']==i].lastPrice.values
            chose_strike.append(int(i))
            last_price.append(lp)
        else:
            nearest_strike = nearest_value(all_strikes, i)
            lp = opt_data.loc[opt_data['strike']==nearest_strike].lastPrice.values
            chose_strike.append(int(nearest_strike))
            last_price.append(lp)
    last_price = [i[0] for i in last_price]
    
    perc_change_data['chose_strike'] = chose_strike
    perc_change_data['last_price'] = last_price
    
    perc_change_data.loc['count','return_perc'] = perc_change_data.loc['count','return_perc']/100
    perc_change_data.loc['count','price'] = 0
    perc_change_data.loc['count','price_int'] = 0
    perc_change_data.loc['count','chose_strike'] = 0
    perc_change_data.loc['count','last_price'] = 0
    
    perc_change_data.loc['std','price'] = 0
    perc_change_data.loc['std','price_int'] = 0
    perc_change_data.loc['std','chose_strike'] = 0
    perc_change_data.loc['std','last_price'] = 0
    
    perc_change_data.loc['mean','price'] = 0
    perc_change_data.loc['mean','price_int'] = 0
    perc_change_data.loc['mean','chose_strike'] = 0
    perc_change_data.loc['mean','last_price'] = 0
    
    return perc_change_data

def plot_histogram(ticker, horizon):
    fig = go.Figure()
    historical = perc_change(ticker,horizon)
    all_perc_change_l = historical.return_perc.values.tolist()
    
    latest_perc_change_l = all_perc_change_l[-20:]
    cur_per_change = all_perc_change_l[-1:]
    print (cur_per_change)
    fig.add_trace(go.Histogram(x=all_perc_change_l,
#                                     histnorm = 'probability',
                                    name = 'all',
#                                     autobinx=True,
#                                     xbins = dict(
#                                                start=-0.4,
#                                                end=0.4,
#                                                size=0.05),
                                    marker_color='#330C73',
                                    opacity=0.75,
#                                     texttemplate="%{x}", 
#                                     textfont_size=10
                                    ))
    
    fig.add_trace(go.Histogram(x=latest_perc_change_l,
                                    name = 'past 20 trading days',
#                                     autobinx=True,
                                    marker_color='#EB89B5',
                                    opacity=0.9,
                                    ))
    
    fig.add_trace(go.Histogram(x=cur_per_change,
                                name = 'today',
#                                 autobinx=True,
                                marker_color='#FF0000',
                                opacity=1,
                                ))

    fig.update_layout(
        barmode='overlay',
        title_text='% Change Distribution Count', # title of plot
        xaxis_title_text='% Change', # xaxis label
        yaxis_title_text='Count', # yaxis label
#         bargap=0.2, # gap between bars of adjacent location coordinates
#         bargroupgap=0.1 # gap between bars of the same location coordinates
    )
    fig.show()

ticker = 'AEE'
expiry_date = '2022-05-20'
days = weekdays_calculator(expiry_date)
print (ticker, expiry_date, days)

def get_basic_info(df):  # return list [current_price, mean, std,ninety_price, ninety_last,ninety_perc_change,dollar_return
    result = []
    current_price = round(df.loc['count','Close'].astype(float),2)
    mean = round(df.loc['mean','return_perc'].astype(float),2)
    std = round(df.loc['std','return_perc'].astype(float),2)
    
    ninety_price = round(df.loc['90%','chose_strike'].astype(float),2)
    ninety_last = round(df.loc['90%','last_price'].astype(float),2)
    ninety_perc_change = round((ninety_price / current_price -1), 4)
    
    dollar_return = round((ninety_last / current_price),4)
    
    result.extend([current_price, mean, std, ninety_price, ninety_last, ninety_perc_change, dollar_return])
    return result
    
def spy_benchmark():
    r = perc_change_with_option(ticker="spy", horizon=days, expiry_date=expiry_date, call_or_put=None, in_or_out = 'out')
    return get_basic_info(r)

# spy = spy_benchmark()  
# spy

descp = perc_change_with_option(ticker=ticker, horizon=days, expiry_date=expiry_date, call_or_put=None, in_or_out = 'out')
print (descp)
plot_histogram(ticker, days)

option_chain(ticker, expiry_date, call_or_put=None, in_or_out='out')
def dump_json(csv_filename):  #need to adjust to get all at once
    """ result look like:
    [{'AAPL': 167.9606},
     {'MSFT': 283.92},
     {'AMZN': 3067.065},
     {'TSLA': 989.62}]
    """
    ticker_list = pd.read_csv('{}.csv'.format(csv_filename),header=None)[0].tolist()[1:]
    result_list = []
    for i in ticker_list:
        print ('get data for {}'.format(i))
        stock_data_dict = {}
        stock_data_dict[i] = get_stock_price(i)
        result_list.append(stock_data_dict)
    y = json.dumps(stock_list)
    with open('{}_json.json'.fomrat(csv_filename), 'w') as outfile:
        outfile.write(y)           
# dump_json("spy")

def select_stock(json_filename):
    f = open('{}.json'.format(json_filename))
    data = json.load(f)
    stock_list = [list(i.keys())[0] for i in data]
    
    # Logic One : Check stocks price less than 100
    unqualified_l = [] 
    for i in data:
        ticker = list(i.keys())[0]
        try:
            cur_price = list(i.values())[0]
            if cur_price > 100:
                unqualified_l.append(ticker)
        except: # no price found, automatically unqualify
            unqualified_l.append(ticker)
    qualified_l = [x for x in stock_list if x not in unqualified_l]
    
    result = []
    #current_price, mean, std,ninety_price, ninety_percentile,ninety_perc_change,dollar_return
#     count = len(qualified_l)

############################################################################
#     breakdown_list = list(split_list(qualified_l,5))  #breakdown to list of lists, 5 element in each
#     print (breakdown_list)
    
#     for i in breakdown_list:
    
####################################################################
    
    for i in qualified_l:  #breakdownlist and do multithread
#         count = count - 1
#         print (i, 'countdown: ' + str(count))
        basic_info = {}
        try:
            df = perc_change_with_option(ticker=i, horizon=days, expiry_date=expiry_date, call_or_put=None, in_or_out = 'out')
            ticker_info = get_basic_info(df)
            basic_info['ticker'] = i
            basic_info['price'] = ticker_info[0]
            basic_info['mean'] = ticker_info[1]
            basic_info['std'] = ticker_info[2]
            basic_info['90_strike_price'] = ticker_info[3]
            basic_info['90_last'] = ticker_info[4]
            basic_info['90_perc_change'] = ticker_info[5]
            basic_info['90_dollar_return'] = ticker_info[6]
            print (basic_info)
            result.append(basic_info)
        except:
            print (i, 'errorhappened')

    try:  # try store in json file first, if file, then store to pickle
        y = json.dumps(result)
        with open('ticker_info.json', 'w') as outfile:
            outfile.write(y)
        print ('all stored in json')
    except:
        file_name = "ticker_info.pkl"
        open_file = open(file_name, "wb")
        pickle.dump(result, open_file)
        open_file.close()
        print ('all stored in pickle')
        
select_stock("spy_json")

def further_filter():
    f = open('ticker_info.json')
    data = json.load(f)
    print (len(data))
    
    qualified_l = []
    for i in data:
        if i.get('mean') > 0:  #ticker has mean >0
            if i.get('std') < spy[2]:  #ticker has std less than spy
                qualified_l.append(i)
    
    return qualified_l

further_filter()
    
