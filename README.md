# OpenDTU2Db - MicroInverter Gateway from OpenDTU to Influx DB

This is a python script querying energy readings from an OpenDTU device.

The readings are transfered into an influx database only if something has changed.

The script can be used by the systemd service so the script does its job whenever the server is up

## Prerequisite

* MQTT broker installed and running

    if you don't have one yet: on opensuse probably as easy as
    ```
    sudo zypper in mosquitto
    systemctl enable mosquitto
    systemctl start mosquito
    ```
* OpenDTU device with an inverter registered and mqtt host configured. See [OpenDTU Github](https://github.com/tbnobody/OpenDTU). Check data is coming in. If your topic is 'OpenDTU1' with e.g.
    ```
    mosquitto_sub -v -t 'OpenDTU1/#'
    ```
* Configure OpenDTU to use a unique topic for each inverter 
* Configure OpenDTU to either use unique names for each inverter string or no inverter string names. For different inverters you can reuse string names.

## Install

* copy openDtu2Db.py and openDtu2Db.sh to ~/bin of the service user
    ```
    cp -a openDtu2Db.py openDtu2Db.sh ~/bin/
    ```
* copy openDtu2Db.service to /etc/systemd/system
    ```
    sudo cp -a openDtu2Db@.service /etc/systemd/system/
    ```
* adapt service user and working directory in the service file (working directory is used to find config files)
* create influx database. Default name is "openDtu"
    ```
    influx --execute 'create database openDtu'
    ```
* create conda environment "openDtu2Db" with python, requests and paho-mqtt
    (or otherwise ensure the required modules are available)
    ```
    conda create --name openDtu2Db python requests pip
    conda activate openDtu2Db
    pip install paho_mqtt
    ```
* register and start service. The name after the "@" is the mqtt topic as configured in the OpenDTU
    ```
    sudo systemctl daemon-reload
    sudo systemctl enable openDtu2Db@OpenDTU1
    sudo systemctl start openDtu2Db@OpenDTU1
    ```
* check if service is running, e.g. with
    ```
    sudo systemctl status openDtu2Db@OpenDTU1
    ```
    Should output something like
    ```
    ● openDtu2Db@OpenDTU1.service - OpenDTU service for topic OpenDTU1
         Loaded: loaded (/etc/systemd/system/openDtu2Db@.service; enabled; vendor preset: disabled)
         Active: active (running) since Mon 2022-11-28 20:04:43 CET; 5s ago
       Main PID: 13328 (python)
          Tasks: 2 (limit: 4915)
         CGroup: /system.slice/system-openDtu2Db.slice/openDtu2Db@OpenDTU1.service
                 └─13328 python -u /home/joachim/bin/openDtu2Db.py OpenDTU1

    Nov 28 20:04:43 job4 systemd[1]: Started OpenDTU service for topic OpenDTU1.
    Nov 28 20:04:44 job4 openDtu2Db.sh[13328]: start openDTU gateway to InfluxDB openDtu@localhost
    Nov 28 20:04:44 job4 openDtu2Db.sh[13328]: connected to mqtt broker localhost with result code 0
    Nov 28 20:04:44 job4 openDtu2Db.sh[13328]: subscribed to mqtt topic OpenDTU1/#
    ```

## Configuration

The script uses reasonable defaults for a single DTU if mqtt and influx is running on the same host and no user or password is needed.
If needed, configuration files OpenDtu2Db.ini can be provided in '/etc', '/etc/TOPIC', '\~/.config', '\~/.config/TOPIC', the working directory '.' and './TOPIC'.
Settings are accumulated, the last one wins (see python configparser for details).
OpenDtu2Db_sample.ini is a sample file with all available parameters

## Use

As soon as the openDTU device receives readings from inverters it will publish mqtt topics.
This gateway subscribes to them and creates entries in influx db measurements.
The following measurements are available
* dtu: topic -> starttime, ip, hostname, online
* signal: topic -> rssi
* device: topic,name -> bootloaderversion, fwbuildversion, fwbuilddatetime, hwpartnumber, hwversion, limit_relative, limit_absolute
* inverter: topic,name -> reachable, producing, powerdc, yieldday, yieldtotal, voltage, current, power, frequency, temperature, powerfactor, efficiency, reactivepower
* string: topic,inverter,name -> voltage, current, power, yieldday, yieldtotal, irradiation

Use the influx data for e.g. a grafana dashboard
