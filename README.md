# dynamic ess - Tariff based ESS controller

### Disclaimer

Work in progres. 

### Purpose

The goal of this project is to develop a feature for Victron Energy to take into account the dynamic tariff prices in the decision to store energy or to return energy to the grid. These dynamic tariff prices are nowadays offered by various energy providers (Easy Energy, ANWB, TIBR, and others) and are always announced a day in advance (also known as the day-ahead pricing model). The feature will control the grid setpoint as its main output. The goal is to implement this feature in VRM, the controller should run externally on PC, Raspberry Pi, or VPS.

### To do
* Retrieve prices from multiple energy providers:
  * ~~ANWB~~ (done)
  * ~~ENTSOE API~~ (done)  
  * Easy Energy
  * TIBR
* ~~Plot chart~~ (done)
* ~~ADD MQTT functionality through VRM~~ (done)
* Implement multiple charge scenarios 
  * ~~Simple charge when prices are X% lower then average~~ (done)
  * Always charge in X lowest tariff hours. (In this cases prices will be sorted in ascending order, first X hours will be used for charging)
  * Above scenario's including PV forecast. SoC will be lower in the morning so there is capacity left for PV charging. 
* Rewrite script as service
* ~~Implement logging~~ (done)
* ~~Implement scheduler~~ (done)
* ~~Implement PV forecast~~ (done)
### PV Features
* ~~Import forecast~~ (done)
* ~~Include forecast in plot~~ (done)
* Determine max SoC so there is capacity for PV energy
  
### Install (best to use in virtual env)

1. Clone GIT project on a machine with Python 3 installed. 
2. Install dependencies `pip3 install matplotlib numpy paho_mqtt pandas pytz requests logzero schedule xmltodict time` or use `pip3 install -r requirements.txt`

I run the script at a Digital Ocean VPS on Ubuntu 22.04

### Config

1. Configure `secret.py`
2. Configure settings in script as explained below

### Run 

* Run script: `python3 ESSController.py` 
* Run in background: `nohup python3 -u ./ESSController.py >> output.log &` 

### Settings
* `lowChargeLimit` this is the threshold used to start charging. Default = 0.8, charging starts in this case 20% below daily average
* `dateToday` If 1, date is today, if 0 date is tomorrow, for testing only. Default is 1
* `tz` Time zone, default is: "Europe/Amsterdam"
* `plotImage` If 1 an image is plotted to show when charging will start
* `defaultGridSetpoint` Default grid point (Watt). Default setting is 30
* `chargingGridSetpoint` Charging grid point (Watt). Default setting is 3000
* `provider` This selects the energy provider. 0 = ANWB, 1 = ENTSOE
* `PV` enables PV features. If PV = 1, PV Aware charging is enabled. PV = 0 is off
* `locLat` Latitude of PV installation
* `locLong` Longitude of PV installation
* `angle` Angle of your panels 0 (horizontal) … 90 (vertical)
* `direction` Plane azimuth, -180 … 180 (-180 = north, -90 = east, 0 = south, 90 = west, 180 = north)
* `totPower` Installed modules power in kilo watt

### Schedule
* Get prices is scheduled every day at 00:00:05.
* The ESS controller is scheduled every 5 minutes. If the charge requirement did change an MQTT message will be published. Otherwise noting will happen.

### Typical log file
In the log below you can see in this case charging started just after 22:00. At 00:00:05 new prices were retrieved and charging stoped just after 06:00

```[I 221214 22:04:09 chargeWithoutPV:153] Requirement has changed, sending MQTT message to change setpoint.
[I 221214 22:04:09 chargeWithoutPV:50] Broker connected.
[I 221214 22:04:10 chargeWithoutPV:167] Current price is €0.38. The average price today is €0.48. This is lower then 0.8* daily average so the battery is now charging.
[I 221214 22:04:10 chargeWithoutPV:56] Message Published.
[...]
[I 221215 00:00:06 chargeWithoutPV:121] Now prices retrieved for today
[I 221215 00:00:06 chargeWithoutPV:122] Average price is: €0.42
[I 221215 00:00:06 chargeWithoutPV:141] New plot created and saved. Filename: plot-20221215.png
[...]
[I 221215 06:04:40 chargeWithoutPV:153] Requirement has changed, sending MQTT message to change setpoint.
[I 221215 06:04:40 chargeWithoutPV:173] Current price is €0.35. The average price today is €0.42. This is not low enough to start charging. 
[I 221215 06:04:40 chargeWithoutPV:56] Message Published.```
