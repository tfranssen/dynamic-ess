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
  
### Install

1. Clone GIT project to local PC
2. Install dependencies `pip3 install matplotlib numpy paho_mqtt pandas pytz requests logzero schedule xmltodict time`
3. Configure `secret.py`
4. Run script `python3 chargeWithoutPV.py` ~~or add it to your crontab to schedule the script~~ (not needed anymore)

### Config

1. Copy or rename the `secret.example.py` to `secret.py` and change it as you need it.
2. Edit settings in script

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
* `totPower` installed modules power in kilo watt



### Schedule
* Get prices is scheduled every day at 00:00:05.
* The ESS controller is scheduled every 5 minutes. If the charge requirement did change an MQTT message will be published. Otherwise noting will happen.

