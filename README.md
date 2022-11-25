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

## Install

* copy openDtu2Db.py and openDtu2Db.sh to ~/bin
    ```
    cp -a openDtu2Db.py openDtu2Db.sh ~/bin/
    ```
* copy openDtu2Db.service to /etc/systemd/system
    ```
    sudo cp -a openDtu2Db.service /etc/systemd/system/
    ```
* adapt mqtt topic of energy device in /etc/systemd/system/ (e.g. use topic 'OpenDTU1')
* adapt mqtt broker and influx host in ~/bin/openDtu2Db.py (e.g. use localhost)
* create influx database "openDtu"
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
* register and start service
    ```
    sudo systemctl daemon-reload
    sudo systemctl enable openDtu2Db
    sudo systemctl start openDtu2Db
    ```
* check if service is running, e.g. with
    ```
    sudo systemctl status openDtu2Db
    ```
    Should output something like
    ```
    ● openDtu2Db.service - OpenDTU service for OpenDtu1
        Loaded: loaded (/etc/systemd/system/openDtu2Db.service; enabled; vendor preset: disabled)
        Active: active (running) since Fri 2022-11-25 19:33:53 CET; 1min 35s ago
    Main PID: 2207 (python)
        Tasks: 2 (limit: 4915)
        CGroup: /system.slice/openDtu2Db.service
                └─2207 python -u /home/joachim/bin/openDtu2Db.py OpenDtu1

    Nov 25 19:33:53 job4 systemd[1]: Started OpenDTU service for OpenDtu1.
    Nov 25 19:33:54 job4 openDtu2Db.sh[2207]: start openDTU InfluxDb gateway for OpenDtu1/#
    Nov 25 19:33:54 job4 openDtu2Db.sh[2207]: connected to mqtt broker job4 with result code 0
    ```
## Use

As soon as the openDTU device receives readings from inverters it will publish mqtt topics.
This gateway subscribes to them and creates entries in influx db measurements.
The following measurements are available
* dtu: topic -> starttime, ip, hostname, online
* signal: topic -> rssi
* device: topic,name -> bootloaderversion, fwbuildversion, fwbuilddatetime, hwpartnumber, hwversion, limit_relative, limit_absolute
* inverter: topic,name -> reachable, producing, powerdc, yieldday, yieldtotal, voltage, current, power, frequency, temperature, powerfactor, efficiency, reactivepower
* string: topic,inverter,name -> voltage, current, power, yieldday, yieldtotal, irradiation

Use the influx data for, e.g. a grafana dashboard
