#nocoes gerais:
# construir modelo para o intervalo medio de oscilacao e qual o comportamento dessa oscilacao:
# usar a taxa de crescimento medio da empresa (projecao linear usando fechamentos em periodos largos)
# ao redor dessa projecao, construir as oscilacoes medias


from dbstock import DBHelper

# bot pra monitorar precos e situacoes no mercado

import json      #modulo que faz comunicacao com o python
import requests
import time
import urllib #lida com caracteres especiais

import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import re
import os
import traceback

from datetime import datetime
conn = sqlite3.connect('dw_stock_data')
plt.figure(figsize=(16,9))


#global variables
TOKEN = "977165415:AAEXEkUgbDiOoEkzXgxRlyicAvGad-MT6v4"
URL = "https://api.telegram.org/bot{}/".format(TOKEN)

alpha_key = 'HV7G47I5ENZV85XG'
request_session = requests.session()

#alpha vantage endpoints
url_intraday = 'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={}&interval={}&apikey={}'
url_daily = 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={}&apikey={}'
url_search = 'https://www.alphavantage.co/query?function=SYMBOL_SEARCH&keywords={}&apikey={}'


emoji1 = u'\U000027A1'   #seta pra direita
db = DBHelper()

def get_url(url):
    try:
        response = requests.get(url)
    except:
        print("problema com o request")
        return
    content = response.content.decode("utf8")
    return content


#maneira de obter conteudo do telegram e converte-lo pra python
def get_json_from_url(url):
    content = get_url(url)
    try:
        js = json.loads(content)
    except:
        print("Deu pau no json")
        return
    return js


#offset trabalha com o numero sequencial das msgs, dar como argumento um update_id
#faz com que o update seja lido a partir daquela msg
def get_updates(offset=None):
    t1 = time.process_time()
    while True:
        t2 = time.process_time()
        url = URL + "getUpdates?timeout=100"
        if offset:
            url += "&offset={}".format(offset)
        js = get_json_from_url(url)
        if t2 - t1 > 0.02:
            return js
        try:
            if len(js["result"]) == 0:
                continue
        except:
            print('deu pau na leitura do json...')
            continue
        else:
            return js


def get_last_update_id(updates):
    update_ids = []
    for update in updates["result"]:
        update_ids.append(int(update["update_id"]))
    return max(update_ids)


def general_handler(updates, num_updates, chat):
    if num_updates > 1:
        print('bla')
        # print("agora sei lidar com mais de 1 mensagem")
        # for update in updates["result"]:
        #     content = []
        #     if 'text' in update["message"]:#checa se existe a key 'text' no dict
        #         content.append(str(update["message"]["text"]))
        #     else:
        #         print("nao sei lidar com updates q nao sao textos ainda :(")
        #         continue
        # return
    elif num_updates == 1:
        text = "Diga o que vc deseja:"
        options = ["Setar Watchlist","Ver Graficos","Atualizar precos"]
        keyboard = build_keyboard(options)
        send_message(text,chat,keyboard)
        last_update_id = get_last_update_id(updates) + 1
        updates = get_updates(last_update_id)
        try:
            if updates["result"][0]["message"]["text"] == "Setar Watchlist":
                last_update_id = watchlist(updates, chat)
                return last_update_id
            elif updates["result"][0]["message"]["text"] == "Ver Graficos":
                get_charts(updates, chat)
            elif updates["result"][0]["message"]["text"] == "Atualizar precos":
                update_stock_prices(updates, chat)
        except:
            print('No updates')
    return


def watchlist(updates, chat):
    while True:
        items = db.get_items(chat)
        options = ['Ver','Pronto']
        keyboard = build_keyboard(options)
        send_message("Diga o que voce quer: 'Ver' para ver a lista e checar items feitos ou digite o novo item (Digite 'Pronto' para sair)",chat,keyboard)
        last_update_id = get_last_update_id(updates) + 1
        updates = get_updates(last_update_id)
        if len(updates["result"]) == 0:
            return last_update_id
        text = updates["result"][0]["message"]["text"]
        if text == 'pronto' or text == 'Pronto':
            return last_update_id
        elif text == "Ver":
            keyboard = build_keyboard(items)
            send_message("Check the items done", chat, keyboard)
            last_update_id = get_last_update_id(updates) + 1
            updates = get_updates(last_update_id)
            if len(updates["result"]) == 0:
                return last_update_id
            elif updates["result"][0]["message"]["text"] == 'pronto' or updates["result"][0]["message"]["text"] == 'Pronto':
                continue
            else:
                text = updates["result"][0]["message"]["text"]
                db.delete_item(text, chat)
                continue
        else:
            db.add_item(text, chat)
            items = db.get_items(chat)
            message = formating2(items)
            send_message(message, chat)


def update_stock_prices(updates, chat):
    items = db.get_items(chat)
    try:
        stock_data = yf.download(items,
                                period='1mo',
                                interval='15m',
                                group_by='ticker'
                                )
        table_name = 'tabela_cotacoes_mensal'+datetime.today().strftime('%m%d')
        stock_data.to_sql(name=table_name, con=conn, if_exists='replace')
    except:
        send_message('algum nome errado de acao',chat)


