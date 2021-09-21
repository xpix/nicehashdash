#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

import logging
from waveshare_epd import epd2in7
from waveshare_epd import api_info
import time
from PIL import Image,ImageDraw,ImageFont
import traceback

#START NICEHASH
import requests
import sched
from time import mktime, sleep
from datetime import datetime
from dateutil import tz
import pytz
import tzlocal
import pprint

# USD -> EUR
from currency_converter import CurrencyConverter

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
to_zone = tz.gettz('Europe/Berlin')
query=''

old_totalHashRate = 0

pp = pprint.PrettyPrinter(indent=4)

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


def getUrl(url, params):
        try:
            response = requests.get(url, headers=params)
        except requests.exceptions.RequestException as e:
            print ("OOps: Connection Error",e)
        else:
            if response.status_code == 200:
               return json.loads(response.content.decode('utf-8'))
         
        
        return None
        
   

def HashRate():
    global old_totalHashRate
    totalHashRate = 0
    rigsHashRate = []
    for rig in api_info.rigs_api:
        rig_vals = getUrl(rig, construct_request(rig))
        if not rig_vals:
            continue

        totalHashRate += rig_vals['total_hashrate_raw']
        
        rigsHashRate.append({
           "totalHashRate"     : rig_vals['total_hashrate_raw'],
           "totalPowerUsage"   : rig_vals['total_power_usage']
        }) 

    if old_totalHashRate > 0 and (old_totalHashRate - totalHashRate) > 10:
        send_email('xpixer@gmail.com', 
                   "Attention: Mining rig has less %d MH/s" % (old_totalHashRate - totalHashRate), 
                   "Totalhasrate: %s : old_totalHashRate %s" % (totalHashRate, old_totalHashRate)
        )
    old_totalHashRate = totalHashRate


    return {
            "totalHashRate" : str(round(totalHashRate/1000000, 2)),
            "rigsHashRate"  : rigsHashRate
           }
    
def return_nh_stats():
    fail = True;
    c = CurrencyConverter()
    while fail:
        # rate from dollar to euro
        eur = c.convert(1, 'USD', 'EUR')
 
        # get nicehash stats from there api
        nh_stats = getUrl(api_info.api_url_base + api_info.api_rig_path, construct_request(api_info.api_rig_path))
        if not nh_stats:
            continue

        # pp.pprint(nh_stats)

        balance_btc = 0
        balance = getUrl(api_info.api_url_base + api_info.api_accounting_path, construct_request(api_info.api_accounting_path))
        if not balance:
            continue
        balance_btc = '{:f}'.format(float(balance['totalBalance']))

        btc_price = 50000.00
        prices_all = getUrl(api_info.api_url_base + api_info.api_exchange_path, construct_request(api_info.api_exchange_path))
        if not prices_all:
            continue
        # pp.pprint(prices_all)
        btc_price = prices_all['BTCUSDC']
        

        balance_usd = float(balance_btc) * btc_price
        profit_btc = nh_stats['totalProfitabilityLocal']
        profit_usd = profit_btc * btc_price;

        next_pay = datetime.strptime(nh_stats['nextPayoutTimestamp'], '%Y-%m-%dT%H:%M:%SZ')
        next_pay = next_pay.replace(tzinfo=from_zone)
        next_pay_mt = next_pay.astimezone(to_zone)
        time_now = datetime.now(pytz.utc).astimezone(tzlocal.get_localzone())

        time_to_pay = next_pay - time_now;
        pay_hours, remainder = divmod(time_to_pay.seconds, 3600)
        pay_minutes, seconds = divmod(remainder, 60)
        next_pay_in = '{:02}:{:02}'.format(int(pay_hours), int(pay_minutes))
        rt_profit = str(round(profit_usd * eur,2)) + u"\N{euro sign}"
        
        # get speedAccepted
        speedAccepted = 0
        for rig in nh_stats['miningRigs']:
            speedAccepted += rig['stats'][0]['speedAccepted']
        
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

    hashrate = HashRate();

    stats_array = {
                   "rtprofit": rt_profit + "/day",
                   "btcprice": "${:,}".format(int(btc_price)) + "/BTC",
                   "activew": str(num_mining),
                   "actived": str(num_devices),
                   "unpaid": str(round(unpaid_usd * eur,2)) + u"\N{euro sign}",
                   "nextpay": next_pay_in,
                   "balancebtc": str(balance_btc) +" BTC",
                   "balanceusd": str(round(balance_usd * eur,2)) + u"\N{euro sign}",
                   "speedAccepted" : str(round(speedAccepted, 2)) + " MH/s",
                   "totalHashRate" : hashrate['totalHashRate'] + "MH/s",
                   "rigs"  : hashrate['rigsHashRate']
                   } 
    return stats_array
    
