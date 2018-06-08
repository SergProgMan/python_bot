
# For trading

import os
import sys
import json
import requests
import urllib, http.client
import hmac, hashlib
import time
import TelegramParser

# Вписываем свои ключи
API_KEY = ''
API_SECRET = b''

CURRENCY_1 = None
CURRENCY_2 = 'btc'

ORDER_LIFE_TIME_BUY = 5  # через сколько секунд отменять неисполненный ордер на покупку CURRENCY_1
ORDER_LIFE_TIME_PART_BUY = 300  # через сколько секунд отменять частично исполненный ордер на покупку CURRENCY_1
ORDER_LIFE_TIME_SELL = 3600  # через 60 минут отменить орден на продажу
STOCK_FEE = 0.002  # Комиссия, которую берет биржа (0.002 = 0.2%)
OFFERS_AMOUNT = 1  # Сколько предложений из стакана берем для расчета средней цены
CAN_SPEND = 0.002  # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFIT_1 = 0.50  # Продажа после роста цены на 50 % (0.001 = 0.1%)
PROFIT_2 = 1.00  # Продажа после роста цены на 100%
DEBUG = True  # True - выводить отладочную информацию, False - писать как можно меньше

"""
    Каждый новый запрос к серверу должен содержать увеличенное число в диапазоне 1-2147483646
    Поэтому храним число в файле поблизости, каждый раз обновляя его. Создаем словарь, в котором по одному из
    ключей (nonce) храним это чило
"""

storage_file = "./storage_file"
if not os.path.exists(storage_file):
    with open(storage_file, 'w') as f:
        dic = {"currency" : None, "msg_od": None, "buy_price": None, "nonce": "1", "find_coin": False}
        json.dump(dict, f)

# Будем перехватывать все сообщения об ошибках с биржи
class ScriptError(Exception):
    pass
class ScriptQuitCondition(Exception):
    pass
        
def call_api(**kwargs):
    nonce_val = None
    # При каждом обращении к торговому API увеличиваем счетчик nonce на единицу
    with open(storage_file, 'w') as f:
        dic = json.load(f)
        nonce_val=int(dic[nonce])
        dic[nonce]=str(nonce_val+1)
        json.dump(dict, f)

    payload = {'nonce': nonce_val}

    if kwargs:
        payload.update(kwargs)
    payload =  urllib.parse.urlencode(payload)

    H = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
    H.update(payload.encode('utf-8'))
    sign = H.hexdigest()
    
    headers = {"Content-type": "application/x-www-form-urlencoded",
           "Key":API_KEY,
           "Sign":sign}
    conn = http.client.HTTPSConnection("yobit.io", timeout=60)
    conn.request("POST", "/tapi/", payload, headers)
    response = conn.getresponse().read()
    
    conn.close()

    try:
        obj = json.loads(response.decode('utf-8'))

        if 'error' in obj and obj['error']:
            raise ScriptError(obj['error'])
        return obj
    except json.decoder.JSONDecodeError:
        raise ScriptError('Ошибка анализа возвращаемых данных, получена строка', response)

def buy(CURR_PAIR):
    # CURRENCY_1 купить
    # Достаточно ли денег на балансе в валюте CURRENCY_2 (Баланс >= CAN_SPEND
    if float(balances.get(CURRENCY_2, 0)) >= CAN_SPEND:
        res = requests.get('https://yobit.net/api/3/ticker/ltc_btc') # получаем данные ticker'а
        res_obj = json.loads(res.text) # переводим полученный текст в объект с данными
        price_buy = res_obj['ltc_btc']['buy']                    
        my_amount = CAN_SPEND/price # рассчитываем количество которое можем купить
        print('buy: кол-во {amount:0.8f}, курс: {rate:0.8f}'.format(amount=my_amount, rate=price_buy))
        # Допускается ли покупка такого кол-ва валюты (т.е. не нарушается минимальная сумма сделки)
        new_order = call_api(method="Trade", pair=CURR_PAIR, type="buy", rate="{rate:0.8f}".format(rate=price), amount="{amount:0.8f}".format(amount=my_amount))['return']
        print(new_order)

        # Фиксируем цену покупки
        with open(storage_file, 'w') as f:
            dic = json.load(f)
            dic[buy_price] = str(price_buy)
            json.dump(dict, f)

        if DEBUG:
            print('Создан ордер на покупку', new_order['order_id'])
    else:
        raise ScriptQuitCondition('Выход, не хватает денег')
        
