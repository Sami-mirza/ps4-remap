"""Create a userspace virtual gamepad on macOS via IOHIDUserDevice (ctypes)."""
from __future__ import annotations

import ctypes
import ctypes.util
import sys
from typing import Optional

# Generic USB gamepad (not Sony VID) so SDL uses IOKit instead of GameController.
VENDOR_ID = 0x1209
PRODUCT_ID = 0x4453  # generic (not Sony) so SDL uses IOKit on macOS
PRODUCT_NAME = "ps4-remap Virtual Gamepad"
MANUFACTURER = "ps4-remap"

# Game Pad: 16 buttons, hat, 4 stick axes + 2 triggers (8-bit)
# Report ID omitted (single report).
HID_DESCRIPTOR = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x05,        # Usage (Game Pad)
    0xA1, 0x01,        # Collection (Application)
    # Buttons 1-16
    0x05, 0x09,        #   Usage Page (Button)
    0x19, 0x01,        #   Usage Minimum (1)
    0x29, 0x10,        #   Usage Maximum (16)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x10,        #   Report Count (16)
    0x81, 0x02,        #   Input (Data,Var,Abs)
    # Hat switch
    0x05, 0x01,        #   Usage Page (Generic Desktop)
    0x09, 0x39,        #   Usage (Hat switch)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x07,        #   Logical Maximum (7)
    0x35, 0x00,        #   Physical Minimum (0)
    0x46, 0x3B, 0x01,  #   Physical Maximum (315)
    0x65, 0x14,        #   Unit (Degrees)
    0x75, 0x04,        #   Report Size (4)
    0x95, 0x01,        #   Report Count (1)
    0x81, 0x42,        #   Input (Data,Var,Abs,Null)
    0x75, 0x04,        #   Report Size (4) padding
    0x95, 0x01,        #   Report Count (1)
    0x81, 0x03,        #   Input (Const,Var,Abs)
    # X Y Z Rz Rx Ry
    0x09, 0x30,        #   Usage (X)
    0x09, 0x31,        #   Usage (Y)
    0x09, 0x32,        #   Usage (Z)
    0x09, 0x35,        #   Usage (Rz)
    0x09, 0x33,        #   Usage (Rx)
    0x09, 0x34,        #   Usage (Ry)
    0x15, 0x00,        #   Logical Minimum (0)
    0x26, 0xFF, 0x00,  #   Logical Maximum (255)
    0x75, 0x08,        #   Report Size (8)
    0x95, 0x06,        #   Report Count (6)
    0x81, 0x02,        #   Input (Data,Var,Abs)
    0xC0,              # End Collection
])

# Button index in report bitfield (0-based) for logical names
BTN_BITS = {
    "cross": 0,
    "circle": 1,
    "square": 2,
    "triangle": 3,
    "l1": 4,
    "r1": 5,
    "l2": 6,   # also analog; digital bit optional
    "r2": 7,
    "share": 8,
    "options": 9,
    "l3": 10,
    "r3": 11,
    "ps": 12,
}


def _load_cf_iokit():
    cf_path = ctypes.util.find_library("CoreFoundation")
    iokit_path = ctypes.util.find_library("IOKit")
    if not cf_path or not iokit_path:
        sys.exit("[-] CoreFoundation / IOKit not found (are you on macOS?)")
    cf = ctypes.CDLL(cf_path)
    iokit = ctypes.CDLL(iokit_path)
    return cf, iokit