def fetch_nh(sc): 
    statsNow = return_nh_stats()
    updatedTime = datetime.now().strftime("%H:%M")
    perpetual_check.enter(120, 1, fetch_nh, (sc,))
    try:
        epd.init() #epd.PART_UPDATE)
        # set fonts
        font15  = ImageFont.truetype(os.path.join(picdir, 'Roboto-Thin.ttf'), 15)
        font15B = ImageFont.truetype(os.path.join(picdir, 'Roboto-Bold.ttf'), 15)

        font17  = ImageFont.truetype(os.path.join(picdir, 'Roboto-Regular.ttf'), 17)
        font17B = ImageFont.truetype(os.path.join(picdir, 'Roboto-Bold.ttf'), 17)

        font24  = ImageFont.truetype(os.path.join(picdir, 'Roboto-Regular.ttf'), 24)
        font24B = ImageFont.truetype(os.path.join(picdir, 'Roboto-Bold.ttf'), 24)

        image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame    
        draw = ImageDraw.Draw(image)
        
        draw.rectangle([(0,0),(165,81)],fill = 0)
        draw.rectangle([(0,84),(264,122)],fill = 0)
        draw.rectangle([(0,125),(264,176)],fill = 1)
        draw.line([(164,0),(164,122)], fill = 0,width = 2)

        draw.text((8, 10), statsNow["rtprofit"], font = font24B, fill = 1)
        draw.text((8, 43), statsNow["totalHashRate"], font = font24B, fill = 1)
        #draw.text((8, 90), "Balance: " + statsNow["balanceusd"], font = font24B, fill = 1)
        draw.text((8, 90), statsNow["balancebtc"] + " / " + statsNow["balanceusd"], font = font24B, fill = 1)

        ypixel = 128
        for rig in statsNow["rigs"]:
            # pp.pprint(rig)
            draw.text((8,   ypixel), str(round(rig["totalHashRate"]/1000000, 2)) + "MH/s", font = font17B, fill = 0)
            draw.text((172, ypixel), str(rig["totalPowerUsage"]) + "W", font = font17B, fill = 0)
            ypixel += 20
            

        draw.text((172, 4), updatedTime, font = font24B, fill = 0)
        draw.text((172, 30), "activ: " + statsNow["activew"] + "/" + statsNow["actived"], font = font15B, fill = 0)
        draw.text((172, 45), "upaid: " + statsNow["unpaid"], font = font15B, fill = 0)
        draw.text((172, 60), "nxpay: " + statsNow["nextpay"], font = font15B, fill = 0)
        epd.display(epd.getbuffer(image))
        
    except IOError as e:
        logging.info(e)
    
    except KeyboardInterrupt:    
        logging.info("ctrl + c:")
        epd2in7.epdconfig.module_exit()
        exit()

def show_error(status):
    logging.info("SHOW ERROR - status: " + str(status))
    epd = epd2in7.EPD()
    epd.init() #epd.PART_UPDATE)
    font24 = ImageFont.truetype(os.path.join(picdir, 'Roboto-Regular.ttf'), 24)

    image = Image.new('1', (epd.height, epd.width), 255)  # 255: clear the frame    
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0,84),(255,122)],fill = 0)
    draw.text((8, 90), str(status) + " Error from API", font = font24, fill = 1)
    #image = image.transpose(Image.ROTATE_180)
    epd.display(epd.getbuffer(image))
    return 

def send_email(recipient, subject, body):
    import smtplib

    FROM = 'your@mining.rig'
    TO = recipient if isinstance(recipient, list) else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.ehlo()
        server.starttls()
        server.login(os.environ.get('GMAILUSR'), os.environ.get('GMAILPWD'))
        server.sendmail(FROM, TO, message)
        server.close()
        print 'successfully sent the mail'
    except:
        print "failed to send mail"


epd = epd2in7.EPD()
epd.init() #epd.FULL_UPDATE)
#epd.Clear(0xFF)
perpetual_check = sched.scheduler(time.time, time.sleep)
perpetual_check.enter(0, 1, fetch_nh, (perpetual_check,))
perpetual_check.run()

#END NICEHASH
