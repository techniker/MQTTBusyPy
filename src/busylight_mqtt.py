# Simple and straight forward MQTT Busylight controller for Kuando HID based Busylights (Alpha and Omega)
# <tec att sixtopia.net>

import hid
import time
import paho.mqtt.client as mqtt
import threading
from enum import IntEnum
from typing import Tuple

# Vendor/Product ID values for BusyLight UC Omega(0x27bb, 0x3bcf or 0x27bb, 0x3bcd) Alpha(0x04d8, 0xf848 or 0x27bb, 0x3bca)
VENDOR_ID = 0x27bb
PRODUCT_ID = 0x3bcf

RAINBOW_COLORS = [
    (255, 0, 0),     # Red
    (255, 127, 0),   # Orange
    (255, 255, 0),   # Yellow
    (0, 255, 0),     # Green
    (0, 0, 255),     # Blue
    (75, 0, 130),    # Indigo
    (148, 0, 211)    # Violet
]

def cycle_rainbow_colors(device, stop_event):
    while not stop_event.is_set():
        for color in RAINBOW_COLORS:
            if stop_event.is_set():
                break
            turn_on_light(device, *color)
            time.sleep(0.1)  # 100ms delay for each color

def fade_color(device, color, stop_event):
    step = 5  # The amount by which brightness is increased or decreased
    delay = 0.02  # Delay between brightness changes for a smoother fade

    while not stop_event.is_set():
        for brightness in range(0, 256, step):
            if stop_event.is_set():
                break
            faded_color = tuple(int(c * (brightness / 255)) for c in color)
            turn_on_light(device, *faded_color)
            print(f"Fading in: {faded_color}")  # Debug statement
            time.sleep(delay)  # Adjust the delay for smoother fade

        for brightness in range(255, -1, -step):
            if stop_event.is_set():
                break
            faded_color = tuple(int(c * (brightness / 255)) for c in color)
            turn_on_light(device, *faded_color)
            print(f"Fading out: {faded_color}")
            time.sleep(delay)  # Adjust the delay for smoother fade

class Ring(IntEnum):
    Off = 0
    OpenOffice = 136
    Quiet = 144
    Funky = 152
    FairyTale = 160
    KuandoTrain = 168
    TelephoneNordic = 176
    TelephoneOriginal = 184
    TelephonePickMeUp = 192
    Buzz = 216

class OpCode(IntEnum):
    Jump = 0x1
    Reset = 0x2
    Boot = 0x4
    KeepAlive = 0x8

class BitField:
    def __init__(self, offset, size):
        self.offset = offset
        self.size = size

    def __get__(self, instance, owner):
        mask = (1 << self.size) - 1
        return (instance.value >> self.offset) & mask

    def __set__(self, instance, value):
        mask = (1 << self.size) - 1
        instance.value &= ~(mask << self.offset)
        instance.value |= (value & mask) << self.offset

