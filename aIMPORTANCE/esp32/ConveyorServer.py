import json
import time
import logging
from contextlib import contextmanager
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class ConveyorServer:
    DEFAULT_CONFIG = {
        "mqtt_users": ["0_SmartConvey2025", "1_SmartConvey2025"],
        "mqtt_password": "",
        "mqtt_server": "mqtt.ohstem.vn",
        "mqtt_port": 1883,
        "cmd_topic": "V1",
        "status_topic": "V2"
    }

    def __init__(self, cfg=None):
        self.cfg = cfg or self.DEFAULT_CONFIG
        # Dùng tên MQTT user làm key
        self.conveyors = {
            user: {"ready": False, "client": None} for user in self.cfg["mqtt_users"]
        }

    # MQTT callbacks
    def make_on_connect(self, user):
        def on_connect(client, userdata, flags, rc, properties=None):
            logging.info(f"{user} connected, rc={rc}")
            status_topic = f"{user}/feeds/{self.cfg['status_topic']}"
            client.subscribe(status_topic)
            logging.info(f"{user} subscribed to {status_topic}")
        return on_connect

    def make_on_message(self, user):
        def on_message(client, userdata, msg):
            try:
                data = json.loads(msg.payload.decode())
                status = data.get("status", "").upper()
            except:
                status = msg.payload.decode().upper()

            if "READY" in status:
                self.conveyors[user]["ready"] = True
                logging.info(f"[PING ACK] {user} READY")
            elif "DONE" in status:
                logging.info(f"[STATUS {user}] {data}")
        return on_message

    # Setup MQTT clients
    def setup_clients(self):
        for user in self.conveyors:
            client = mqtt.Client(client_id=user, protocol=mqtt.MQTTv311)
            client.username_pw_set(user, self.cfg["mqtt_password"])
            client.on_connect = self.make_on_connect(user)
            client.on_message = self.make_on_message(user)
            client.connect(self.cfg["mqtt_server"], self.cfg["mqtt_port"], 60)
            client.loop_start()
            self.conveyors[user]["client"] = client
            time.sleep(0.5)

    # Send command
    def send_command(self, user, action, duration_ms=None):
        client = self.conveyors[user]["client"]
        cmd_topic = f"{user}/feeds/{self.cfg['cmd_topic']}"
        payload = {"action": action}
        if duration_ms:
            payload["duration_ms"] = duration_ms
        client.publish(cmd_topic, json.dumps(payload))
        logging.info(f"[SENT {user}] {payload} -> {cmd_topic}")

    # Ping context
    @contextmanager
    def ping(self, user, timeout=5):
        if not self.conveyors[user]["client"]:
            yield False
            return
        self.conveyors[user]["ready"] = False
        cmd_topic = f"{user}/feeds/{self.cfg['cmd_topic']}"
        self.conveyors[user]["client"].publish(cmd_topic, json.dumps({"action": "PING"}))
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.conveyors[user]["ready"]:
                yield True
                break
            time.sleep(0.1)
        else:
            yield False
        self.conveyors[user]["ready"] = False


# Example usage (gọi từng conveyor riêng biệt)
if __name__ == "__main__":
    server = ConveyorServer()
    server.setup_clients()

    # Conveyor 0
    user = "0_SmartConvey2025"
    with server.ping(user) as ok:
        if ok:
            print(f"✅ {user} READY")
            server.send_command(user, action=2, duration_ms=2000)
        else:
            print(f"❌ {user} NOT responding")

    # Conveyor 1
    # user = "1_SmartConvey2025"
    # with server.ping(user) as ok:
    #     if ok:
    #         print(f"✅ {user} READY")
    #         server.send_command(user, action=1, duration_ms=1000)
    #     else:
    #         print(f"❌ {user} NOT responding")
