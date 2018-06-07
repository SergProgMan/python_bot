import json
import requests

res = requests.get('https://yobit.net/api/3/ticker/ltc_btc') # получаем данные ticker'а
res_obj = json.loads(res.text) # переводим полученный текст в объект с данными

print("SELL: %0.8f" % res_obj['ltc_btc']['sell'])
print("BUY: %0.8f" % res_obj['ltc_btc']['buy'])