class BitVector:
    def __init__(self, value=0, size=64):
        self.value = value
        self.size = size

    def to_bytes(self):
        return self.value.to_bytes(self.size // 8, 'big')

    def __repr__(self):
        return f"{type(self).__name__}(value={self.value:0{self.size // 4}x})"

    def reset(self):
        self.value = 0


class Instruction(BitVector):
    @classmethod
    def Jump(
        cls,
        target: int = 0,
        color: Tuple[int, int, int] = None,
        repeat: int = 0,
        on_time: int = 0,
        off_time: int = 0,
        update: int = 0,
        ringtone: Ring = Ring.Off,
        volume: int = 0,
    ) -> "Instruction":
        instruction = cls()
        instruction.cmd_hi = OpCode.Jump
        instruction.cmd_lo = target & 0x07
        instruction.repeat = repeat
        instruction.dc_on = on_time
        instruction.dc_off = off_time
        instruction.update = update
        instruction.ringtone = ringtone
        instruction.volume = volume
        if color:
            instruction.red, instruction.green, instruction.blue = color
        return instruction

    @classmethod
    def KeepAlive(cls, timeout: int) -> "Instruction":
        instruction = cls()
        instruction.cmd_hi = OpCode.KeepAlive
        instruction.cmd_lo = timeout & 0xF
        return instruction

    def __init__(self):
        super().__init__(0, 64)

    cmd = CommandField(56, 8)
    cmd_hi = CommandField(60, 4)
    cmd_lo = CommandField(56, 4)
    repeat = RepeatField(48, 8)
    red = ColorField(40, 8)
    green = ColorField(32, 8)
    blue = ColorField(24, 8)
    dc_on = DutyCycleField(16, 8)
    dc_off = DutyCycleField(8, 8)
    update = UpdateField(7, 1)
    ringtone = RingtoneField(3, 4)
    volume = VolumeField(0, 3)

    def reset(self) -> None:
        self.value = 0

    def __repr__(self):
        return f"{type(self).__name__}(value={self.value:016x})"

class CommandBuffer(BitVector):
    def __init__(self):
        super().__init__(0x00FF_FFFF_0000, 512)
        self.default = 0x00FF_FFFF_0000

    line0 = InstructionField(448, 64)
    line1 = InstructionField(384, 64)
    line2 = InstructionField(320, 64)
    line3 = InstructionField(256, 64)
    line4 = InstructionField(192, 64)
    line5 = InstructionField(128, 64)
    line6 = InstructionField(64, 64)
    line7 = InstructionField(0, 64)

    sensitivity = BitField(56, 8)
    timeout = BitField(48, 8)
    trigger = BitField(40, 8)
    padbytes = BitField(16, 24)
    checksum = CheckSumField(0, 16)

    def to_bytes(self):
        raw_bytes = self.value.to_bytes(self.size // 8, 'big')
        self.checksum = sum(raw_bytes[:-2]) & 0xFFFF
        return raw_bytes[:-2] + self.checksum.to_bytes(2, 'big')

def send_packet(device, packet):
    try:
        packet_bytes = packet.to_bytes()
        device.write(packet_bytes)
        print(f"Packet sent: {list(packet_bytes)}")
    except hid.HIDException as e:
        print(f"Failed to send packet: {e}")
    except TypeError as e:
        print(f"Type error in packet: {e}")

def open_device():
    try:
        device = hid.Device(VENDOR_ID, PRODUCT_ID)
        print("Device opened successfully")
        return device
    except hid.HIDException as e:
        print(f"Failed to open device: {e}")
        return None

def turn_on_light(device, red, green, blue):
    cmd_buf = CommandBuffer()
    instruction = Instruction.Jump(color=(red, green, blue))
    cmd_buf.line0 = instruction.value
    send_packet(device, cmd_buf)

def turn_off_light(device):
    cmd_buf = CommandBuffer()
    instruction = Instruction.Jump(color=(0, 0, 0))
    cmd_buf.line0 = instruction.value
    send_packet(device, cmd_buf)

def keep_alive(device, stop_event):
    timeout = 15
    while not stop_event.is_set():
        cmd_buf = CommandBuffer()
        instruction = Instruction.KeepAlive(timeout)
        cmd_buf.line0 = instruction.value
        send_packet(device, cmd_buf)
        time.sleep(7)

def blink_light(device, red, green, blue, on_duration, off_duration):
    cmd_buf = CommandBuffer()
    instruction = Instruction.Jump(color=(red, green, blue), on_time=on_duration, off_time=off_duration)
    cmd_buf.line0 = instruction.value
    send_packet(device, cmd_buf)

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("busylight/control")


# Global variables to manage the threads
rainbow_thread = None
rainbow_stop_event = threading.Event()
fade_thread = None
fade_stop_event = threading.Event()
keep_alive_stop_event = threading.Event()


def on_message(client, userdata, msg):
    global rainbow_thread, rainbow_stop_event, fade_thread, fade_stop_event

    payload = msg.payload.decode()
    print(f"Message received: {payload}")
    device = userdata['device']

    color_commands = {
        "color_red": (255, 0, 0),
        "color_green": (0, 255, 0),
        "color_blue": (0, 0, 255),
        "color_yellow": (255, 255, 0),
        "color_cyan": (0, 255, 255),
        "color_magenta": (255, 0, 255),
        "color_white": (255, 255, 255),
        "color_orange": (255, 165, 0),
        "color_purple": (128, 0, 128),
        "color_pink": (255, 192, 203),
        "color_brown": (165, 42, 42)
    }

    blink_commands = {
        "blink_color_red": (255, 0, 0),
        "blink_color_green": (0, 255, 0),
        "blink_color_blue": (0, 0, 255),
        "blink_color_yellow": (255, 255, 0),
        "blink_color_cyan": (0, 255, 255),
        "blink_color_magenta": (255, 0, 255),
        "blink_color_white": (255, 255, 255),
        "blink_color_orange": (255, 165, 0),
        "blink_color_purple": (128, 0, 128),
        "blink_color_pink": (255, 192, 203),
        "blink_color_brown": (165, 42, 42)
    }

    ringtone_commands = {
        "ring_off": Ring.Off,
        "ring_open_office": Ring.OpenOffice,
        "ring_quiet": Ring.Quiet,
        "ring_funky": Ring.Funky,
        "ring_fairy_tale": Ring.FairyTale,
        "ring_kuando_train": Ring.KuandoTrain,
        "ring_telephone_nordic": Ring.TelephoneNordic,
        "ring_telephone_original": Ring.TelephoneOriginal,
        "ring_telephone_pick_me_up": Ring.TelephonePickMeUp,
        "ring_buzz": Ring.Buzz
    }

    if payload in color_commands:
        red, green, blue = color_commands[payload]
        turn_on_light(device, red, green, blue)
    elif payload in blink_commands:
        red, green, blue = blink_commands[payload]
        blink_light(device, red, green, blue, 5, 5)
    elif payload in ringtone_commands:
        ringtone = ringtone_commands[payload]
        cmd_buf = CommandBuffer()
        instruction = Instruction.Jump(ringtone=ringtone, update=1, volume=7, repeat=1, on_time=0, off_time=0)  # Call ringtone once
        cmd_buf.line0 = instruction.value
        send_packet(device, cmd_buf)
        
        # Blink red once after ringtone
        time.sleep(0.5)  # Small delay to ensure ringtone command is processed first
        blink_light(device, 255, 0, 0, 1, 1)  # Blink red once with 1-second on and off time
    elif payload == "stop_ringtone":
        cmd_buf = CommandBuffer()
        instruction = Instruction.Jump(ringtone=Ring.Off, update=1, volume=0)  # Stop the ringtone
        cmd_buf.line0 = instruction.value
        send_packet(device, cmd_buf)
    elif payload == "off":
        if rainbow_thread and rainbow_thread.is_alive():
            rainbow_stop_event.set()
            rainbow_thread.join()
        turn_off_light(device)
    elif payload == "rainbow_on":
        # Stop any existing rainbow thread
        if rainbow_thread and rainbow_thread.is_alive():
            rainbow_stop_event.set()
            rainbow_thread.join()
        rainbow_stop_event.clear()
        rainbow_thread = threading.Thread(target=cycle_rainbow_colors, args=(device, rainbow_stop_event))
        rainbow_thread.start()
    elif payload == "rainbow_off":
        if rainbow_thread and rainbow_thread.is_alive():
            rainbow_stop_event.set()
            rainbow_thread.join()
        turn_off_light(device)
    elif payload.startswith("fade_"):
        color_name = payload.split("_", 1)[1]
        if color_name in color_commands:
            color = color_commands[color_name]
            # Stop any existing fade thread
            if fade_thread and fade_thread.is_alive():
                fade_stop_event.set()
                fade_thread.join()
            fade_stop_event.clear()
            fade_thread = threading.Thread(target=fade_color, args=(device, color, fade_stop_event))
            fade_thread.start()
    elif payload == "fade_off":
        if fade_thread and fade_thread.is_alive():
            fade_stop_event.set()
            fade_thread.join()
        turn_off_light(device)
    elif payload.startswith("raw_color"):
        try:
            _, color_values = payload.split(" ")
            red, green, blue = map(int, color_values.split(","))
            if 0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255:
                turn_on_light(device, red, green, blue)
            else:
                print("Color values must be between 0 and 255")
        except ValueError:
            print("Invalid color format. Use 'raw_color xxx,xxx,xxx'")
    elif payload == "reset_device":
        reset_device(device)
    elif payload == "device_bootloader":
        start_bootloader(device)


if __name__ == "__main__":
    device = open_device()
    if device:
        mqtt_client = mqtt.Client(client_id="busylight-controller", userdata={"device": device})
        mqtt_client.username_pw_set("user", "password")
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        mqtt_client.connect("mqtt-broker-url", 1883, 60)

    keep_alive_thread = threading.Thread(target=keep_alive, args=(device, keep_alive_stop_event))
    keep_alive_thread.start()

    try:
        mqtt_client.loop_start()
        # Keep the main thread alive to listen for MQTT messages
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        turn_off_light(device)
    finally:
        mqtt_client.loop_stop()
        keep_alive_stop_event.set()
        keep_alive_thread.join()
        if rainbow_thread and rainbow_thread.is_alive():
            rainbow_stop_event.set()
            rainbow_thread.join()
        if fade_thread and fade_thread.is_alive():
            fade_stop_event.set()
            fade_thread.join()
        device.close()
        print("Device closed")