# dynamic ess - Tariff based ESS controller

### Disclaimer

Work in progres. 

### Purpose

The goal of this project is to develop a feature for Victron Energy to take into account the dynamic tariff prices in the decision to store energy or to return energy to the grit. These dynamic tariff prices are nowadays offered by various energy providers (Easy Energy, ANWB, TIBR, and others) and are always announced a day in advance (also known as the day-ahead pricing model). The feature will control the grid setpoint as its main output.

### To do
* Retrieve
* Retrieve prices from multiple energy providers:
  * ~~ANWB~~ (done)
  * Easy Energy
  * TIBR
* ~~Plot chart~~ (done)
* ~~ADD MQTT functionality through VRM~~ (done)
* Implement multiple charge scenarios 
  * ~~Simple charge when prices are X% lower then average~~ (done)
  * Always charge in X lowest tariff hours. (In this cases prices will be sorted in ascending order, first X hours will be used for charging)
  * Above scenario's including PV forecast. SoC will be lower in the morning so there is capacity left for PV charging. 
* Rewrite script as service
* Implement logging
  
### Install

1. Clone GIT project to local PC
3. Configure `secret.py`
2. Run script `python3 chargeWithoutPV.py` or add it to your crontab to schedule the script

### Config

Copy or rename the `secret.example.py` to `secret.py` and change it as you need it.