# Реализация алгоритма
def main_flow():
    CURRENCY_1 = None
    can_buy = False
    CURR_PAIR = None
    
    with open(storage_file, 'w') as f:
        dic = json.load(f)
        CURRENCY_1 = dic[currency]
        can_buy = dic[find_coin]
        CURR_PAIR = CURRENCY_1.lower() + "_" + CURRENCY_2.lower()
        if can_buy:
            buy(CURR_PAIR)
        dic[find_coin] = False
        json.dump(dict, f)


    
    try:
        # Получаем список активных ордеров
        opened_orders = []
        try:
            yobit_orders = call_api(method="ActiveOrders", pair=CURR_PAIR)['return']

            for order in yobit_orders:
                o = yobit_orders[order]
                o['order_id']=order
                opened_orders.append(o)
                
        except KeyError:
            if DEBUG:
                print('Открытых ордеров нет')

    
        sell_orders = []
        # Есть ли неисполненные ордера на продажу CURRENCY_1?
        for order in opened_orders:
            if order['type'] == 'sell':
                # Есть неисполненные ордера на продажу CURRENCY_1, выход
                raise ScriptQuitCondition('Выход, ждем пока не исполнятся/закроются все ордера на продажу (один ордер может быть разбит биржей на несколько и исполняться частями)')
            else:
                # Запоминаем ордера на покупку CURRENCY_1
                sell_orders.append(order)
                
        # Проверяем, есть ли открытые ордера на покупку CURRENCY_1
        if sell_orders:  # открытые ордера есть

            for order in sell_orders:
                # Проверяем, есть ли частично исполненные
                if DEBUG:
                    print('Проверяем, что происходит с отложенным ордером', order['order_id'])
                # Получаем состояние ордера, если он еще не исполнен, отменяем
                order_info = call_api(method="OrderInfo", order_id=order['order_id'])['return'][str(order['order_id'])]
                time_passed = time.time() - int(order['timestamp_created'])
                if order_info ['status'] == 0 and order_info['start_amount'] == order_info['amount']: # ордер не исполнен, по нему ничего не куплено
                    if time_passed > ORDER_LIFE_TIME_BUY:
                        # Ордер отменяем
                        call_api(method="CancelOrder", order_id=order['order_id'])
                        #buy(CURR_PAIR)
                        raise ScriptQuitCondition('Отменяем ордер: за ' + str(ORDER_LIFE_TIME_BUY) + ' секунд не удалось купить '+ str(CURRENCY_1)+' и сразу заключаем новую сделку на покупку')

                    else:
                        raise ScriptQuitCondition('Выход, продолжаем надеяться купить валюту по указанному ранее курсу, со времени создания ордера прошло %s секунд' % str(time_passed))
                else:
                    if time_passed > ORDER_LIFE_TIME_PART_BUY:
                        call_api(method="CancelOrder", order_id=order['order_id'])
                        Print("Отменяем частично выполненный орден на покупку, так как прошло"+str(ORDER_LIFE_TIME_PART_BUY)+"следующее собщение не брать во внимание")

                    raise ScriptQuitCondition('Ордер на покупку открыт, по нему были торги, ждем' + str(order_info))

                   
        elif CURRENCY_1:   # Открытых ордеров нет

            balances = call_api(method="getInfo")['return']['funds']
            # При каждом обращении к торговому API увеличиваем счетчик nonce на единицу
            b_price = None

            with open(storage_file, 'w') as f:
                dic = json.load(f)
                b_price = float(dic[buy_price])


            if float(balances.get(CURRENCY_1, 0)) > 0:  # Есть ли в наличии CURRENCY_1, которую можно продать?
                print('sell', balances[CURRENCY_1])
                new_order_1 = call_api(method="Trade", pair=CURR_PAIR, type="sell", rate="{rate:0.8f}".format(rate=float(buy_price+0.5*b_price)), amount="{amount:0.8f}".format(amount=0.5*balances[CURRENCY_1]))['return']
                print(new_order_1)
                new_order_2 = call_api(method="Trade", pair=CURR_PAIR, type="sell", rate="{rate:0.8f}".format(rate=float(b_price*2)), amount="{amount:0.8f}".format(amount=balances[CURRENCY_1]))['return']
                print(new_order_2)
                if DEBUG:
                    print('Создан ордер на продажу', CURRENCY_1, new_order['order_id'])
            else:
               
                raise ScriptQuitCondition('Нет активных ордеров - выходим')

        
    except ScriptError as e:
        print(e)
    except ScriptQuitCondition as e:
        print(e)
    except Exception as e:
        print("!!!!",e)

while(True):
    main_flow()
    time.sleep(1)