class VirtualGamepad:
    """Userspace HID gamepad. May require HID virtual-device entitlement on newer macOS."""

    REPORT_LEN = 9  # 2 btn + 1 hat/pad + 6 axes

    def __init__(self):
        self._cf, self._iokit = _load_cf_iokit()
        self._setup_protos()
        self._device = None
        self._report = (ctypes.c_uint8 * self.REPORT_LEN)()
        self._create()

    def _setup_protos(self):
        cf, iokit = self._cf, self._iokit
        self.CFSTR = cf.CFStringCreateWithCString
        self.CFSTR.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        self.CFSTR.restype = ctypes.c_void_p

        self.CFNumber = cf.CFNumberCreate
        self.CFNumber.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        self.CFNumber.restype = ctypes.c_void_p

        self.CFData = cf.CFDataCreate
        self.CFData.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long]
        self.CFData.restype = ctypes.c_void_p

        self.CFDict = cf.CFDictionaryCreateMutable
        self.CFDict.argtypes = [ctypes.c_void_p, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
        self.CFDict.restype = ctypes.c_void_p

        self.CFDictSet = cf.CFDictionarySetValue
        self.CFDictSet.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

        self.CFRelease = cf.CFRelease
        self.CFRelease.argtypes = [ctypes.c_void_p]

        iokit.IOHIDUserDeviceCreate.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        iokit.IOHIDUserDeviceCreate.restype = ctypes.c_void_p
        iokit.IOHIDUserDeviceHandleReport.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long
        ]
        iokit.IOHIDUserDeviceHandleReport.restype = ctypes.c_int

    def _s(self, text: str):
        return self.CFSTR(None, text.encode(), 0x08000100)  # kCFStringEncodingUTF8

    def _num(self, value: int, ctype=ctypes.c_uint32):
        v = ctype(value)
        # kCFNumberSInt32Type = 3, SInt64 = 4, IntType = 9
        return self.CFNumber(None, 3, ctypes.byref(v))

    def _create(self):
        props = self.CFDict(None, 0, None, None)
        desc = self.CFData(None, HID_DESCRIPTOR, len(HID_DESCRIPTOR))
        self.CFDictSet(props, self._s("ReportDescriptor"), desc)
        self.CFDictSet(props, self._s("VendorID"), self._num(VENDOR_ID))
        self.CFDictSet(props, self._s("ProductID"), self._num(PRODUCT_ID))
        self.CFDictSet(props, self._s("PrimaryUsagePage"), self._num(0x01))
        self.CFDictSet(props, self._s("PrimaryUsage"), self._num(0x05))
        self.CFDictSet(props, self._s("Manufacturer"), self._s(MANUFACTURER))
        self.CFDictSet(props, self._s("Product"), self._s(PRODUCT_NAME))

        device = self._iokit.IOHIDUserDeviceCreate(None, props)
        self.CFRelease(props)
        if not device:
            sys.exit(
                "[-] macOS refused to create a virtual HID gamepad.\n"
                "    Apple restricts IOHIDUserDevice without a special entitlement.\n\n"
                "    Options:\n"
                "      1) Use this tool on Linux or Windows (full DualShock 4 emulation)\n"
                "      2) Advanced: allow virtual HID (disables AMFI) — see README\n"
                "         then re-run this script\n"
            )
        self._device = device
        # Neutral report
        self._report[3] = 128
        self._report[4] = 128
        self._report[5] = 128
        self._report[6] = 128
        self.flush()

    @staticmethod
    def _hat(dx: int, dy: int) -> int:
        # 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW, 8=none
        table = {
            (0, -1): 0, (1, -1): 1, (1, 0): 2, (1, 1): 3,
            (0, 1): 4, (-1, 1): 5, (-1, 0): 6, (-1, -1): 7, (0, 0): 8,
        }
        return table.get((dx, dy), 8)

    def apply(self, state: dict) -> None:
        buttons = state.get("buttons", set())
        bits = 0
        for name, bit in BTN_BITS.items():
            if name in buttons:
                bits |= (1 << bit)
        # analog triggers also set digital bits when pressed hard
        if state.get("l2", 0) > 0.5:
            bits |= (1 << BTN_BITS["l2"])
        if state.get("r2", 0) > 0.5:
            bits |= (1 << BTN_BITS["r2"])

        self._report[0] = bits & 0xFF
        self._report[1] = (bits >> 8) & 0xFF
        hat = self._hat(int(state.get("dpad_x", 0)), int(state.get("dpad_y", 0)))
        self._report[2] = hat & 0x0F

        def stick(v: float) -> int:
            return max(0, min(255, int(round((v + 1.0) * 0.5 * 255))))

        def trig(v: float) -> int:
            return max(0, min(255, int(round(float(v) * 255))))

        self._report[3] = stick(state.get("lx", 0.0))
        self._report[4] = stick(state.get("ly", 0.0))
        self._report[5] = stick(state.get("rx", 0.0))
        self._report[6] = stick(state.get("ry", 0.0))
        self._report[7] = trig(state.get("l2", 0.0))
        self._report[8] = trig(state.get("r2", 0.0))
        self.flush()

    def flush(self) -> None:
        if not self._device:
            return
        rc = self._iokit.IOHIDUserDeviceHandleReport(
            self._device, ctypes.byref(self._report), self.REPORT_LEN
        )
        if rc != 0:
            # kIOReturnSuccess == 0
            pass

    def close(self) -> None:
        if self._device:
            self.CFRelease(self._device)
            self._device = None
