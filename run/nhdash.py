#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd2in13_V2
from nicehash_creds import api_info
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

#START NICEHASH
import requests
import sched
from time import mktime, sleep
from datetime import datetime
from dateutil import tz
#import string
import uuid
import hmac
import json
from hashlib import sha256

LOG_FILE = "/var/log/nhpy.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

logging.basicConfig(filename=LOG_FILE,format=LOG_FORMAT,level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG)

#base variables    
from_zone = tz.gettz('UTC')
to_zone = tz.gettz('America/Denver')
query=''

def get_epoch_ms_from_now():
    now = datetime.now()
    now_ec_since_epoch = mktime(now.timetuple()) + now.microsecond / 1000000.0
    return int(now_ec_since_epoch * 1000)

def construct_request(endpoint): 
    xtime = get_epoch_ms_from_now()
    xnonce = str(uuid.uuid4())

    #construct bytearray for xauth string for private API
    priv_params = bytearray(str(api_info.api_key), 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray(str(xtime), 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray(xnonce, 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray(api_info.org_id, 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray('GET', 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray(endpoint, 'utf-8')
    priv_params += bytearray('\x00', 'utf-8')
    priv_params += bytearray(query, 'utf-8')
        
    xauth = hmac.new(bytearray(api_info.api_secret,'utf-8'), priv_params, sha256).hexdigest()
        
    headers = { 'Content-Type': 'application/json',
                'Authorization': 'Bearer {0}'.format(api_info.api_key),
                'X-Time': str(xtime),
                'X-Nonce': xnonce,
                'X-Organization-Id': api_info.org_id,
                'X-Auth': api_info.api_key + ":" + xauth,
                'X-Request-Id': str(uuid.uuid4())}
    return headers

def get_nh_stats():
    fail = True;
    while fail:
        response = requests.get(api_info.api_url_base + api_info.api_rig_path, headers=construct_request(api_info.api_rig_path))
        if response.status_code == 200:
            fail = False
            return json.loads(response.content.decode('utf-8'))
        else:        
            logging.info("Error response: " + str(response.status_code))
            show_error(response.status_code)
            time.sleep(30)
    
def return_nh_stats():
    fail = True;
    while fail:
        nh_stats = get_nh_stats()
        balance = requests.get(api_info.api_url_base + api_info.api_accounting_path, headers=construct_request(api_info.api_accounting_path))
        if balance.status_code == 200:
            balance = json.loads(balance.content.decode('utf-8'))
            balance_btc = round(float(balance['totalBalance']),5)
        else:
            balance_btc = 0
            
        prices = requests.get(api_info.api_url_base + api_info.api_exchange_path, headers=construct_request(api_info.api_exchange_path))

        if prices.status_code == 200:
            prices_all = json.loads(prices.content.decode('utf-8'))
            btc_price = prices_all['BTCUSDC']
        else:
            btc_price = 50000.00

        balance_usd = float(balance_btc) * btc_price
        profit_btc = nh_stats['totalProfitability']
        profit_usd = profit_btc * btc_price;

        next_pay = datetime.strptime(nh_stats['nextPayoutTimestamp'], '%Y-%m-%dT%H:%M:%SZ')
        next_pay = next_pay.replace(tzinfo=from_zone)
        next_pay_mt = next_pay.astimezone(to_zone)
        time_now = datetime.now().astimezone(to_zone);
        
        time_to_pay = next_pay - time_now;
        pay_hours, remainder = divmod(time_to_pay.seconds, 3600)
        pay_minutes, seconds = divmod(remainder, 60)
        next_pay_in = '{:2}h {:2}m'.format(int(pay_hours), int(pay_minutes))
        rt_profit = "$" + str(round(profit_usd,2))
        
        if 'MINING' not in nh_stats['minerStatuses']:
            logging.info("No Miner Data")
            show_error('no data')
            logging.info("LN 126 - Sleep 30") 
            time.sleep(30)
        else:
            fail = False
        
    num_mining = nh_stats['minerStatuses']['MINING']
    num_devices = nh_stats['devicesStatuses']['MINING']
    unpaid_btc = nh_stats['unpaidAmount']
    unpaid_usd = float(unpaid_btc) * float(btc_price)
    stats_array = {"rtprofit": rt_profit + "/day",
                   "btcprice": "${:,}".format(int(btc_price)) + "/BTC",
                   "activew": str(num_mining),
                   "actived": str(num_devices),
                   "unpaid": "$" + str(round(unpaid_usd,2)),
                   "nextpay": next_pay_in,
                   "balancebtc": str(balance_btc) +" BTC",
                   "balanceusd": "$" + str(round(balance_usd))}
    return stats_array
    
def fetch_nh(sc): 
    statsNow = return_nh_stats()
    updatedTime = datetime.now().strftime("%l:%M:%P")
    #uncomment below to see console output 
    #print(statsNow["rtprofit"])
    #print(statsNow["btcprice"])
    #print("Active Workers: " + statsNow["activew"])
    #print("Unpaid: " + statsNow["unpaid"])
    #print("Payout in: "+ statsNow["nextpay"])
    #print("Updated : " + updatedTime)
    perpetual_check.enter(120, 1, fetch_nh, (sc,))
    try:
        epd.init(epd.PART_UPDATE)
        # set fonts
        font15 = ImageFont.truetype(os.path.join(picdir, 'Roboto-Thin.ttf'), 15)
        font17 = ImageFont.truetype(os.path.join(picdir, 'Roboto-Thin.ttf'), 17)
        font24 = ImageFont.truetype(os.path.join(picdir, 'Roboto-Regular.ttf'), 24)
        font24B = ImageFont.truetype(os.path.join(picdir, 'Roboto-Bold.ttf'), 24)

        image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame    
        draw = ImageDraw.Draw(image)
        
        draw.rectangle([(0,0),(165,81)],fill = 0)
        draw.rectangle([(0,84),(255,122)],fill = 0)
        draw.line([(164,0),(164,122)], fill = 0,width = 2)
        draw.text((8, 10), statsNow["rtprofit"], font = font24B, fill = 1)
        draw.text((8, 43), statsNow["btcprice"], font = font24B, fill = 1)
        draw.text((8, 90), statsNow["balancebtc"] + " / " + statsNow["balanceusd"], font = font24, fill = 1)
        draw.text((172, 8), "@" + updatedTime, font = font15, fill = 0)
        draw.text((172, 26), "actv: " + statsNow["activew"] + " / " + statsNow["actived"], font = font15, fill = 0)
        draw.text((172, 44), "pnd: " + statsNow["unpaid"], font = font15, fill = 0)
        draw.text((172, 62), "in" + statsNow["nextpay"], font = font15, fill = 0)
        #draw.text((78, 93), "paying out in:" + statsNow["nextpay"], font = font17, fill = 1)
        image = image.transpose(Image.ROTATE_180)
        epd.displayPartial(epd.getbuffer(image))
        
    except IOError as e:
        logging.info(e)
    
    except KeyboardInterrupt:    
        logging.info("ctrl + c:")
        epd2in13_V2.epdconfig.module_exit()
        exit()

def show_error(status):
    logging.info("SHOW ERROR - status: " + str(status))
    epd = epd2in13_V2.EPD()
    epd.init(epd.PART_UPDATE)
    font24 = ImageFont.truetype(os.path.join(picdir, 'Roboto-Regular.ttf'), 24)

    image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame    
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0,84),(255,122)],fill = 0)
    draw.text((8, 90), str(status) + " Error from API", font = font24, fill = 1)
    image = image.transpose(Image.ROTATE_180)
    epd.displayPartial(epd.getbuffer(image))
    return 

epd = epd2in13_V2.EPD()
epd.init(epd.FULL_UPDATE)
epd.Clear(0xFF)
perpetual_check = sched.scheduler(time.time, time.sleep)
perpetual_check.enter(0, 1, fetch_nh, (perpetual_check,))
perpetual_check.run()

#END NICEHASH