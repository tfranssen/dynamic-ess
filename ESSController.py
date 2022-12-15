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

import requests, datetime, pytz, base64, time, logzero, schedule, xmltodict
from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import paho.mqtt.client as mqtt
from logzero import logger

global dfPrices, flagConntected, lowChargeLimit, dateToday, tz, plotImage, defaultGridSetpoint, chargingGridSetpoint, password, vrmID, username, lastChargeCondition, PV, locLat, locLong, angle, direction , totPower
from secret import password, vrmID, username

# Settings
lowChargeLimit = 0.8
dateToday = 1; # If 1, date is today, if 0 date is tomorrow, for testing only
tz = "Europe/Amsterdam" # Time zone
plotImage = 1 # If true image get created
defaultGridSetpoint = 30 # Default grid point (Watt)
chargingGridSetpoint = 3000 # Charging grid point (Watt)
lastChargeCondition = 0
provider = 1 #0 = ANWB, 1 = ENTSOE

#PV Settings
PV = 0 # if PV = 1, PV Aware charging is enabled. PV = 0 is off
locLat = "51.33.36" #Latitude
locLong = "5.5.60" #Longitude
angle = 40 # Angle of your panels 0 (horizontal) … 90 (vertical)
direction = 90 # Plane azimuth, -180 … 180 (-180 = north, -90 = east, 0 = south, 90 = west, 180 = north)
totPower = 3 # installed modules power in kilo watt

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

