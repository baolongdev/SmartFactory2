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
# LED colors
# ========================================
COLORS = {
    'INIT':  '#ff0000',
    'READY': '#00ff00',
    'ERROR': '#ff00ff',
    'RUN':   '#0000ff',
    'IDLE':  '#ffff00',
}

def blink_color(color_hex, times=1, delay=150):
    rgb = hex_to_rgb(color_hex)
    for _ in range(times):
        try: neopix.show(0, rgb)
        except: pass
        utime.sleep_ms(delay)
        try: neopix.show(0, (0, 0, 0))
        except: pass
        utime.sleep_ms(delay)


# ========================================
# URL decode helper (FIX: form POST data)
# ========================================
def _url_decode(s):
    """
    Decode application/x-www-form-urlencoded string.
    '+' → space, '%XX' → character.
    Required so passwords with @, !, #, space, etc. work correctly.
    """
    s = s.replace('+', ' ')
    out = []
    i = 0
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            try:
                out.append(chr(int(s[i+1:i+3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        out.append(s[i])
        i += 1
    return ''.join(out)


def _sock_sendall(sock, data):
    """
    Send all bytes — MicroPython socket.send() may send fewer bytes than
    requested on a single call (similar to POSIX write()).  Loop until done.
    """
    if isinstance(data, str):
        data = data.encode()
    mv = memoryview(data)
    total = 0
    while total < len(mv):
        sent = sock.send(mv[total:])
        if sent == 0:
            break
        total += sent


# =========================================================
# WiFi Manager (SCAN → AP Mode → Save JSON)
# =========================================================
class WiFiManager:
    WIFI_FILE = "wifi_config.json"

    def __init__(self, ssid=None, pw=None):
        self.ssid = ssid
        self.pw   = pw
        self.load_saved_wifi()

    # ── Load saved config ────────────────────────────────────────────────
    def load_saved_wifi(self):
        if self.ssid:
            return   # caller-supplied value takes priority
        try:
            if self.WIFI_FILE in os.listdir():
                with open(self.WIFI_FILE) as f:
                    data = ujson.loads(f.read())
                    self.ssid = data.get("ssid")
                    self.pw   = data.get("pw")
                    print("[WiFi] Loaded saved SSID:", self.ssid)
        except Exception as e:
            print("[WiFi] Error reading config:", e)

    # ── Save config ──────────────────────────────────────────────────────
    def save_wifi(self, ssid, pw):
        try:
            with open(self.WIFI_FILE, "w") as f:
                f.write(ujson.dumps({"ssid": ssid, "pw": pw}))
            print("[WiFi] Saved SSID:", ssid)
        except Exception as e:
            print("[WiFi] Save failed:", e)

    # ── Connect to saved network ─────────────────────────────────────────
    def connect(self, retries=20):
        if not self.ssid:
            print("[WiFi] No SSID stored")
            return False

        ap = network.WLAN(network.AP_IF)
        ap.active(False)

        sta = network.WLAN(network.STA_IF)
        try: sta.disconnect()
        except: pass
        sta.active(False)
        utime.sleep_ms(200)
        sta.active(True)
        utime.sleep_ms(200)

        print("[WiFi] Connecting →", self.ssid)
        try:
            sta.connect(self.ssid, self.pw)
        except Exception as e:
            print("[WiFi] connect() error:", e)
            return False

        for _ in range(retries):
            if sta.isconnected():
                print("[WiFi] Connected:", sta.ifconfig())
                return True
            utime.sleep_ms(500)

        print("[WiFi] FAILED after %d attempts" % retries)
        return False

    # ── Scan available SSIDs ─────────────────────────────────────────────
    def scan_wifi_list(self):
        """
        Returns deduplicated list of (ssid, rssi) sorted by signal strength.
        FIX: safe UTF-8 decode so non-ASCII SSIDs don't crash.
        """
        sta = network.WLAN(network.STA_IF)
        sta.active(False)
        utime.sleep_ms(200)
        sta.active(True)
        utime.sleep_ms(500)

        try:
            raw = sta.scan()   # [(ssid_bytes, bssid, channel, rssi, authmode, hidden), ...]
        except Exception as e:
            print("[WiFi] Scan error:", e)
            return []

        seen   = set()
        result = []
        for w in raw:
            try:
                name = w[0].decode('utf-8', 'ignore').strip()
            except Exception:
                continue
            if not name or name in seen:
                continue          # skip hidden / duplicate SSIDs
            seen.add(name)
            rssi = w[3] if len(w) > 3 else -100
            result.append((name, rssi))

        # Sort: strongest signal first
        result.sort(key=lambda x: -x[1])
        print("[WiFi] Scan:", [n for n, _ in result])
        return result   # [(ssid, rssi), ...]

    # ── Start AP hotspot ─────────────────────────────────────────────────
    def start_ap(self, ssid="ConveyorSetup", password="12345678"):
        ap = network.WLAN(network.AP_IF)
        ap.active(False)
        utime.sleep_ms(200)
        ap.active(True)
        ap.config(essid=ssid, password=password)
        print("[WiFi] AP started → SSID:%s  PASS:%s" % (ssid, password))
        return ap

    # ── Captive WiFi portal ──────────────────────────────────────────────
    def web_config(self):
        """
        Start AP + HTTP server so the user can pick a WiFi network.
        Returns (ssid, pw) after the user submits the form.

        FIX: URL-decode POST values so special-char passwords work.
        FIX: sendall() so large HTML pages aren't truncated.
        FIX: raise if no port could be bound (prevents NameError on s.listen).
        """
        wifi_list = self.scan_wifi_list()   # [(ssid, rssi), ...]
        self.start_ap()

        # ── HTML template ────────────────────────────────────────────────
        HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conveyor WiFi Setup</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Helvetica Neue',Arial;background:#fff;color:#000;
     display:flex;flex-direction:column;min-height:100vh}
.hdr{height:52px;display:flex;align-items:center;justify-content:space-between;
     padding:0 14px;border-bottom:2px solid #000}
.chip{padding:3px 10px;border:2px solid #000;font-size:12px;font-weight:700}
.wrap{flex:1;display:flex;justify-content:center;align-items:center;padding:16px}
.card{width:100%;max-width:360px;border:2px solid #000;padding:18px;
      display:flex;flex-direction:column;gap:14px}
.fld{display:flex;flex-direction:column;gap:5px}
label{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
select,input{border:2px solid #000;padding:7px 9px;font-size:14px;width:100%}
.signal{font-size:11px;color:#666;float:right}
.btn{width:100%;border:2px solid #000;padding:9px;font-weight:700;
     font-size:14px;cursor:pointer;background:#fff;transition:.15s}
.btn:hover{background:#000;color:#fff}
.btn-reload{background:#ffe082}
.btn-reload:hover{background:#000;color:#fff}
</style>
</head>
<body>
<header class="hdr">
  <strong>Conveyor WiFi Setup</strong>
  <div class="chip">AP Mode</div>
</header>
<div class="wrap">
  <div class="card">
    <form method="POST" action="/">
      <div class="fld">
        <label>Chon WiFi</label>
        <select name="ssid">{OPTIONS}</select>
      </div>
      <div class="fld" style="margin-top:8px">
        <label>Mat khau</label>
        <input type="password" name="pw" placeholder="Nhap mat khau...">
      </div>
      <button class="btn" type="submit" style="margin-top:4px">Ket noi</button>
    </form>
    <form method="GET" action="/reload">
      <button class="btn btn-reload" type="submit">Reload WiFi</button>
    </form>
  </div>
</div>
</body>
</html>"""

        def signal_bar(rssi):
            if rssi >= -55: return "[|||]"
            if rssi >= -70: return "[|| ]"
            if rssi >= -85: return "[|  ]"
            return "[   ]"

        def build_html():
            opts = "".join(
                "<option value='{n}'>{b} {n}</option>".format(n=name, b=signal_bar(rssi))
                for name, rssi in wifi_list
            )
            return HTML.replace("{OPTIONS}", opts)

        html = build_html()

        # ── Bind socket ──────────────────────────────────────────────────
        s = None
        for port in (80, 8080, 8081):
            try:
                s = socket.socket()
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", port))
                print("[Portal] Ready → http://192.168.4.1" +
                      ("" if port == 80 else ":%d" % port))
                break
            except Exception as e:
                print("[Portal] Port %d failed: %s" % (port, e))
                try: s.close()
                except: pass
                s = None

        if s is None:
            raise OSError("No port available for web config portal")

        s.listen(3)

        # ── Server loop ──────────────────────────────────────────────────
        while True:
            conn, _ = s.accept()
            try:
                req = conn.recv(2048).decode('utf-8', 'ignore')

                if "GET /reload" in req:
                    wifi_list[:] = self.scan_wifi_list()
                    html = build_html()
                    _sock_sendall(conn,
                        "HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n")
                    _sock_sendall(conn, html)

                elif "POST /" in req:
                    # ── Parse + URL-decode form body ─────────────────────
                    # FIX: ure.search on raw body; URL-decode to handle
                    #      special chars in SSID / password.
                    body = req.split("\r\n\r\n", 1)[-1]
                    m_ssid = ure.search(r"ssid=([^&]*)", body)
                    m_pw   = ure.search(r"pw=([^&]*)",   body)
                    ssid = _url_decode(m_ssid.group(1)) if m_ssid else ""
                    pw   = _url_decode(m_pw.group(1))   if m_pw   else ""

                    _sock_sendall(conn,
                        "HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n"
                        "<h2 style='font-family:sans-serif;padding:20px'>"
                        "Dang ket noi toi <b>" + ssid + "</b>..."
                        "</h2>")
                    conn.close()
                    s.close()

                    self.save_wifi(ssid, pw)
                    self.ssid = ssid
                    self.pw   = pw
                    print("[Portal] User chose:", ssid)
                    return ssid, pw

                else:
                    _sock_sendall(conn,
                        "HTTP/1.1 200 OK\r\nContent-Type:text/html\r\n\r\n")
                    _sock_sendall(conn, html)

            except Exception as e:
                print("[Portal] Error:", e)
            finally:
                try: conn.close()
                except: pass


# =========================================================
# Config
# =========================================================
class ConveyorConfig:
    ssid     = None
    password = None

    mqtt_server   = 'mqtt.ohstem.vn'
    mqtt_port     = 1883
    mqtt_user     = '0_SmartConvey2025'
    mqtt_password = ''

    speed_servo   = 90
    action_servo  = 45
    default_servo = 0
    speed_motor   = 70

    # Idle belt jog: every 30 s run for 1 s to show it's alive
    idle_interval_ms = 30_000
    idle_duration_ms =  1_000

    @property
    def mqtt_topics_cmd(self):
        return ['V1']

    @property
    def mqtt_topic_status(self):
        return 'V2'


# =========================================================
# Conveyor Belt
# =========================================================
class ConveyorBelt:

    def __init__(self, cfg: ConveyorConfig):
        self.cfg = cfg

        self.md     = MotorDriverV2()
        self.servo1 = Servo(self.md, S1, 180)
        self.servo2 = Servo(self.md, S2, 180)
        self.motor  = DCMotor(self.md, M1)
        self.busy   = False

        mqtt_cfg = config.copy()
        mqtt_cfg.update({
            'ssid':     cfg.ssid,
            'wifi_pw':  cfg.password,
            'server':   cfg.mqtt_server,
            'port':     cfg.mqtt_port,
            'user':     cfg.mqtt_user,
            'password': cfg.mqtt_password,
        })
        mqtt_cfg["topics"] = [(t, self.on_mqtt_msg) for t in cfg.mqtt_topics_cmd]
        self.mqtt = MQTTClient(mqtt_cfg)
        MQTTClient.DEBUG = True

    # ── LED ──────────────────────────────────────────────────────────────

    def led_state(self, mode):
        try: neopix.show(0, hex_to_rgb(COLORS[mode]))
        except: pass
        print("[%d][LED] %s" % (utime.ticks_ms(), mode))

    # ── MQTT publish status ───────────────────────────────────────────────

    async def send_status(self, status, data=None):
        msg = {"status": status}
        if data:
            msg.update(data)
        payload = ujson.dumps(msg)
        try:
            await self.mqtt.publish(self.cfg.mqtt_topic_status, payload)
            print("[%d][MQTT TX] %s" % (utime.ticks_ms(), payload))
        except Exception as e:
            print("[%d][MQTT TX FAIL] %s" % (utime.ticks_ms(), e))

    # ── Hardware init ─────────────────────────────────────────────────────

    async def init_servo_motor(self):
        self.led_state("INIT")
        print("[%d][INIT] start" % utime.ticks_ms())

        # Brief motor test
        self.motor.run(self.cfg.speed_motor)
        await asleep_ms(300)
        self.motor.run(0)

        # Servo home sweep
        for sv in (self.servo1, self.servo2):
            try:
                sv.limit(0, self.cfg.action_servo)
                await sv.run_angle(self.cfg.action_servo, self.cfg.speed_servo)
                await sv.run_angle(self.cfg.default_servo, self.cfg.speed_servo)
            except Exception as e:
                print("[%d][INIT] Servo error: %s" % (utime.ticks_ms(), e))

        print("[%d][INIT] done" % utime.ticks_ms())
        self.led_state("READY")

    # ── Execute one conveyor action ───────────────────────────────────────

    async def perform_action(self, servo=None, action_id=None,
                             duration_ms=None, silent=False):
        """
        Run servo + motor sequence.

        Parameters
        ----------
        servo      : Servo object to actuate, or None (motor only)
        action_id  : Identifier echoed in MQTT status (int or str)
        duration_ms: How long to run the motor (default 800 ms)
        silent     : If True, skip MQTT status publish (used for idle jog)
        """
        if self.busy:
            print("[%d][ACTION] BUSY → ignore action=%s" %
                  (utime.ticks_ms(), action_id))
            if not silent:
                await self.send_status("BUSY", {"action": action_id})
            return

        self.busy    = True
        duration     = duration_ms or 800
        self.led_state("RUN")
        print("[%d][ACTION] START action=%s duration=%d" %
              (utime.ticks_ms(), action_id, duration))

        try:
            if servo:
                await servo.run_angle(self.cfg.action_servo, self.cfg.speed_servo)
                await asleep_ms(150)

            self.motor.run(self.cfg.speed_motor)
            await asleep_ms(duration)
            self.motor.run(0)

            if servo:
                await servo.run_angle(
                    self.cfg.default_servo,
                    int(self.cfg.speed_servo * 0.6)  # gentler return
                )

            print("[%d][ACTION] DONE action=%s" % (utime.ticks_ms(), action_id))
            self.led_state("IDLE")
            if not silent:
                await self.send_status("DONE", {"action": action_id})

        except Exception as e:
            self.motor.run(0)   # safety stop
            print("[%d][ACTION] ERROR: %s" % (utime.ticks_ms(), e))
            self.led_state("ERROR")
            if not silent:
                await self.send_status("ERROR",
                                       {"action": action_id, "error": str(e)})
        finally:
            self.busy = False   # always release, even on exception

    # ── MQTT message handler ──────────────────────────────────────────────

    async def on_mqtt_msg(self, topic, msg):
        msg_str = msg.decode() if isinstance(msg, bytes) else str(msg)
        print("[%d][MQTT RX] %s" % (utime.ticks_ms(), msg_str))

        action   = None
        duration = None

        try:
            parsed   = ujson.loads(msg_str)
            action   = parsed.get("action")
            duration = parsed.get("duration_ms")
        except Exception:
            # plain string / number fallback
            action = int(msg_str) if msg_str.isdigit() else msg_str.strip().upper()

        print("[%d][MQTT RX] action=%s duration=%s" %
              (utime.ticks_ms(), action, duration))

        if action == "PING":
            # Always respond to PING regardless of busy state
            await self.send_status("READY")
            return

        if self.busy:
            await self.send_status("BUSY", {"action": action})
            return

        if action == 1:
            await self.perform_action(self.servo1, 1, duration)
        elif action == 2:
            await self.perform_action(self.servo2, 2, duration)
        elif action == 3:
            await self.perform_action(None, 3, duration)
        else:
            print("[%d][MQTT RX] Unknown action: %s" % (utime.ticks_ms(), action))
            await self.send_status("ERROR",
                                   {"msg": "Unknown action", "raw": msg_str})

    # ── Setup + main loop ─────────────────────────────────────────────────

    async def setup(self):
        await self.init_servo_motor()
        print("[%d][MQTT] Connecting..." % utime.ticks_ms())
        await self.mqtt.connect()
        print("[%d][MQTT] Connected" % utime.ticks_ms())
        self.led_state("READY")

    async def run(self):
        await self.setup()
        idle_timer = utime.ticks_ms()

        while True:
            elapsed = utime.ticks_diff(utime.ticks_ms(), idle_timer)
            if elapsed > self.cfg.idle_interval_ms and not self.busy:
                # FIX: silent=True → idle jog does NOT publish MQTT status
                #      (avoids confusing the server with action=0 every 5 s)
                await self.perform_action(
                    None, "idle", self.cfg.idle_duration_ms, silent=True
                )
                idle_timer = utime.ticks_ms()

            await asleep_ms(100)


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":

    cfg  = ConveyorConfig()
    wifi = WiFiManager()

    print("[BOOT] Checking WiFi...")

    if not wifi.connect():
        print("[BOOT] WiFi failed → starting portal")
        wifi.web_config()           # saves internally; sets self.ssid/pw
        # FIX: removed redundant wifi.save_wifi() call — web_config already saves
        wifi.connect()              # connect with newly saved credentials

    cfg.ssid     = wifi.ssid
    cfg.password = wifi.pw

    blink_color(COLORS['READY'], 3, 100)

    conveyor = ConveyorBelt(cfg)
    run_loop(conveyor.run())
