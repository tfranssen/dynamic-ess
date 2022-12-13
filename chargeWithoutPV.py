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

import requests, datetime, pytz, base64, time, logzero, schedule
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import paho.mqtt.client as mqtt
from logzero import logger

global dfPrices, flagConntected, lowChargeLimit, dateToday, tz, plotImage, defaultGridSetpoint, chargingGridSetpoint, password, vrmID, username, lastChargeCondition
from secret import password, vrmID, username

# Settings
lowChargeLimit = 0.8
dateToday = 1; # If 1, date is today, if 0 date is tomorrow, for testing only
tz = "Europe/Amsterdam" # Time zone
plotImage = 1 # If true image get created
defaultGridSetpoint = 30 # Default grid point (Watt)
chargingGridSetpoint = 3000 # Charging grid point (Watt)
lastChargeCondition = 0

# Secrets
# vrmID = "" # VRM ID, if not imported from secret.py put it here
# username = "" #VRM Username, if not imported from secret.py put it here
# Save base64 encoded password to sectret.py. 
# For testing you can write your password here in plain text but not recommended
password = base64.b64decode(password).decode("utf-8") # Retrieve password from secrets.py

# Set up MQTT Broker
global client 

def on_connect(client, userdata, flags, rc):
    client.subscribe("$SYS/#")
    global flagConntected
    flagConntected = 1 
    logger.info("Broker connected.")

def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))
    
def on_publish(client, userdata, mid):
    logger.info("Message Published.")    
    
def on_disconnect(client, userdata, rc):
    global flagConntected
    flagConntected = 0  
    logger.info("Broker disconnected.")

client = mqtt.Client("client12312313")
flagConntected = 0
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish
client.on_disconnect = on_disconnect
client.tls_set("venus-ca.crt")
client.username_pw_set(username, password)       

# Declare logfile
logzero.logfile("log.log", maxBytes=1e6, backupCount=3)

# Calculate MQTT Broker URL
def calculateBroker(vrmID):
    sum2 = 0
    for character in vrmID.lower().strip():
        sum2 += ord(character)
    broker_index = sum2 % 128
    brokerURL = "mqtt{}.victronenergy.com".format(broker_index)
    return brokerURL

# Retrieve ANWB prices
def getPrices():
    # Retrieve prices
    global dfPrices, averagePrice
    if dateToday:
        dayString = "today"
    else:
        dayString = "tomorrow"
    # Set dates of interest in correct format for API
    fromDate = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)
    tillDate = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)+timedelta(days=1)-timedelta(seconds=1)
    if dateToday == 0:
        fromDate = fromDate+timedelta(days=1)
        tillDate = tillDate+timedelta(days=1)
    # Add time zone info to dates    
    fromDateTZ = fromDate.astimezone(pytz.timezone(tz))
    fromDateTZ = fromDateTZ.astimezone(pytz.utc)
    tillDateTZ = tillDate.astimezone(pytz.timezone(tz))
    tillDateTZ = tillDateTZ.astimezone(pytz.utc)
    # Reformat dates for correct format for API
    fromDateString = fromDateTZ.isoformat().replace("+00:00","Z")
    tillDateString = tillDateTZ.isoformat().replace("+00:00","Z")
    # Build API URL
    url = "https://api.energyzero.nl/v1/energyprices?fromDate=" + fromDateString + "&tillDate=" + tillDateString + "&interval=4&usageType=1&inclBtw=true"
    # Excecute API request
    prices = requests.get(url)
    pricesDoc = prices.json()
    # Add prices to Pandas dataframe
    dfPrices = pd.DataFrame.from_dict(pricesDoc["Prices"])
    # Convert strings to datetime
    dfPrices['readingDate'] = pd.to_datetime(dfPrices['readingDate'])
    # Add timezone info to dates and calculate local times
    dfPrices['localDate'] = dfPrices['readingDate'].dt.tz_convert(tz)
    # Calculate average price
    averagePrice = round(dfPrices["price"].mean()*100)/100
    # Add column with charge condition based on lower limit.
    dfPrices['chargeCondition'] = np.where((dfPrices['price'] < averagePrice*lowChargeLimit), True, False)
    logger.info("Now prices retrieved for " + dayString)
    logger.info("Average price is: €" + str(averagePrice))

    #Plot prices
    if plotImage:
        x = range(24)
        y = dfPrices.price.tolist()
        colors = ["red" if i <= averagePrice*lowChargeLimit else "blue" for i in y]
        plt.bar(x,y, color=colors)
        plt.xlim(-1,24)
        plt.grid(1)
        timestr = time.strftime("%Y - %m - %d")
        plt.title("Energy prices " + dayString + " " + timestr + ". Mean price: €" + str(round(dfPrices["price"].mean()*100)/100))
        plt.xlabel("Hour")
        plt.ylabel("Price (€)")
        plt.axhline(y=averagePrice, color="green")
        plt.axhline(y=averagePrice*lowChargeLimit, color="red")
        plt.legend(["Average", "Lower limit: " + str(lowChargeLimit), "Charging hours"])
        timestr = time.strftime("%Y%m%d")
        plt.savefig("plot-" + timestr + ".png")
        logger.info("New plot created and saved. Filename: " + "plot-" + timestr + ".png")

def updateController():
    global flagConntected, client, lastChargeCondition

    # Find current price and required charge condition
    now = datetime.now().replace(microsecond=0, second=0, minute=0)
    nowTZ = now.astimezone(pytz.timezone(tz))
    chargeConditionNow = dfPrices["chargeCondition"].loc[dfPrices['localDate'] == nowTZ].item()
    chargePriceNow = dfPrices["price"].loc[dfPrices['localDate'] == nowTZ].item()

    if chargeConditionNow != lastChargeCondition:
        logger.info("Requirement has changed, sending MQTT message to change setpoint.")

        # Control ESS over MQTT
        client.connect(calculateBroker(vrmID), 8883, keepalive=60)
        client.loop_start()

        # Wait for connecting
        while not flagConntected:
            time.sleep(1)

        if chargeConditionNow:
        # If the ESS should charge do this:        
            if flagConntected:
                client.publish("W/" + vrmID + "/settings/0/Settings/CGwacs/AcPowerSetPoint", '{"value":' + str(chargingGridSetpoint) + '}')
                logger.info("Current price is €" + str(chargePriceNow) + ". The average price today is €" + str(averagePrice) + ". This is lower than " + str(lowChargeLimit) + " * daily average so the battery is now charging.")
                lastChargeCondition = 1                
        else:
        # If the ESS should not charge do this:              
            if flagConntected:
                client.publish("W/" + vrmID + "/settings/0/Settings/CGwacs/AcPowerSetPoint", '{"value":' + str(defaultGridSetpoint) + '}')
                logger.info("Current price is €" + str(chargePriceNow) + ". The average price today is €" + str(averagePrice) + ". This is higher than " + str(lowChargeLimit) + " *  daily average. This is not low enough to start charging. ")
                lastChargeCondition = 0
        
        client.loop_stop()
    logger.info("Requirement has not changed. No MQTT message needed. ")     

# Set up scheduler
schedule.every().day.at("00:00:05").do(getPrices)
schedule.every(5).minutes.do(updateController)
logger.info("Script started.")
logger.info("Get prices is scheduled every day at 00:00:05.")
logger.info("The ESS controller is scheduled every 5 minutes.")

getPrices()
updateController()

def main():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()

