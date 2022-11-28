"""
Subscribe to mqtt topic of an openDTU device
Put result in influx db if available for the first time or if values for a measurement have changed

requires requests, paho-mqtt

Author: Joachim Banzhaf
License: GPL V2
"""

from threading import Timer
import sys
import json
import requests
import paho.mqtt.client as mqtt
from datetime import datetime as dt
import copy
from configparser import ConfigParser


influx_api = "2.1"  # changes if new version of this script sends different data
                    # increased minor: added new data, increased major: also changed existing data
                    # history: 
                    # * 1.0: all values are strings
                    # * 2.0: panel names required (or only last panel is updated)
                    # * 2.1: if panel names are empty, panel numbers are used

inverters = {}  # { id: name }
panels = {}     # { (id, num): name }


class PostTimer(Timer):
    def __init__(self):
        super().__init__(1.0, self.on_elapsed)
        self.start()
        self.data = {}       # new data { measurement: { "tags": tag(s): "values": { key=value ...} } }
        self.set_clean()
        self.start_time = 0  # dtu start time

    def run(self):  
        while not self.finished.wait(self.interval):  
            self.function(*self.args,**self.kwargs)  

    def on_elapsed(self):
        if self.is_clean(): return
        if self.is_data_incoming(): return

        for measurement, lines in self.data.items():
            if measurement not in self.prev_data or lines != self.prev_data[measurement]:
                for tags, values in lines.items():
                    if tags and values:
                        tags_dict = tags2DIPdict(tags)
                        tag_string = dict2string(tags_dict)
                        value_string = dict2quotedstring(values)
                        payload = f"{measurement},{tag_string} {value_string}"
                        try:
                            response = requests.post(url=influx_url, data=payload)
                            response.raise_for_status()
                        except Exception as e:
                            print(f"influx exception '{str(e)}'")

        self.set_clean()

    def set_dirty(self):
        self.lastUpdate = dt.now()

    def set_clean(self):
        self.prev_data = copy.deepcopy(self.data)
        self.lastUpdate = None

    def is_clean(self):
        return self.lastUpdate is None

    def is_data_incoming(self):
        # assume data set is complete if mqtt does not send data for > 1s
        return (dt.now() - self.lastUpdate).total_seconds() < 1.0

    def set_value(self, measurement, tags, key, value):
        """ collect a measurement value for later influx insert
        """
        if measurement not in self.data:
            self.data[measurement] = {}

        if tags not in self.data[measurement]:
            self.data[measurement][tags] = {}

        try:
            value = int(value)        # make value an int if possible
        except ValueError:
            try:
                value = float(value)  # else make value a float if possible
            except ValueError:
                pass                  # unchanged otherwise

        if key == "rssi":
            prev_rssi = self.data[measurement][tags].get(key, 0)
            if abs(value - prev_rssi) < 5:
                value = prev_rssi  # don't report minor rssi changes 

        if key == "last_update":
            prev_update = self.data[measurement][tags].get(key, 0)
            if abs(value - prev_update) < 2:
                value = prev_update  # don't report minor update time changes 

        if key not in self.data[measurement][tags] or self.data[measurement][tags][key] != value:
            self.data[measurement][tags][key] = value
            timer.set_dirty()


def tags2DIPdict(t):
    """ return tag tuple as dict
    keys are from fixed list as needed by OpenDTU mqtt data
    """
    keys = ["dtu", "inverter", "panel"]
    tagDict = {key: value for key, value in zip(keys, t)}
    tagDict["version"] = influx_api
    return tagDict


def dict2string(d):
    """ return comma separated key=value items from dictionary
    """
    return ",".join([f"{key}={value}" for key, value in sorted(d.items())])


def influxField(v):
    if isinstance(v, str):
        return f'"{v}"'
    else:
        return v


def dict2quotedstring(d):
    """ return comma separated key=value items from dictionary and quote string values
    """
    return ",".join([f'{key}={influxField(value)}' for key, value in sorted(d.items())])


def on_connect(mqtt_client, userdata, flags, rc):
    print(f"connected to mqtt broker {config['mqtt']['host']} with result code {rc}")
    mqtt_client.subscribe(mqtt_topic)  # wait for openDTU messages
    print(f"subscribed to mqtt topic {mqtt_topic}")


def on_message(mqtt_client, userdata, msg):
    """ Assemble single inverter data items from mqtt in one dict of influx measurements
    """
    try:
        message = msg.payload.decode("utf-8")
        topic = msg.topic.split("/")
        if len(topic) < 3: return

        if topic[1] == "dtu":
            if topic[2] == "rssi":
                timer.set_value("signal", (topic[0],), topic[2], message)
            else:
                if topic[2] == "uptime":
                    topic[2] = "start_time"
                    start = round(dt.now().timestamp() - int(message))
                    if abs(start - timer.start_time) > 1:
                        timer.start_time = start
                    message = str(timer.start_time)
                timer.set_value(topic[1], (topic[0],), topic[2], message)
        elif topic[2] == "name":
            if message is None or message == "":
                inverters[topic[1]] = hash(topic[1]) & 0xffff  # no name, use 16bit hash of serial
            else:
                inverters[topic[1]] = message  # to later translate serial to name
        else:
            inverter = inverters.get(topic[1])
            if inverter is not None and len(topic) == 4:
                if topic[2] == "device" or topic[2] == "status":
                    timer.set_value(topic[2], (topic[0], inverter), topic[3], message)
                elif topic[2] == "0":
                    timer.set_value("inverter", (topic[0], inverter), topic[3], message)
                else:
                    key = (inverter, topic[2])
                    if topic[3] == "name":
                        if message is None or message == "":
                            panels[key] = topic[2]  # no name, use number
                        else:
                            panels[key] = message  # to later translate (inv, panel_num) to name
                    else:
                        panel = panels.get(key)
                        if panel is not None:
                            timer.set_value("string", (topic[0], inverter, panel), topic[3], message)

    except UnicodeDecodeError:
        pass  # not interested...
    

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"syntax: {sys.argv[0]} mqtt_topic")
        exit(1)

    mqtt_topic = sys.argv[1]

    config = ConfigParser()

    config['DEFAULT'] = {
        'host': 'localhost',
        'user': 'openDtu2Db',
        'pass': None }
    config['mqtt'] = {}
    config['mqtt']['port'] = 1883
    config['influx'] = {}
    config['influx']['port'] = 8086
    config['influx']['db'] = 'openDtu'

    configs = ['/etc', '~/.config', '.']
    configs = [base + d + '/OpenDtu2Db.ini' for base in ['', mqtt_topic] for d in configs]
    config.read(configs)

    mqtt_topic += '/#'

    influx = config['influx']
    influx_url = f"http://{influx['host']}:influx['port']/write?db={influx['db']}&u={influx['user']}
    if influx['pass'] is not None
        influx_url += f"&p={influx['pass']}"
    print(f"start openDTU gateway to InfluxDB {influx['db']}@{influx['host']}")

    mqtt = config['mqtt']
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(username=mqtt['user'],password=mqtt['pass'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(mqtt_broker)

    timer = PostTimer()

    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        timer.cancel()

    print("bye")
