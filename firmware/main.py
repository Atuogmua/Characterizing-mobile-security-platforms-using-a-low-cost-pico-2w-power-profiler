import network, socket, time, json
from machine import I2C, Pin, SPI
import dht
from ina219 import INA219
from ssd1306 import SSD1306_I2C

# Loading configuration
with open("config.json") as f:
    cfg = json.load(f)

# INA219 setup
i2c = I2C(1, sda=Pin(10), scl=Pin(11), freq=400000)
ina = INA219(0.1, i2c)
ina.configure()

# OLED setup
OLED_W, OLED_H = 128, 64
oled = SSD1306_I2C(OLED_W, OLED_H, i2c)

# Button setup
button = Pin(12, Pin.IN, Pin.PULL_UP)

# DHT11 temperature sensor setup
temp_sensor = dht.DHT11(Pin(15))
ambient_temp = 0.0
ambient_hum = 0.0
last_temp_read = 0

# Display modes and state
MODES = ["graph_current", "graph_voltage", "graph_power", "text"]
mode_index = 0
last_btn = 1

# Rolling history
HIST_LEN = OLED_W
hist_ma = [0.0] * HIST_LEN
hist_v = [0.0] * HIST_LEN
hist_mw = [0.0] * HIST_LEN

def push(hist, val):
    hist.pop(0)
    hist.append(val)

# Graph drawing
GRAPH_Y = 12
GRAPH_H = OLED_H - GRAPH_Y

def draw_graph(label, unit, hist):
    oled.fill(0)
    lo = min(hist)
    hi = max(hist)
    if hi == lo:
        hi = lo + 1

    oled.text(f"{label}: {hist[-1]:.1f}{unit}", 0, 0)

    for x in range(HIST_LEN):
        frac = (hist[x] - lo) / (hi - lo)
        y = OLED_H - 1 - int(frac * (GRAPH_H - 1))
        oled.pixel(x, y, 1)

    oled.text(f"{hi:.1f}", 0, GRAPH_Y)
    oled.text(f"{lo:.1f}", 0, OLED_H - 8)
    oled.show()

def draw_text(v, ma, mw):
    oled.fill(0)
    oled.text("\tPower monitoring", 0, 0)
    oled.text(f"V:  {v:.3f} V", 0, 16)
    oled.text(f"mA: {ma:.1f}", 0, 28)
    oled.text(f"mW: {mw:.1f}", 0, 40)
    oled.text(f"t: {time.ticks_ms()//1000}s", 0, 54)
    oled.show()

# Connecting to the network
oled.fill(0)
oled.text("Connecting...", 0, 28)
oled.show()

if cfg["connection"] == "wifi":
    nic = network.WLAN(network.STA_IF)
    nic.active(True)
    nic.connect(cfg["ssid"], cfg["password"])
elif cfg["connection"] == "ethernet":
    spi = SPI(0, baudrate=31_250_000, mosi=Pin(19), miso=Pin(16), sck=Pin(18))
    nic = network.WIZNET5K(spi, Pin(17), Pin(20))
    nic.active(True)
else:
    raise ValueError(f"Unknown connection: {cfg["connection"]}")

while not nic.isconnected():
    time.sleep(0.5)
print("Connected:", nic.ifconfig()[0])

s = socket.socket()
s.connect((cfg["laptop_ip"], cfg["port"]))
print("Sending to", cfg["laptop_ip"])

while True:
    v = ina.voltage()
    ma = ina.current()
    mw = ina.power()

    # Read DHT11 every 2 seconds
    now = time.ticks_ms()
    if time.ticks_diff(now, last_temp_read) > 2000:
        try:
            temp_sensor.measure()
            ambient_temp = temp_sensor.temperature()
            ambient_hum = temp_sensor.humidity()
        except OSError:
            pass
        last_temp_read = now

    push(hist_ma, ma)
    push(hist_v, v)
    push(hist_mw, mw)

    btn = button.value()
    if btn == 0 and last_btn == 1:
        mode_index = (mode_index + 1) % len(MODES)
        time.sleep_ms(200)
    last_btn = btn

    mode = MODES[mode_index]
    if mode == "graph_current":
        draw_graph("mA", "mA", hist_ma)
    elif mode == "graph_voltage":
        draw_graph("V", "V", hist_v)
    elif mode == "graph_power":
        draw_graph("mW", "mW", hist_mw)
    else:
        draw_text(v, ma, mw)

    line = f"{time.ticks_ms()},{v:.3f},{ma:.1f},{mw:.1f},{ambient_temp},{ambient_hum}\n"
    s.send(line.encode())

    time.sleep_ms(100)