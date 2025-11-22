from servo import *
from mdv2 import *
from mqtt_as import MQTTClient, config
from wifi import *
from pins import *
from motor import *
from abutton import *
import ujson
import utime
import network
import socket
import ure
import os


# ========================================
# LED colors & helper
# ========================================
COLORS = {
    'INIT': '#ff0000',
    'READY': '#00ff00',
    'ERROR': '#ff00ff',
    'RUN': '#0000ff',
    'IDLE': '#ffff00'
}

def blink_color(color_hex, times=1, delay=150):
    rgb = hex_to_rgb(color_hex)
    for _ in range(times):
        try:
            neopix.show(0, rgb)
        except:
            pass
        utime.sleep_ms(delay)
        try:
            neopix.show(0, (0, 0, 0))
        except:
            pass
        utime.sleep_ms(delay)


# =========================================================
# WiFi Manager (SCAN → AP Mode → Save JSON)
# =========================================================
class WiFiManager:
    WIFI_FILE = "wifi_config.json"

    def __init__(self, ssid=None, pw=None):
        self.ssid = ssid
        self.pw = pw
        self.load_saved_wifi()  # nếu có file json thì tự load

    # ---------------- LOAD CONFIG FILE ----------------
    def load_saved_wifi(self):
        if self.ssid:
            # nếu đã truyền ssid từ ngoài thì ưu tiên giá trị đó
            return

        try:
            if self.WIFI_FILE in os.listdir():
                with open(self.WIFI_FILE) as f:
                    data = ujson.loads(f.read())
                    self.ssid = data.get("ssid")
                    self.pw = data.get("pw")
                    print("📁 Loaded saved WiFi →", self.ssid)
        except Exception as e:
            print("⚠ Error reading wifi_config.json:", e)

    # ---------------- SAVE WIFI TO FILE ----------------
    def save_wifi(self, ssid, pw):
        try:
            with open(self.WIFI_FILE, "w") as f:
                f.write(ujson.dumps({"ssid": ssid, "pw": pw}))
            print("💾 Saved WiFi:", ssid)
        except Exception as e:
            print("❌ Failed to save WiFi file:", e)

    # ---------------- CONNECT WIFI ----------------
    def connect(self):
        if not self.ssid:
            print("⚠ No WiFi stored")
            return False

        print("\n🔄 Reset WiFi driver...")

        # Tắt AP nếu đang bật
        ap = network.WLAN(network.AP_IF)
        ap.active(False)

        # Reset STA
        sta = network.WLAN(network.STA_IF)
        try:
            sta.disconnect()
        except:
            pass
        sta.active(False)
        utime.sleep_ms(200)
        sta.active(True)
        utime.sleep_ms(200)

        print("📡 Connecting WiFi →", self.ssid)

        try:
            sta.connect(self.ssid, self.pw)
        except Exception as e:
            print("❌ sta.connect error:", e)
            return False

        for _ in range(15):
            if sta.isconnected():
                print("✅ WiFi Connected:", sta.ifconfig())
                return True
            utime.sleep_ms(500)

        print("❌ WiFi connect FAILED")
        return False

    # ---------------- SCAN WIFI ----------------
    def scan_wifi_list(self):
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
        utime.sleep_ms(200)
        sta.active(True)
        utime.sleep_ms(400)

        try:
            wifi_list = sta.scan()
            names = [w[0].decode() for w in wifi_list]
            print("📶 Scan result:", names)
            return names
        except Exception as e:
            print("❌ Scan error:", e)
            return []

    # ---------------- ENABLE AP ----------------
    def start_ap(self):
        ap = network.WLAN(network.AP_IF)
        ap.active(False)
        utime.sleep_ms(200)
        ap.active(True)
        ap.config(essid="ConveyorSetup", password="12345678")
        print("\n📡 AP MODE ENABLED → SSID: ConveyorSetup | PASS: 12345678")
        return ap

    # ---------------- WEB CONFIG (WiFi Portal) ----------------
    def web_config(self):

        wifi_names = self.scan_wifi_list()
        print("📶 WiFi found:", wifi_names)

        ap = self.start_ap()

        # ============ HTML TEMPLATE =============
        HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Conveyor WiFi Setup</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{
    font-family:'Helvetica Neue',Arial;
    background:#fff;color:#000;
    display:flex;flex-direction:column;
    height:100vh;overflow:hidden;
}
.app-header{
    height:55px;display:flex;
    align-items:center;justify-content:space-between;
    padding:0 14px;border-bottom:2px solid #000;
}
.status-chip{
    padding:4px 10px;border:2px solid #000;font-size:13px;
}
.container{
    flex:1;display:flex;justify-content:center;
    align-items:center;padding:14px;
}
.wifi-card{
    width:100%;max-width:380px;
    border:2px solid #000;padding:16px;
    display:flex;flex-direction:column;gap:12px;
}
.field{display:flex;flex-direction:column;gap:4px;}
select,input{
    border:2px solid #000;padding:6px 8px;font-size:14px;
}
button{
    width:100%;border:2px solid #000;margin-top:4px;
    padding:8px;font-weight:600;cursor:pointer;transition:.2s;
}
button:hover{background:#000;color:#fff;}
.reload-btn{background:#ffe082;}
.reload-btn:hover{background:#ffca28;color:#000;}
</style>
</head>
<body>

<header class="app-header">
    <h3>Conveyor WiFi Setup</h3>
    <div class="status-chip">AP Mode</div>
</header>

<div class="container">
    <div class="wifi-card">
        <form action="/" method="POST">
            <div class="field">
                <label>Chọn WiFi:</label>
                <select name="ssid">{OPTIONS}</select>
            </div>
            <div class="field">
                <label>Mật khẩu:</label>
                <input type="password" name="pw" placeholder="Nhập mật khẩu">
            </div>
            <button type="submit">Kết nối</button>
        </form>

        <form action="/reload" method="GET">
            <button class="reload-btn">🔄 Reload WiFi</button>
        </form>
    </div>
</div>

</body>
</html>
"""
        def build_html():
            opts = "".join([f"<option value='{n}'>{n}</option>" for n in wifi_names])
            return HTML.replace("{OPTIONS}", opts)

        html = build_html()

        # ----- BIND PORT 8080 → fallback 8081 -----
        for PORT in (8080, 8081):
            try:
                s = socket.socket()
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", PORT))
                print("🌐 Web Config Ready → http://192.168.4.1:%d" % PORT)
                break
            except Exception as e:
                print("⚠ Port %d busy, trying next... (%s)" % (PORT, e))
        s.listen(1)

        # ---- SERVER LOOP ----
        while True:
            conn, addr = s.accept()
            try:
                req = conn.recv(2048).decode()

                # Reload danh sách WiFi
                if "GET /reload" in req:
                    wifi_names = self.scan_wifi_list()
                    html = build_html()
                    conn.send("HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n")
                    conn.send(html)
                    conn.close()
                    continue

                # Submit form
                if "POST" in req:
                    ssid = ure.search("ssid=([^&]+)", req).group(1)
                    pw = ure.search("pw=([^&]*)", req).group(1)

                    self.ssid = ssid
                    self.pw = pw
                    self.save_wifi(ssid, pw)

                    conn.send("HTTP/1.1 200 OK\r\n\r\nConnecting...")
                    conn.close()
                    s.close()

                    print("🔁 Trying WiFi:", ssid)
                    # KHÔNG connect ở đây, để main xử lý sau
                    return (ssid, pw)

                # Trang mặc định
                conn.send("HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n")
                conn.send(html)
                conn.close()

            except Exception as e:
                print("⚠ Web server error:", e)
                try:
                    conn.close()
                except:
                    pass


# =========================================================
# =============== CONVEYOR BELT MAIN CLASS =================
# =========================================================
class ConveyorConfig:
    # sẽ được set lại từ WiFiManager
    ssid = None
    password = None

    mqtt_server = 'mqtt.ohstem.vn'
    mqtt_port = 1883
    mqtt_user = '0_SmartConvey2025'
    mqtt_password = ''

    speed_servo = 90
    action_servo = 45
    default_servo = 0
    speed_motor = 70
    idle_interval_ms = 5000
    idle_duration_ms = 1000

    @property
    def mqtt_topics_cmd(self):
        return ['V1']

    @property
    def mqtt_topic_status(self):
        return 'V2'


class ConveyorBelt:
    def __init__(self, cfg: ConveyorConfig):
        self.cfg = cfg

        self.md = MotorDriverV2()
        self.servo1 = Servo(self.md, S1, 180)
        self.servo2 = Servo(self.md, S2, 180)
        self.motor = DCMotor(self.md, M1)
        self.busy = False

        # MQTT setup (y hệt bản bạn đang dùng được)
        self.mqtt_cfg = config.copy()
        self.mqtt_cfg.update({
            'ssid': cfg.ssid,
            'wifi_pw': cfg.password,
            'server': cfg.mqtt_server,
            'port': cfg.mqtt_port,
            'user': cfg.mqtt_user,
            'password': cfg.mqtt_password
        })
        self.mqtt_cfg["topics"] = [(t, self.on_mqtt_msg) for t in cfg.mqtt_topics_cmd]
        self.mqtt = MQTTClient(self.mqtt_cfg)
        MQTTClient.DEBUG = True

    # ----------------------------------------
    # LED
    # ----------------------------------------
    def led_state(self, mode):
        try:
            neopix.show(0, hex_to_rgb(COLORS[mode]))
        except:
            pass
        print("[%d ms][LED] %s" % (utime.ticks_ms(), mode))

    # ----------------------------------------
    # MQTT Status
    # ----------------------------------------
    async def send_status(self, status, data=None):
        msg = {"status": status}
        if data:
            msg.update(data)
        payload = ujson.dumps(msg)
        try:
            await self.mqtt.publish(self.cfg.mqtt_topic_status, payload)
            print("[%d ms][MQTT] SENT:" % utime.ticks_ms(), payload)
        except Exception as e:
            print("[%d ms][MQTT] SEND FAILED:" % utime.ticks_ms(), e)

    # ----------------------------------------
    # Init servo + motor
    # ----------------------------------------
    async def init_servo_motor(self):
        self.led_state("INIT")
        print("[%d ms][INIT] Motor+Servo init start" % utime.ticks_ms())

        self.motor.run(self.cfg.speed_motor)
        await asleep_ms(400)
        self.motor.run(0)

        for s in (self.servo1, self.servo2):
            try:
                s.limit(0, self.cfg.action_servo)
                await s.run_angle(self.cfg.action_servo, self.cfg.speed_servo)
                await s.run_angle(self.cfg.default_servo, self.cfg.speed_servo)
            except Exception as e:
                print("[%d ms][INIT] Servo error:" % utime.ticks_ms(), e)

        print("[%d ms][INIT] Done" % utime.ticks_ms())
        self.led_state("READY")

    # ----------------------------------------
    # Perform action + LOG CHI TIẾT
    # ----------------------------------------
    async def perform_action(self, servo=None, action_id=None, duration_ms=None):
        ts = utime.ticks_ms()

        if self.busy:
            print("[%d ms][ACTION] IGNORED → BUSY (requested %s)" % (ts, action_id))
            await self.send_status("BUSY", {"action": action_id})
            return

        self.busy = True
        duration = duration_ms or 800

        print("[%d ms][ACTION] START → action=%s, duration=%d" %
              (ts, action_id, duration))

        self.led_state("RUN")

        try:
            # Servo đến góc thao tác
            if servo:
                print("[%d ms][SERVO] Move to %d°" %
                      (utime.ticks_ms(), self.cfg.action_servo))
                await servo.run_angle(self.cfg.action_servo, self.cfg.speed_servo)
                await asleep_ms(150)

            # Motor chạy
            print("[%d ms][MOTOR] RUN speed=%d" %
                  (utime.ticks_ms(), self.cfg.speed_motor))
            self.motor.run(self.cfg.speed_motor)
            await asleep_ms(duration)

            # Dừng motor
            print("[%d ms][MOTOR] STOP" % utime.ticks_ms())
            self.motor.run(0)

            # Servo trả về
            if servo:
                print("[%d ms][SERVO] Return to %d°" %
                      (utime.ticks_ms(), self.cfg.default_servo))
                smooth_speed = int(self.cfg.speed_servo * 0.6)
                await servo.run_angle(self.cfg.default_servo, smooth_speed)

            print("[%d ms][ACTION] DONE → action=%s" %
                  (utime.ticks_ms(), action_id))
            self.led_state("IDLE")
            await self.send_status("DONE", {"action": action_id})

        except Exception as e:
            print("[%d ms][ACTION] ERROR:" % utime.ticks_ms(), e)
            self.motor.run(0)
            self.led_state("ERROR")
            await self.send_status("ERROR", {"action": action_id, "error": str(e)})

        self.busy = False

    # ----------------------------------------
    # MQTT Handler (đã FIX decode)
    # ----------------------------------------
    async def on_mqtt_msg(self, topic, msg):
        # mqtt_as đôi khi truyền str, đôi khi bytes → luôn chuẩn hóa
        msg_str = msg.decode() if isinstance(msg, bytes) else str(msg)
        print("[%d ms][MQTT] RX raw:" % utime.ticks_ms(), msg_str)

        action = None
        duration = None

        try:
            parsed = ujson.loads(msg_str)
            action = parsed.get("action")
            duration = parsed.get("duration_ms")
            print("[%d ms][MQTT] Parsed:" % utime.ticks_ms(), parsed)
        except Exception:
            # fallback: chuỗi đơn, số đơn
            action = int(msg_str) if msg_str.isdigit() else msg_str.upper()
            print("[%d ms][MQTT] Parsed fallback action=%s" %
                  (utime.ticks_ms(), action))

        if self.busy:
            print("[%d ms][MQTT] BUSY, cannot run action=%s" %
                  (utime.ticks_ms(), action))
            await self.send_status("BUSY", {"action": action})
            return

        if action == 1:
            await self.perform_action(self.servo1, 1, duration)
        elif action == 2:
            await self.perform_action(self.servo2, 2, duration)
        elif action == 3:
            await self.perform_action(None, 3, duration)
        elif action == "PING":
            print("[%d ms][MQTT] PING → READY" % utime.ticks_ms())
            await self.send_status("READY")
        else:
            print("[%d ms][MQTT] Unknown action:" % utime.ticks_ms(), action)
            await self.send_status("ERROR", {"msg": "Unknown action", "payload": msg_str})

    # ----------------------------------------
    # Setup & Run
    # ----------------------------------------
    async def setup(self):
        await self.init_servo_motor()
        print("[%d ms][MQTT] Connecting..." % utime.ticks_ms())
        await self.mqtt.connect()
        print("[%d ms][MQTT] Connected" % utime.ticks_ms())
        self.led_state("READY")

    async def run(self):
        await self.setup()
        timer = utime.ticks_ms()

        while True:
            if utime.ticks_diff(utime.ticks_ms(), timer) > self.cfg.idle_interval_ms:
                if not self.busy:
                    # idle: chạy băng tải 1 tí cho "sống"
                    await self.perform_action(None, 0, self.cfg.idle_duration_ms)
                timer = utime.ticks_ms()
            await asleep_ms(100)


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":

    cfg = ConveyorConfig()
    wifi = WiFiManager()  # sẽ tự load wifi_config.json nếu có

    print("🔌 Checking WiFi before start...")

    if not wifi.connect():
        print("➡ WiFi FAIL → AP CONFIG MODE")
        ssid, pw = wifi.web_config()
        wifi.save_wifi(ssid, pw)
        # Sau khi user nhập xong → thử connect lại
        wifi.connect()

    # gán vào cfg để MQTT dùng
    cfg.ssid = wifi.ssid
    cfg.password = wifi.pw

    blink_color("#00ff00", 3, 120)

    conveyor = ConveyorBelt(cfg)
    run_loop(conveyor.run())