def get_charts(updates, chat):
    items = db.get_items(chat)

    keyboard = build_keyboard(items)
    send_message('Diga qual acao voce deseja ver o grafico:',chat,keyboard)
    last_update_id = get_last_update_id(updates) + 1
    updates = get_updates(last_update_id)

    item = updates["result"][0]["message"]["text"]
    
    try:
        data = json.loads(request_session.get(url=url_intraday.format(item,'5min',alpha_key)).content)
    except:
        send_message('algum problema no request',chat)

    time_span = list(data)[1] #primeiro elemento sao metadados

    open = []
    high = []
    low = []
    close = []

    for i in list(data[time_span])[0:5]:
        open.append(data[time_span][i]['1. open'])
        high.append(data[time_span][i]['2. high'])
        low.append(data[time_span][i]['3. low'])
        close.append(data[time_span][i]['4. close'])

    fig = go.Figure(data=[go.Candlestick(x=list(data.get(time_span))[0:5],
                                        open=open,
                                        high=high,
                                        low=low,
                                        close=close
                                        )
                        ]
                    )
    fig = fig.update_layout(xaxis_rangeslider_visible=False)
    
    print('gerou figura')

    try:
        fig.write_image('temp_chart.png')
    except Exception:
        traceback.print_exc()
    
    send_image(chat)
    # os.remove('temp_chart.png'


def rename(column):
    new_column = re.sub(r"(\'|\(|\)|,|\s|sa)",r"",re.sub(r"\.","_",column.lower()))
    return new_column


def get_latest(updates,chat):
    items = db.get_items(chat)
    stocks = pd.read_sql_query('select * from tabela_cotacoes_mensal limit 50', con=conn).round(2)

    stocks = stocks.rename(columns=rename)

    keyboard = build_keyboard(items)
    send_message('Diga de qual acao voce deseja ver os ultimos precos:',chat,keyboard)
    last_update_id = get_last_update_id(updates) + 1
    updates = get_updates(last_update_id)

    item = updates["result"][0]["message"]["text"]

    # columns = [col for col in stocks.columns if item2 in columns]


def monitoring(updates,chat):
    items = db.get_items(chat)

    stock_data = yf.download(items,
                         period='1d',
                         interval='5m',
                         group_by='ticker'
                         ).round(2)
    
    stock_data_recent = stock_data.tail(2)

    index_column = [i for i in range(len(stock_data_recent.index))]

    stock_data_recent2 = stock_data_recent.set_index(pd.Index(index_column))
    stock_data_recent2['datetime'] = stock_data_recent.index

    stock_list = []

    for stock in items:
        if abs(stock_data_recent2.loc[0,(stock,'Close')] - stock_data_recent2.loc[0,(stock,'Open')] +
           stock_data_recent2.loc[1,(stock,'Close')] - stock_data_recent2.loc[1,(stock,'Open')]) > 0.04:
           stock_list.append(stock)

    lines = []
    for stock in stock_list:
        # column_stock = stock_data.loc[:,(stock,'Close')].values
        # column_datetime = stock_data.index.values.astype(str)
        # column_stock2 = [datetime.datetime.strptime(i[:16],"%Y-%m-%dT%H:%M") for i in column_array]
        line = stock_data_recent2.loc[0,('datetime')] + stock_data_recent2.loc[0,(stock,'Open')] + stock_data_recent2.loc[0,(stock,'Close')]
        lines.append(line)


def send_image(chat):
    files = {'photo': open('temp_chart.png','rb')}
    data = {'chat_id': chat}
    r = requests.post('https://api.telegram.org/bot977165415:AAEXEkUgbDiOoEkzXgxRlyicAvGad-MT6v4/sendPhoto',
                  files=files,
                  data = data)


# files = {'photo': open('./saved/{}.jpg'.format(user_id), 'rb')}
# status = requests.post('https://api.telegram.org/bot<TOKEN>/sendPhoto?chat_id={}'.format(chat_id), files=files)


def send_message(text,chat_id,reply_markup=None):
    text = urllib.parse.quote_plus(text)
    url = URL + "sendMessage?text={}&chat_id={}".format(text, chat_id)
    if reply_markup:
        url += "&reply_markup={}".format(reply_markup)
    get_url(url)


def formating2(text):
    content = ''
    for i in text:
        try:
            i = '\n' + emoji1 + i
        except:
            i = str(i)
            i = '\n' + emoji1 + i
        content = content + i
    return content


def formating(text,chat_id,reply_markup=None):
    content = ''
    len_total = 0
    limit = 3500
    i0 = 0
    for i in text:
        len_total = len_total + len(i)
    if len_total < limit:
        for i in text:
            if i:
                try:
                    i = '\n' + emoji1 + i
                except:
                    i = str(i)
                    i = '\n' + emoji1 + i
            content = content + i
        send_message(content,chat_id,reply_markup)
    elif len_total > limit:
        for i in text:
            if i:
                try:
                    i = '\n' + emoji1 + i
                except:
                    i = str(i)
                    i = '\n' + emoji1 + i
                content = content + i
        n = int(len_total/limit)
        while i0 <= n:
            i1 = i0 + 1
            partial_msg = content[i0*limit:i1*limit]
            send_message(partial_msg,chat_id,reply_markup)
            i0 = i1
    return


def build_keyboard(items):
    keyboard = [[str(item)] for item in items]
    reply_markup = {"keyboard":keyboard, "one_time_keyboard":True}
    return json.dumps(reply_markup)


def main():
    db.setup_stocklist()
    time_abs_ref = time.time() #secs since epoch
    last_update_id = None
    interval = 540.0 #[sec]
    while True:
        time_abs_now = time.time()
        updates = get_updates(last_update_id)
        try:
            length = len(updates["result"])
        except:
            print("Deu problema no update")
            return
        if time_abs_now > time_abs_ref + interval:
            chat = updates["result"][0]["message"]["chat"]["id"]
            monitoring(updates,chat)
            time_abs_ref = time_abs_now
        if length > 0:
            try:
                chat = updates["result"][0]["message"]["chat"]["id"]
                general_handler(updates, length, chat)
                last_update_id = get_last_update_id(updates) + 1
            except:
                print('nao foi possivel processar o update')
        else:
            time.sleep(0.5)
            continue


if __name__ == '__main__':
    main()
