#!/usr/bin/env python
# coding: utf-8

# Simple script for charging battery when prices are low
# In this scenario the battery will be charged when prices are x percent below the dialy average. 
# The limit can be set by the lowChargeLimit variable. 
# Default is 0.8, which means that charging will start when current price is 20% below the daily average. 
#
# To get this script working you need to provide (best to edit the secret.py file):
#  * vrmID
#  * password
#  * username
#  
#  Retrieving data is now only available for ANWB, other providers will be added later. 

import requests, datetime, pytz, base64, time
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from secret import password, vrmID, username
import paho.mqtt.client as mqtt

# Settings
lowChargeLimit = 0.8
dateToday = 1; # If 1, date is today, if 0 date is tomorrow, for testing only
tz = "Europe/Amsterdam" # Time zone
# vrmID = "" # VRM ID, if not imported from secret.py put it here
# username = "" #VRM Username, if not imported from secret.py put it here
# Save base64 encoded password to sectret.py. 
# For testing you can write your password here in plain text but not recommended
password = base64.b64decode(password).decode("utf-8") # Retrieve password from secrets.py
plotImage = 0 # If true image get created
defaultGridSetpoint = 30 # Default grid point (Watt)
chargingGridSetpoint = 3000 # Charging grid point (Watt)

# Calculate MQTT Broker URL
sum2 = 0
for character in vrmID.lower().strip():
    sum2 += ord(character)
broker_index = sum2 % 128
brokerURL = "mqtt{}.victronenergy.com".format(broker_index)

while True:

    # Retrieve prices
    fromDate = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)
    tillDate = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)+timedelta(days=1)-timedelta(seconds=1)
    if dateToday == 0:
        fromDate = fromDate+timedelta(days=1)
        tillDate = tillDate+timedelta(days=1)
    fromDateTZ = fromDate.astimezone(pytz.timezone(tz))
    fromDateTZ = fromDateTZ.astimezone(pytz.utc)
    tillDateTZ = tillDate.astimezone(pytz.timezone(tz))
    tillDateTZ = tillDateTZ.astimezone(pytz.utc)
    fromDateString = fromDateTZ.isoformat().replace("+00:00","Z")
    tillDateString = tillDateTZ.isoformat().replace("+00:00","Z")
    url = "https://api.energyzero.nl/v1/energyprices?fromDate=" + fromDateString + "&tillDate=" + tillDateString + "&interval=4&usageType=1&inclBtw=true"
    prices = requests.get(url)
    pricesDoc = prices.json()
    dfPrices = pd.DataFrame.from_dict(pricesDoc["Prices"])
    dfPrices['readingDate'] = pd.to_datetime(dfPrices['readingDate'])
    dfPrices['localDate'] = dfPrices['readingDate'].dt.tz_convert(tz)
    averagePrice = round(dfPrices["price"].mean()*100)/100
    dfPrices['chargeCondition'] = np.where((dfPrices['price'] < averagePrice*lowChargeLimit), True, False)

    #Plot prices
    if plotImage:
        x = range(24)
        y = dfPrices.price.tolist()
        colors = ["red" if i <= averagePrice*lowChargeLimit else "blue" for i in y]
        plt.bar(x,y, color=colors)
        plt.xlim(-1,24)
        plt.grid(1)
        if dateToday:
            dayString = "today"
        else:
            dayString = "tomorrow"
        plt.title("Energy prices " + dayString + ". Mean price: €" + str(round(dfPrices["price"].mean()*100)/100))
        plt.xlabel("Hour")
        plt.ylabel("Price (€)")
        plt.axhline(y=averagePrice, color="green")
        plt.axhline(y=averagePrice*lowChargeLimit, color="red")
        plt.legend(["Average", "Lower limit", "Charging hours"])
        plt.savefig('plot.png')

    # Find current price
    now = datetime.now().replace(microsecond=0, second=0, minute=0)
    nowTZ = now.astimezone(pytz.timezone(tz))
    chargeConditionNow = dfPrices["chargeCondition"].loc[dfPrices['localDate'] == nowTZ].item()
    chargePriceNow = dfPrices["price"].loc[dfPrices['localDate'] == nowTZ].item()

    # Control ESS over MQTT
    flag_connected = 0 
    def on_connect(client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        client.subscribe("$SYS/#")
        global flag_connected
        flag_connected = 1

    def on_message(client, userdata, msg):
        print(msg.topic+" "+str(msg.payload))
        
    def on_publish(client, userdata, mid):
        print("Message Published")
        
    def on_disconnect(client, userdata, rc):
        global flag_connected
        flag_connected = 0    
        
    client = mqtt.Client("client12312313")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_publish = on_publish
    client.on_disconnect = on_disconnect

    print("Connecting to broker")
    client.tls_set("venus-ca.crt")
    client.username_pw_set(username, password)
    client.connect(brokerURL, 8883, keepalive=60)
    client.loop_start()

    # Wait for connecting
    while not flag_connected:
        time.sleep(1)

    if chargeConditionNow:
        if flag_connected:
            client.publish("W/" + vrmID + "/settings/0/Settings/CGwacs/AcPowerSetPoint", '{"value":' + str(chargingGridSetpoint) + '}')
            print ("Current price is €" + str(chargePriceNow) + ". The average price today is €" + str(averagePrice) + ". This is lower then " + str(lowChargeLimit) + "* daily average so the battery is now charging.")
    else:
        if flag_connected:
            client.publish("W/" + vrmID + "/settings/0/Settings/CGwacs/AcPowerSetPoint", '{"value":' + str(defaultGridSetpoint) + '}')
            print ("Current price is €" + str(chargePriceNow) + ". The average price today is €" + str(averagePrice) + ". This is not low enough to start charging. ")

    client.loop_stop()
    time.sleep(300)
