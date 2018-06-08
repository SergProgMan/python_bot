from telethon import TelegramClient
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.tl.functions.channels import GetMessagesRequest
from telethon.tl.functions.messages import GetHistoryRequest, ReadHistoryRequest
from telethon.utils import InputPeerChannel

import json

api_id = 240334                  # API ID (получается при регистрации приложения на my.telegram.org)
api_hash = "0f9197ade9ccb29595ca1779e4631e48"              # API Hash (оттуда же)
phone_number = "+380500770259"    # Номер телефона аккаунта, с которого будет выполняться код
channel = "https://t.me/cryptopiapumps2018"

client = TelegramClient('your_account', api_id, api_hash)
client.connect()
if not client.is_user_authorized():
    client.send_code_request(phone_number)
    client.sign_in(phone_number, input('Enter the code (phone_number): '))
chat_entity = client.get_entity(channel)
msgs = client.get_messages(chat_entity, limit=5)

for msg in reversed(msgs.data):
    # print(type(msg.message))
    if type(msg.message) == str and "COIN:" in msg.message and "💎" in msg.message:
        print("Find coin!")
        cutt_start = None
        bool_first = True
        i = 0
        for letter in msg.message:
            if letter == "💎" and bool_first == True:
                cutt_start = i + 1
                bool_first = False
            elif letter == "💎" and bool_first != True:
                cutt_stop = i
                coin = msg.message[cutt_start:cutt_stop].strip()
                print(coin)
                print(msg.id)
                if check_id_message(msg.id):
                    return coin
            i = i + 1
return None

def check_id_message(new_id):
    with open(storage_file, 'w') as f:
        dic = json.load(f)
        old_id=int(dic[msg_id])
        if new_id > old_id:
            dic[msg_id]=str(new_id)
            json.dump(dict, f)
            return True
        else:
            return False
