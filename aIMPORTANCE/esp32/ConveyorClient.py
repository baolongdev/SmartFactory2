from servo import *
from mdv2 import *
from mqtt_as import MQTTClient, config
from wifi import *
from pins import *
from motor import *
from abutton import *
import ujson
import utime

# ========================================
# LED colors
# ========================================
COLORS = {
    'INIT': '#ff0000',
    'READY': '#00ff00',
    'ERROR': '#ff00ff',
    'RUN': '#0000ff',
    'IDLE': '#ffff00'
}

# ========================================
# Conveyor Configuration
# ========================================
class ConveyorConfig:
    ssid = 'ACLAB'
    password = 'ACLAB2023'
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

# ========================================
# ConveyorBelt Class
# ========================================
class ConveyorBelt:
    def __init__(self, cfg: ConveyorConfig):
        self.cfg = cfg
        self.md = MotorDriverV2()
        self.servo1 = Servo(self.md, S1, 180)
        self.servo2 = Servo(self.md, S2, 180)
        self.motor = DCMotor(self.md, M1)
        self.led = Pins(D13_PIN)
        self.btn = aButton(BOOT_PIN)
        self.busy = False

        # MQTT setup
        self.mqtt_cfg = config.copy()
        self.mqtt_cfg.update({
            'ssid': cfg.ssid,
            'wifi_pw': cfg.password,
            'server': cfg.mqtt_server,
            'port': cfg.mqtt_port,
            'user': cfg.mqtt_user,
            'password': cfg.mqtt_password
        })
        self.mqtt_cfg['topics'] = [(t, self.on_mqtt_msg) for t in cfg.mqtt_topics_cmd]
        self.mqtt = MQTTClient(self.mqtt_cfg)
        MQTTClient.DEBUG = True

    # ----------------------------------------
    # LED Control
    # ----------------------------------------
    def led_state(self, state):
        try:
            neopix.show(0, hex_to_rgb(COLORS.get(state, '#000000')))
        except Exception:
            pass
        print(f"[{utime.ticks_ms()} ms][LED] State={state}")

    # ----------------------------------------
    # MQTT Status
    # ----------------------------------------
    async def send_status(self, status, data=None):
        msg = {'status': status}
        if data:
            msg.update(data)
        payload = ujson.dumps(msg)
        try:
            await self.mqtt.publish(self.cfg.mqtt_topic_status, payload, retain=False)
            print(f"[{utime.ticks_ms()} ms][MQTT] SENT: {payload}")
        except Exception as e:
            print(f"[{utime.ticks_ms()} ms][MQTT] SEND FAILED: {e}")

    # ----------------------------------------
    # Initialize Servo + Motor
    # ----------------------------------------
    async def init_servo_motor(self):
        self.led_state('INIT')
        print(f"[{utime.ticks_ms()} ms] Init motor+servo start")
        self.motor.run(self.cfg.speed_motor)
        await asleep_ms(500)
        self.motor.run(0)
        for s in [self.servo1, self.servo2]:
            try:
                s.limit(min=self.cfg.default_servo, max=self.cfg.action_servo)
                await s.run_angle(self.cfg.action_servo, self.cfg.speed_servo)
                await s.run_angle(self.cfg.default_servo, self.cfg.speed_servo)
            except Exception as e:
                print(f"[{utime.ticks_ms()} ms] Servo init error: {e}")
        print(f"[{utime.ticks_ms()} ms] Init motor+servo done")
        self.led_state('READY')

    # ----------------------------------------
    # Perform Generic Action
    # ----------------------------------------
    async def perform_action(self, servo=None, action_id=None, duration_ms=None):
        if self.busy:
            print(f"[{utime.ticks_ms()} ms] Ignored action {action_id} because system is BUSY")
            await self.send_status("BUSY", {"action": action_id})
            return

        self.busy = True
        duration = duration_ms or getattr(self.cfg, f"action{action_id}_duration_ms", 1000)

        try:
            print(f"[{utime.ticks_ms()} ms] Start action {action_id}, duration={duration}")
            self.led_state('RUN')

            # 1️⃣ Servo di chuyển tới góc thao tác
            if servo:
                servo.limit(min=0, max=self.cfg.action_servo)
                print(f"[{utime.ticks_ms()} ms] Servo moving to {self.cfg.action_servo}")
                await servo.run_angle(self.cfg.action_servo, self.cfg.speed_servo)
                await asleep_ms(300)

            # 2️⃣ Chạy motor
            self.motor.run(self.cfg.speed_motor)
            await asleep_ms(duration)

            # 3️⃣ Dừng motor và trả servo
            self.motor.run(0)
            await asleep_ms(200)
            if servo:
                print(f"[{utime.ticks_ms()} ms] Servo returning to {self.cfg.default_servo}")
                smooth_speed = max(20, int(self.cfg.speed_servo * 0.5))
                await servo.run_angle(self.cfg.default_servo, smooth_speed)
                await asleep_ms(200)

            # 4️⃣ Hoàn tất
            self.led_state('IDLE')
            await self.send_status('DONE', {'action': action_id})
            print(f"[{utime.ticks_ms()} ms] ✅ Action {action_id} DONE")

        except Exception as e:
            self.motor.run(0)
            self.led_state('ERROR')
            await self.send_status('ERROR', {'action': action_id, 'error': str(e)})
            print(f"[{utime.ticks_ms()} ms] ❌ Action {action_id} ERROR: {e}")

        finally:
            self.busy = False

    # ----------------------------------------
    # Idle Action
    # ----------------------------------------
    async def idle_action(self, duration_ms=None):
        if self.busy:
            return
        duration = duration_ms or self.cfg.idle_duration_ms
        self.led_state('IDLE')
        self.motor.run(self.cfg.speed_motor)
        await asleep_ms(duration)
        self.motor.run(0)
        print(f"[{utime.ticks_ms()} ms] IDLE Done")

    # ----------------------------------------
    # MQTT Handler
    # ----------------------------------------
    async def on_mqtt_msg(self, topic, msg):
        msg_str = msg.decode() if isinstance(msg, bytes) else str(msg)
        action, duration = None, None
        try:
            parsed = ujson.loads(msg_str)
            action = parsed.get("action")
            duration = parsed.get("duration_ms")
        except Exception:
            action = int(msg_str) if msg_str.isdigit() else msg_str.upper()

        if self.busy:
            print(f"[{utime.ticks_ms()} ms] Received action while BUSY: {action}")
            await self.send_status("BUSY", {"action": action})
            return

        if action == 1:
            await self.perform_action(self.servo1, 1, duration)
        elif action == 2:
            await self.perform_action(self.servo2, 2, duration)
        elif action == 3:
            await self.perform_action(None, 3, duration)
        elif action == "PING":
            await self.send_status("READY")
        else:
            await self.send_status("ERROR", {"msg": "Unknown action", "payload": msg_str})

    # ----------------------------------------
    # LED Blink Task
    # ----------------------------------------
    async def led_blink_task(self, interval_ms=500):
        while True:
            if not self.busy:
                self.led_state('RUN')
                await asleep_ms(interval_ms)
                self.led_state('IDLE')
                await asleep_ms(interval_ms)
            else:
                await asleep_ms(100)

    # ----------------------------------------
    # Button Handler
    # ----------------------------------------
    async def handle_boot(self, pressed):
        if pressed:
            if self.busy:
                print(f"[{utime.ticks_ms()} ms] Boot pressed but system busy -> ignored")
                return
            await self.perform_action(self.servo1, 1)
            await self.perform_action(self.servo2, 2)
        else:
            self.motor.run(0)
            for s in [self.servo1, self.servo2]:
                try:
                    await s.run_angle(self.cfg.default_servo, self.cfg.speed_servo)
                except Exception:
                    pass
            self.led_state('IDLE')

    # ----------------------------------------
    # Setup & Run
    # ----------------------------------------
    async def setup(self):
        await self.init_servo_motor()
        wifi = Wifi()
        wifi.connect(self.cfg.ssid, self.cfg.password)
        await self.mqtt.connect()
        self.led_state('READY')
        self.btn.pressed(lambda: create_task(self.handle_boot(True)))
        self.btn.released(lambda: create_task(self.handle_boot(False)))
        create_task(self.led_blink_task())

    async def run(self):
        await self.setup()
        last_idle = utime.ticks_ms()
        while True:
            now = utime.ticks_ms()
            if utime.ticks_diff(now, last_idle) > self.cfg.idle_interval_ms:
                if not self.busy:
                    await self.idle_action()
                last_idle = now
            await asleep_ms(100)

# ========================================
# Main
# ========================================
if __name__ == '__main__':
    conveyor = ConveyorBelt(ConveyorConfig())
    run_loop(conveyor.run())