# Retrieve prices
def getPrices():
    if dateToday:
        dayString = "today"
    else:
        dayString = "tomorrow"
    #In case of ANWB
    if provider == 0:
        # Retrieve prices
        global dfPrices, averagePrice
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
        try:
            prices = requests.get(url)
        except Exception as e:
            logger.error("Can't retrieve prices.")
            return
        try:
            pricesDoc = prices.json()
        except Exception as e:
            logger.exception(e)
            logger.error("Can't retrieve prices.")
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
        logger.info("Average price is: €" + '%.2f' % averagePrice)
    
    # In case of ENTSOE
    if provider == 1:
        from secret import entsoeKey
        fromDate = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)
        tillDate = datetime.now().replace(microsecond=0, second=0, minute=0, hour=0)+timedelta(days=1)
        if dateToday == 0:
            fromDate = fromDate+timedelta(days=1)
            tillDate = tillDate+timedelta(days=1)
        fromDateTZ = fromDate.astimezone(pytz.timezone(tz))
        fromDateTZ = fromDateTZ.astimezone(pytz.utc)
        tillDateTZ = tillDate.astimezone(pytz.timezone(tz))
        tillDateTZ = tillDateTZ.astimezone(pytz.utc)
        fromDateString = fromDateTZ.strftime("%Y%m%d%H%M")
        tillDateString = tillDateTZ.strftime("%Y%m%d%H%M")
        url = "https://transparency.entsoe.eu/api?documentType=A44&in_Domain=10YNL----------L&out_Domain=10YNL----------L&periodStart="+fromDateString+"&periodEnd="+tillDateString+"&securityToken=" + entsoeKey
        try:
            prices = requests.get(url)
        except Exception as e:
            logger.error("Can't retrieve prices.")
            return
        try:
            dict_data = xmltodict.parse(prices.content)
        except Exception as e:
            logger.exception(e)
            logger.error("Can't retrieve prices.")
        dict_data["Publication_MarketDocument"]["TimeSeries"]["Period"]["Point"]
        dfPrices = pd.DataFrame.from_dict(dict_data["Publication_MarketDocument"]["TimeSeries"]["Period"]["Point"])
        dfPrices['localDate'] = pd.to_datetime(datetime.now().replace(microsecond=0, second=0, minute=0, hour=0), utc=True) + dfPrices.position.astype('timedelta64[h]')-timedelta(hours=2)
        dfPrices['localDate'] = dfPrices['localDate'].dt.tz_convert(tz)
        dfPrices = dfPrices.astype({"price.amount": float})
        dfPrices['price.amount'] = dfPrices['price.amount'].div(1000).round(2)
        dfPrices.rename(columns={'price.amount': 'price'}, inplace=True)
        dfPrices.drop('position', axis=1, inplace=True)
        averagePrice = round(dfPrices["price"].mean()*100)/100
        dfPrices['chargeCondition'] = np.where((dfPrices['price'] < averagePrice*lowChargeLimit), True, False)
        logger.info("Now prices retrieved for " + dayString)
        logger.info("Average price is: €" + str(averagePrice))

    if PV:
        url = "https://api.forecast.solar/estimate/"+str(locLat)+"/"+str(locLong)+"/"+str(angle)+"/"+str(direction)+"/"+str(totPower)+"?no_sun=1"
        try:
            pvInfo = requests.get(url)
        except Exception as e:
            logger.error("Can't retrieve PV info.")
            return
        try:
            pvInfoDoc = pvInfo.json()
        except Exception as e:
            logger.error("Can't retrieve PV info.")
            return
        dfPVInfo = pd.DataFrame.from_dict(pvInfoDoc["result"]["watt_hours_period"],orient="index",columns=["wattHours"])
        dfPVInfo.reset_index(inplace=True)
        dfPVInfo.rename(columns={'index': 'date'}, inplace=True)
        dfPVInfo['date'] = pd.to_datetime(dfPVInfo['date'])
        dfPVInfo['date'] = dfPVInfo['date'].dt.tz_localize(tz)
        tomorrowDT = datetime.now()+timedelta(days=1)
        tomorrow = tomorrowDT.strftime("%Y-%m-%d")
        dfPVInfo = dfPVInfo[(dfPVInfo['date'] < tomorrow)]
        dfPrices = pd.merge(dfPrices, dfPVInfo, how='left', left_on="localDate", right_on="date")
        dfPrices.drop(['date'], axis=1, inplace=True)

    #Plot prices
    if plotImage:
        logger.info("Now Plotting")
        x = range(24)
        y = dfPrices.price.tolist()
        fig, ax1 = plt.subplots() 
        ax1.set_ylabel('Price (€)') 
        colors = ["red" if i <= averagePrice*lowChargeLimit else "blue" for i in y]
        plot_1 = ax1.bar(x, y, color = colors) 
        ax1.tick_params(axis ='y', labelcolor = 'black') 
        plt.xlim(-1,24)
        plt.grid(1)
        if dateToday:
            dayString = "today"
        else:
            dayString = "tomorrow"
        plt.title("Energy prices " + dayString + ". Mean price: €" + str(round(dfPrices["price"].mean()*100)/100))
        ax1.axhline(y=averagePrice, color="green")
        ax1.axhline(y=averagePrice*lowChargeLimit, color="red")
        ax1.legend(["Average", "Lower limit", "Charging hours","Forecast"])
        ax1.set_xlabel('Hour')     
        if PV:
            y2 = dfPrices.wattHours.tolist()                    
            ax2 = ax1.twinx() 
            ax2.set_ylabel('Energy (Wh)') 
            plot_2 = ax2.plot(x, y2, color = 'yellow') 
            ax2.tick_params(axis ='y')         
            ax2.legend(["Forecast"])
        timestr = time.strftime("%Y%m%d")
        fig.savefig("plot-" + timestr + ".png")
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
                logger.info("Current price is €" + '%.2f' % chargePriceNow + ". The average price today is €" + '%.2f' % averagePrice + ". This is lower than " + str(lowChargeLimit) + " * daily average so the battery is now charging.")
                lastChargeCondition = 1                
        else:
        # If the ESS should not charge do this:              
            if flagConntected:
                client.publish("W/" + vrmID + "/settings/0/Settings/CGwacs/AcPowerSetPoint", '{"value":' + str(defaultGridSetpoint) + '}')
                logger.info("Current price is €" + '%.2f' % chargePriceNow + ". The average price today is €" + '%.2f' % averagePrice + ". This is higher than " + str(lowChargeLimit) + " *  daily average. This is not low enough to start charging. ")
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
    try:
        main()
    except KeyboardInterrupt:
        print('Stop program')