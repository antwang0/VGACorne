"""Electrical design of the VGACorne boards.

* ``main``      -- right half (geometry.MAIN_SIDE): 21 HE sensors, 3 muxes, the
                   MCU module's landing pads, USB-C, the optional trackpad, link port.
* ``satellite`` -- left half: 23 HE sensors (the Corne's 21 and two mouse
                   buttons), a rotary encoder, 3 muxes, cable buffer, LDO,
                   link port.
* ``link``      -- VGA daughterboard (one per half, identical): vertical DE-15
                   socket screwed to the case wall, wired to the half's PCB
                   with a 10-pin JST-SH pigtail.
* ``module_*``  -- the castellated MCU modules, soldered onto the main PCB.

Only the main half has a microcontroller. The satellite's three mux outputs
travel to the MCU's ADC over the VGA cable's three 75-ohm coax pairs; the three
mux select lines ride HSYNC, VSYNC and SDA; +5 V rides pin 9. See
docs/architecture.md for the rationale.
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import MAIN_SIDE, MODULE_SIZE, SATELLITE_SIDE, all_keys, frame_keys
from .trackpad import MODEL as PAD
from .schematic import Circuit, Part

REV = "0.1"

# ---------------------------------------------------------------------------
# Sensor choice. Everything that depends on it (firmware polarity, the
# "cable unplugged" pull direction) is derived from here.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensorChoice:
    lib_id: str
    mpn: str
    # libhmk: true if the ADC reading falls as the key is pressed. For
    # sensors on B.Cu this depends on the switch magnet polarity; verify at
    # bring-up with the hmkconf debug view.
    invert_adc: bool
    initial_rest_value: int
    initial_bottom_out_threshold: int
    # Travel curve for the QMK port: distance ~ log(1 + a x). 0.0082 reproduces
    # libhmk's table (fitted to GEON Raw HE + OH49E-S); re-fit for your sensor.
    travel_curve: float = 0.0082


SENSOR = SensorChoice(
    lib_id="Sensor_Magnetic:DRV5055A3xDBZxQ1",
    mpn="DRV5055A3QDBZR",
    invert_adc=True,
    initial_rest_value=2400,
    initial_bottom_out_threshold=650,
)

# ---------------------------------------------------------------------------
# Footprints and common parts
# ---------------------------------------------------------------------------

R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
MUX_FP = "Package_SO:TSSOP-16_4.4x5mm_P0.65mm"
JST10_FP = "Connector_JST:JST_SH_SM10B-SRSS-TB_1x10-1MP_P1.00mm_Horizontal"
PTC_FP = "Fuse:Fuse_0805_2012Metric"

# JST-SH link cable pinout -- identical on main, satellite and daughterboard.
# Use a 1:1 ("same side") SH cable.
LINK_PINS = {
    "1": "+5V_LINK", "2": "GND", "3": "LINK_S0", "4": "LINK_S1", "5": "LINK_S2",
    "6": "LINK_DET", "7": "GND", "8": "LINK_A", "9": "LINK_B", "10": "LINK_C",
}

# DE-15 (VGA) pin -> signal. Pins keep their VGA roles: analog on the coax
# pairs, logic on the sync/DDC wires, +5 V on the DDC supply pin.
VGA_PINS = {
    "1": "LINK_A", "2": "LINK_B", "3": "LINK_C",  # RED/GREEN/BLUE coax
    "6": "GND", "7": "GND", "8": "GND",  # coax returns
    "5": "GND", "10": "GND",
    "13": "LINK_S0", "14": "LINK_S1",  # HSYNC / VSYNC
    "12": "LINK_S2",  # DDC SDA
    "9": "VGA_P9", "15": "VGA_P15",  # +5V / DDC SCL, routed through JP1/JP2
    "SH": "GND",
}


def R(ref, value, a, b, block, dnp=False, fp=R0402, **kw):
    return Part(ref, "Device:R", value, fp, {"1": a, "2": b}, block, dnp=dnp, **kw)


def C(ref, value, a, b, block, fp=C0402, **kw):
    return Part(ref, "Device:C", value, fp, {"1": a, "2": b}, block, **kw)


# ---------------------------------------------------------------------------
# Sensor array + muxes (identical on both halves)
# ---------------------------------------------------------------------------

# Mux channel assignment, outer to inner. The satellite fills all 24 channels:
# its mouse column (M0, M1 and the rotary encoder) takes mux C's last three; on
# the main half those are tied to ground.
MUX_KEYS = {
    "A": ["C0R0", "C0R1", "C0R2", "C1R0", "C1R1", "C1R2", "C2R0", "C2R1"],
    "B": ["C2R2", "C3R0", "C3R1", "C3R2", "C4R0", "C4R1", "C4R2", "T0"],
    "C": ["C5R0", "C5R1", "C5R2", "T1", "T2", "M0", "M1", "ENC"],
}
MUX_REFS = {"A": "U11", "B": "U12", "C": "U13"}
KEY_ORDER = [k.name for k in all_keys()]  # C0R0..C5R2, T0..T2, M0, M1

# Rotary encoder: its A/B contacts (common to GND) are summed into one voltage
# on the ENC mux channel, each contact pulled up and weighted by its own
# resistor, so each of the four contact states gives its own level (see
# qmk.encoder_levels). 1 nF keeps the node quiet between mux samples.
ENCODER_PULL_UP = 10e3
ENCODER_SUM = {"A": 47e3, "B": 100e3}


def key_index(name: str) -> int:
    """1-based per-half index used for SWn / HEn / C1nn / R3nn / C2nn."""
    return KEY_ORDER.index(name) + 1


def sensor_array(select_nets: tuple[str, str, str], com_nets: dict[str, str], side: str) -> list[Part]:
    parts: list[Part] = []
    keys = frame_keys(side)
    present = {k.name for k in keys} | ({"ENC"} if side == SATELLITE_SIDE else set())
    for key in keys:
        n = key_index(key.name)
        net = f"HE_{key.name}"
        fp = "vgacorne:SW_HE_MX_1u" if key.w == 1 else "vgacorne:SW_HE_MX_1.5u"
        parts += [
            Part(f"SW{n}", "Mechanical:MountingHole", f"{key.name}", fp, {}, "keys", key=key.name,
                 description="Hall-effect switch position (plate-mounted, not soldered)"),
            Part(f"HE{n}", SENSOR.lib_id, SENSOR.mpn, "Package_TO_SOT_SMD:SOT-23",
                 {"1": "+3.3VA", "2": f"{net}_OUT", "3": "GND"}, "keys", key=key.name,
                 fields={"MPN": SENSOR.mpn}),
            C(f"C{100 + n}", "100n", "+3.3VA", "GND", "keys", key=key.name),
            # TI: no capacitor straight on the DRV5055 output, it can oscillate.
            # The 4.7 nF stays on the mux side as the charge reservoir it samples.
            R(f"R{300 + n}", "1k", f"{net}_OUT", net, "keys", key=key.name),
            C(f"C{200 + n}", "4.7n", net, "GND", "keys", key=key.name),
        ]
    for mux, names in MUX_KEYS.items():
        pins = {"VCC": "+3.3VA", "VEE": "GND", "GND": "GND", "~{E}": "GND",
                "S0": select_nets[0], "S1": select_nets[1], "S2": select_nets[2],
                "A": com_nets[mux]}
        for ch in range(8):
            name = names[ch] if ch < len(names) else None
            pins[f"A{ch}"] = ("ENC" if name == "ENC" else f"HE_{name}") if name in present else "GND"
        used = [n for n in names if n in present]
        parts.append(Part(MUX_REFS[mux], "74xx:74HC4051", "SN74LV4051APWR", MUX_FP, pins, "mux",
                          fields={"MPN": "SN74LV4051APWR"},
                          description=f"8:1 analog mux {mux} ({', '.join(used)})"))
    parts.append(C("C31", "100n", "+3.3VA", "GND", "mux"))
    parts.append(C("C32", "100n", "+3.3VA", "GND", "mux"))
    parts.append(C("C33", "100n", "+3.3VA", "GND", "mux"))
    return parts


def standoffs(side: str, block="mech") -> list[Part]:
    from .geometry import standoffs as pts
    return [Part(f"H{i + 1}", "Mechanical:MountingHole", "M2 standoff", "vgacorne:Standoff_M2", {}, block,
                 description="PCB-to-plate M2 standoff")
            for i in range(len(pts(side)))]


def link_esd(block="link") -> list[Part]:
    """ESD clamps on every cable line, right next to J3 (the daughterboard has no room)."""
    return [
        Part("U6", "Power_Protection:SRV05-4", "SRV05-4", "Package_TO_SOT_SMD:SOT-23-6",
             {"IO1": "LINK_S0", "IO2": "LINK_S1", "IO3": "LINK_S2", "IO4": "LINK_DET",
              "VP": "+5V_LINK", "VN": "GND"}, block, fields={"MPN": "SRV05-4"}),
        Part("U7", "Power_Protection:SRV05-4", "SRV05-4", "Package_TO_SOT_SMD:SOT-23-6",
             {"IO1": "LINK_A", "IO2": "LINK_B", "IO3": "LINK_C",
              "VP": "+5V_LINK", "VN": "GND"}, block, fields={"MPN": "SRV05-4"}),
    ]


def link_connector(block="link") -> Part:
    return Part("J3", "Connector_Generic_MountingPin:Conn_01x10_MountingPin", "SM10B-SRSS-TB", JST10_FP,
                dict(LINK_PINS), block, fields={"MPN": "SM10B-SRSS-TB"},
                description="Link cable to the VGA daughterboard (JST-SH 10p, 1:1 cable)")


# ---------------------------------------------------------------------------
# Main half
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# MCU module interface
# ---------------------------------------------------------------------------

_MW, _MH = MODULE_SIZE
LANDING_FP = f"vgacorne:Module_Castellated_Landing_2x12_P1.27mm_{_MW:g}x{_MH:g}mm"
CASTELLATED_FP = f"vgacorne:Module_Castellated_2x12_P1.27mm_{_MW:g}x{_MH:g}mm"

# The module connector: 2 x 12 castellated pads on the module, soldered onto the
# landing pads J4 on the main PCB. Numbered as on J4; net names are the same on
# both boards. Odd pins run along the module's back edge (towards the link
# connector and, on the right half, the USB-C), even pins along its front edge,
# each left to right. Only pads beside each other on the same edge are
# neighbours, and each edge follows the order of the LQFP pins that reach it:
# - back: reset/boot, the trackpad bus, supplies, SWD, then the USB pair
#   between grounds at the corner nearest the USB-C;
# - front: the select lines, a ground, the analog supply (the module's VDDA and
#   ADC reference), the six ADC inputs together, then cable detect.
MODULE_PINS = {
    "1": "NRST", "3": "BOOT",  # BOOT: carrier button pulls it to +3V3; the module decides what that means
    "5": "I2C_SDA", "7": "I2C_SCL",  # trackpad bus; pulled up on the carrier
    "9": "+5V", "11": "+3V3",
    "13": "SWCLK", "15": "SWDIO",
    "17": "GND", "19": "USB_DP", "21": "USB_DN", "23": "GND",
    "2": "MUX_S0", "4": "MUX_S1", "6": "MUX_S2",
    "8": "GND", "10": "+3.3VA",
    "12": "ADC_L_A", "14": "ADC_L_B", "16": "ADC_L_C",
    "18": "ADC_R_A", "20": "ADC_R_B", "22": "ADC_R_C",
    "24": "DET",
}


def mating_pin(n: str) -> str:
    """Main-PCB landing pad that module pad ``n`` is soldered to.

    The module sits face up on the landing pads and both footprints are drawn
    the same way round, so pad n meets pad n. checks.module_connector verifies
    this geometrically on the real PCBs.
    """
    return n


def module_header_pins() -> dict[str, str]:
    return {mating_pin(n): net for n, net in MODULE_PINS.items()}


# LQFP-64 pins used for keyboard signals. The AT32F405RCT7 and STM32F446RET6 share
# these pin numbers, so both modules (and their firmware configs) use the same map.
MCU_SIGNAL_PINS = {
    "14": "ADC_L_A", "15": "ADC_L_B", "16": "ADC_L_C",  # PA0..PA2: local muxes
    "17": "ADC_R_A", "20": "ADC_R_B", "21": "ADC_R_C",  # PA3..PA5: satellite muxes
    "9": "MUX_S0", "10": "MUX_S1", "11": "MUX_S2",  # PC1..PC3
    "24": "DET",  # PC4
    "7": "NRST", "60": "BOOT", "46": "SWDIO", "49": "SWCLK",  # NRST, BOOT0, PA13, PA14
    "58": "I2C_SCL", "59": "I2C_SDA",  # PB6/PB7: I2C1 (AF4 on the STM32, MUX4 on the AT32)
}
# firmware.py derives libhmk's select/input pin names from these by tracing the netlists.


def main() -> Circuit:
    p: list[Part] = []
    # USB-C, protection, regulators
    usb = {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
           "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
           "A5": "CC1", "B5": "CC2", "A6": "USB_CONN_DP", "B6": "USB_CONN_DP",
           "A7": "USB_CONN_DN", "B7": "USB_CONN_DN"}
    p += [
        Part("J1", "Connector:USB_C_Receptacle_USB2.0_16P", "TYPE-C-31-M-12",
             "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", usb, "power",
             fields={"MPN": "HRO TYPE-C-31-M-12"}),
        R("R1", "5.1k", "CC1", "GND", "power"),
        R("R2", "5.1k", "CC2", "GND", "power"),
        # 750 mA hold: 44 sensors at the older (LBC8) DRV5055's 6 mA typical already draw
        # ~0.36 A with the MCU, and a 500 mA part derates to ~0.4 A in a warm case.
        Part("F1", "Device:Polyfuse", "750mA", PTC_FP, {"1": "VBUS", "2": "+5V"}, "power",
             fields={"MPN": "SMD0805-075"}),
        Part("U4", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
             {"1": "USB_CONN_DN", "6": "USB_DN", "3": "USB_CONN_DP", "4": "USB_DP", "2": "GND",
              "5": "+5V"}, "power", fields={"MPN": "USBLC6-2SC6"}),
        Part("U2", "Regulator_Linear:TLV75733PDBV", "TLV75733PDBVR", "Package_TO_SOT_SMD:SOT-23-5",
             {"IN": "+5V", "EN": "+5V", "GND": "GND", "OUT": "+3.3VA"}, "power",
             fields={"MPN": "TLV75733PDBVR"}, description="Analog 3.3 V: sensors, muxes, module VDDA (ADC reference)"),
        Part("U3", "Regulator_Linear:TLV75733PDBV", "TLV75733PDBVR", "Package_TO_SOT_SMD:SOT-23-5",
             {"IN": "+5V", "EN": "+5V", "GND": "GND", "OUT": "+3V3"}, "power",
             fields={"MPN": "TLV75733PDBVR"},
             description="Digital 3.3 V: MCU module and trackpad (the AT32 with its USB HS PHY draws up to ~0.1 A)"),
        C("C1", "2.2u", "+5V", "GND", "power", fp=C0603),
        C("C2", "2.2u", "+5V", "GND", "power", fp=C0603),
        C("C3", "2.2u", "+3.3VA", "GND", "power", fp=C0603),
        C("C4", "10u", "+3.3VA", "GND", "power", fp=C0805),
        C("C5", "2.2u", "+3V3", "GND", "power", fp=C0603),
    ]
    # MCU module landing pads. Boot/reset buttons and SWD stay on the carrier (the
    # buttons through the case floor); everything MCU-specific lives on the module.
    p += [
        Part("J4", "Connector_Generic:Conn_02x12_Odd_Even", "MCU module", LANDING_FP, dict(MODULE_PINS), "mcu",
             description="Landing pads for the castellated MCU module (2x12, 1.27 mm), top side under "
                         "the trackpad; the module is soldered on"),
        C("C9", "10u", "+3V3", "GND", "mcu", fp=C0805),
        C("C10", "1u", "+3.3VA", "GND", "mcu", fp=C0603),
        Part("SW22", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
             {"1": "+3V3", "2": "BOOT"}, "mcu", fields={"MPN": "TS-1187A-B-A-B"}),
        Part("SW23", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A",
             {"1": "NRST", "2": "GND"}, "mcu", fields={"MPN": "TS-1187A-B-A-B"}),
        Part("J2", "Connector:Conn_ARM_SWD_TagConnect_TC2030-NL", "SWD",
             "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical",
             {"1": "+3V3", "2": "SWDIO", "3": "NRST", "4": "SWCLK", "5": "GND"}, "mcu"),
    ]
    # Optional trackpad (trackpad.MODEL) on the module's I2C1: an FFC to the pad,
    # which runs from the digital +3V3. Pads carry no I2C pull-ups of their own.
    n = max(int(k) for k in PAD.connector_pins if k.isdigit())  # unused pins get no-connect flags
    p += [
        Part("J5", f"Connector_Generic_MountingPin:Conn_01x{n:02d}_MountingPin", "Trackpad", PAD.connector_fp,
             dict(PAD.connector_pins), "trackpad", fields={"MPN": PAD.connector_mpn},
             description=PAD.connector_note),
        R("R19", "4.7k", "I2C_SCL", "+3V3", "trackpad"),
        R("R20", "4.7k", "I2C_SDA", "+3V3", "trackpad"),
        C("C16", "1u", "+3V3", "GND", "trackpad", fp=C0603),
    ]
    if "TP_NRST" in PAD.connector_pins.values():  # internal pull-up; Azoteq recommends 100 nF
        p.append(C("C17", "100n", "TP_NRST", "GND", "trackpad"))
    # Link to the satellite (via the VGA daughterboard)
    pull_up = SENSOR.invert_adc  # pull toward "released" when the cable is absent
    p += [
        link_connector(),
        Part("U8", "Power_Management:TPS2051CDBV", "TPS2051CDBVR", "Package_TO_SOT_SMD:SOT-23-5",
             {"IN": "+5V", "EN": "+5V", "GND": "GND", "OUT": "LINK_5V_F"}, "link",
             fields={"MPN": "TPS2051CDBVR"},
             description="Satellite supply switch: 0.55 ms soft start and a 0.65-1.05 A limit, so plugging "
                         "in the VGA cable can't drag +5V down (and brown out the MCU)"),
        C("C18", "100n", "+5V", "GND", "link"),
        Part("D1", "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123",
             {"A": "LINK_5V_F", "K": "+5V_LINK"}, "link", fields={"MPN": "B5819W"},
             description="Blocks back-feed if the port meets a PC's VGA +5 V"),
        R("R5", "470", "MUX_S0", "LINK_S0", "link"),
        R("R6", "470", "MUX_S1", "LINK_S1", "link"),
        R("R7", "470", "MUX_S2", "LINK_S2", "link"),
        R("R8", "100", "LINK_A", "ADC_R_A", "link"),
        R("R9", "100", "LINK_B", "ADC_R_B", "link"),
        R("R10", "100", "LINK_C", "ADC_R_C", "link"),
        R("R11", "100k", "ADC_R_A", "+3.3VA", "link", dnp=not pull_up),
        R("R12", "100k", "ADC_R_B", "+3.3VA", "link", dnp=not pull_up),
        R("R13", "100k", "ADC_R_C", "+3.3VA", "link", dnp=not pull_up),
        R("R14", "100k", "ADC_R_A", "GND", "link", dnp=pull_up),
        R("R15", "100k", "ADC_R_B", "GND", "link", dnp=pull_up),
        R("R16", "100k", "ADC_R_C", "GND", "link", dnp=pull_up),
        R("R17", "10k", "LINK_DET", "+3V3", "link"),
        R("R18", "1k", "LINK_DET", "DET", "link"),
        C("C15", "1u", "+5V_LINK", "GND", "link", fp=C0603),
        *link_esd(),
    ]
    p += sensor_array(("MUX_S0", "MUX_S1", "MUX_S2"),
                      {"A": "ADC_L_A", "B": "ADC_L_B", "C": "ADC_L_C"}, MAIN_SIDE)
    p += standoffs(MAIN_SIDE)
    blocks = [
        ("power", "USB-C, protection, regulators", (20.32, 38.1), 260),
        ("mcu", "MCU module landing pads, boot/reset, SWD", (292.1, 38.1), 290),
        ("link", "Link to the satellite half (VGA daughterboard)", (596.9, 38.1), 225),
        ("trackpad", "Trackpad (optional)", (292.1, 130.0), 290),
        ("mux", "Analog muxes (select lines shared with the right half)", (20.32, 205.74), 560),
        ("mech", "Mechanical", (596.9, 205.74), 225),
        ("keys", "Hall-effect sensors (on B.Cu, centred under each switch)", (20.32, 292.1), 800),
    ]
    notes = [
        ("Cable unplugged: R11-R13 (pull-up) or R14-R16 (pull-down) hold the remote ADC inputs at the\n"
         "'released' end of the range; populate the set matching libhmk invert_adc.", (596.9, 250.0)),
    ]
    return Circuit("vgacorne-main", f"VGACorne - main ({MAIN_SIDE}) half", REV, p, blocks, notes)


# ---------------------------------------------------------------------------
# Satellite half
# ---------------------------------------------------------------------------

def satellite() -> Circuit:
    p: list[Part] = [
        link_connector(),
        R("R17", "1k", "LINK_DET", "GND", "link", description="Tells the main half the cable is present"),
        *link_esd(),
        Part("U2", "Regulator_Linear:TLV75733PDBV", "TLV75733PDBVR", "Package_TO_SOT_SMD:SOT-23-5",
             {"IN": "+5V_LINK", "EN": "+5V_LINK", "GND": "GND", "OUT": "+3.3VA"}, "power",
             fields={"MPN": "TLV75733PDBVR"}),
        C("C1", "10u", "+5V_LINK", "GND", "power", fp=C0805),
        C("C2", "2.2u", "+3.3VA", "GND", "power", fp=C0603),
        C("C3", "10u", "+3.3VA", "GND", "power", fp=C0805),
        Part("U5", "Amplifier_Operational:TLV9064", "TLV9064IPWR", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
             {"3": "MUX_A", "2": "OPA_A", "1": "OPA_A",
              "5": "MUX_B", "6": "OPA_B", "7": "OPA_B",
              "10": "MUX_C", "9": "OPA_C", "8": "OPA_C",
              "12": "GND", "13": "OPA_D", "14": "OPA_D",
              "4": "+3.3VA", "11": "GND"}, "buffer", fields={"MPN": "TLV9064IPWR"},
             description="Unity-gain buffers driving the VGA coax (10 MHz RRIO)"),
        C("C4", "100n", "+3.3VA", "GND", "buffer"),
        R("R1", "75", "OPA_A", "LINK_A", "buffer", description="75 ohm back-termination"),
        R("R2", "75", "OPA_B", "LINK_B", "buffer"),
        R("R3", "75", "OPA_C", "LINK_C", "buffer"),
    ]
    p += sensor_array(("LINK_S0", "LINK_S1", "LINK_S2"), {"A": "MUX_A", "B": "MUX_B", "C": "MUX_C"},
                      SATELLITE_SIDE)
    p += standoffs(SATELLITE_SIDE)
    # Rotary encoder (mouse column): read through mux C's last channel, see ENCODER_SUM.
    p += [
        Part("ENC1", "Device:RotaryEncoder", "PEC12R-4220F-N0024",
             "Rotary_Encoder:RotaryEncoder_Bourns_Vertical_PEC12R-3x17F-Nxxxx",
             {"A": "ENC_A", "B": "ENC_B", "C": "GND"}, "encoder", fields={"MPN": "PEC12R-4220F-N0024"},
             description="Rotary encoder with a knob: 24 detents, 20 mm shaft, no bushing, no switch "
                         "(same PCB layout as the -3 bushing version)"),
        R("R21", f"{ENCODER_PULL_UP / 1e3:g}k", "ENC_A", "+3.3VA", "encoder"),
        R("R22", f"{ENCODER_PULL_UP / 1e3:g}k", "ENC_B", "+3.3VA", "encoder"),
        R("R23", f"{ENCODER_SUM['A'] / 1e3:g}k", "ENC_A", "ENC", "encoder", fields={"Tolerance": "1%"}),
        R("R24", f"{ENCODER_SUM['B'] / 1e3:g}k", "ENC_B", "ENC", "encoder", fields={"Tolerance": "1%"}),
        C("C5", "1n", "ENC", "GND", "encoder"),
    ]
    blocks = [
        ("link", "Link to main half (VGA daughterboard)", (20.32, 38.1), 250),
        ("power", "Local analog regulator (from VGA pin 9 +5 V)", (292.1, 38.1), 250),
        ("buffer", "Coax drivers", (563.88, 38.1), 260),
        ("mux", "Analog muxes (selects driven by the main MCU over the cable)", (20.32, 205.74), 560),
        ("mech", "Mechanical", (596.9, 205.74), 225),
        ("keys", "Hall-effect sensors (on B.Cu, centred under each switch)", (20.32, 292.1), 800),
        ("encoder", "Rotary encoder: A/B summed into one level on mux C channel 7", (292.1, 130.0), 250),
    ]
    return Circuit("vgacorne-satellite", f"VGACorne - satellite ({SATELLITE_SIDE}) half", REV, p, blocks)


# ---------------------------------------------------------------------------
# VGA daughterboard
# ---------------------------------------------------------------------------

def link() -> Circuit:
    """Vertical daughterboard: DE-15 on the front, pigtail pads on the back.

    It stands against the case's back wall and is held there by the DE-15's
    4-40 screwlocks, so cable forces go straight into the aluminium.
    """
    p: list[Part] = [
        Part("J1", "Connector:DE15_Socket_HighDensity_MountingHoles", "DE-15F (VGA)",
             "Connector_Dsub:DSUB-15-HD_Socket_Vertical_P2.29x1.98mm_MountingHoles",
             dict(VGA_PINS), "conn",
             description="HD-15 female, vertical PCB mount, 4-40 threaded inserts"),
        Part("J2", "Connector_Generic:Conn_01x10", "JST-SH pigtail", "vgacorne:WirePads_1x10_P1.6mm",
             dict(LINK_PINS), "conn",
             description="Solder a 10-pin JST-SH pigtail here; its plug goes to J3 on the half's PCB"),
        Part("JP1", "Jumper:SolderJumper_3_Bridged12", "5V pin", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm",
             {"1": "VGA_P9", "2": "+5V_LINK", "3": "VGA_P15"}, "jumpers",
             description="+5 V on VGA pin 9 (default) or pin 15 (for 3+4 cables without pin 9)"),
        Part("JP2", "Jumper:SolderJumper_3_Bridged12", "DET pin", "Jumper:SolderJumper-3_P1.3mm_Bridged12_RoundedPad1.0x1.5mm",
             {"1": "VGA_P15", "2": "LINK_DET", "3": "VGA_P9"}, "jumpers",
             description="Cable-detect on VGA pin 15 (default) or pin 9; always set opposite to JP1"),
        C("C1", "100n", "+5V_LINK", "GND", "jumpers"),
    ]
    blocks = [
        ("conn", "Connectors", (20.32, 38.1), 250),
        ("jumpers", "Cable variant jumpers (set both boards the same way)", (20.32, 150.0), 250),
    ]
    notes = [
        ("VGA pinout: 1/2/3 (R/G/B coax) = LINK_A/B/C, 6/7/8 = their returns (GND), 13 HSYNC = S0,\n"
         "14 VSYNC = S1, 12 SDA = S2, 9 = +5V, 15 SCL = cable detect, 5/10 = GND, 4/11 unused.\n"
         "ESD protection for these lines sits next to J3 on the main and satellite PCBs.", (20.32, 230.0)),
    ]
    return Circuit("vgacorne-link", "VGACorne - VGA link daughterboard", REV, p, blocks, notes, paper="A3")


# ---------------------------------------------------------------------------
# MCU modules
# ---------------------------------------------------------------------------

def _module(name: str, title: str, mcu: Part, parts: list[Part], notes: list[str]) -> Circuit:
    p = [
        Part("J1", "Connector_Generic:Conn_02x12_Odd_Even", "to main PCB J4", CASTELLATED_FP,
             module_header_pins(), "conn",
             description="2x12 castellated edge pads, 1.27 mm; soldered onto J4 on the main PCB (not a part)",
             in_bom=False),
        mcu, *parts,
    ]
    blocks = [("conn", "Module edge pads (castellated; pad n is soldered to J4 pad n)", (20.32, 38.1), 120),
              ("mcu", mcu.value, (150.0, 38.1), 250)]
    return Circuit(name, title, REV, p, blocks, [("\n".join(notes), (20.32, 250.0))], paper="A3")


def module_at32() -> Circuit:
    """AT32F405RCT7: libhmk with USB high-speed (8 kHz)."""
    pins = {**MCU_SIGNAL_PINS,
            "1": "+3V3", "36": "+3V3", "64": "+3V3", "13": "+3.3VA",
            "31": "GND", "63": "GND", "12": "GND",
            "5": "HSE_IN", "6": "HSE_OUT", "33": "OTGHS_R", "34": "USB_DN", "35": "USB_DP"}
    mcu = Part("U1", "vgacorne:AT32F405RCT7", "AT32F405RCT7", "Package_QFP:LQFP-64_10x10mm_P0.5mm",
               pins, "mcu", fields={"MPN": "AT32F405RCT7"})
    parts = [
        C("C1", "100n", "+3V3", "GND", "mcu"), C("C2", "100n", "+3V3", "GND", "mcu"),
        C("C3", "100n", "+3V3", "GND", "mcu"), C("C4", "4.7u", "+3V3", "GND", "mcu", fp=C0603),
        C("C5", "100n", "+3.3VA", "GND", "mcu"), C("C6", "1u", "+3.3VA", "GND", "mcu", fp=C0603),
        Part("Y1", "Device:Crystal_GND24", "12MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
             {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"}, "mcu",
             fields={"MPN": "X322512MSB4SI"}, description="12 MHz, CL 20 pF (libhmk's AT32 port requires 12 MHz)"),
        C("C7", "30p", "HSE_IN", "GND", "mcu"), C("C8", "30p", "HSE_OUT", "GND", "mcu"),
        R("R1", "12k", "OTGHS_R", "GND", "mcu", description="USB HS PHY reference resistor",
          fields={"Tolerance": "1%"}),
        R("R2", "10k", "BOOT", "GND", "mcu", description="BOOT0 pull-down"),
        C("C9", "100n", "NRST", "GND", "mcu"),
    ]
    return _module("vgacorne-module-at32", "VGACorne MCU module - AT32F405RCT7 (libhmk, USB HS)", mcu, parts,
                   ["libhmk driver at32f405xx, USB high-speed on OTGHS1 (8 kHz polling).",
                    "Not supported by QMK (only the AT32F415 is)."])


def module_f446() -> Circuit:
    """STM32F446RET6: QMK, or libhmk at USB full speed."""
    pins = {**MCU_SIGNAL_PINS,
            "1": "+3V3", "19": "+3V3", "32": "+3V3", "48": "+3V3", "64": "+3V3", "13": "+3.3VA",
            "18": "GND", "31": "GND", "47": "GND", "63": "GND", "12": "GND",
            "30": "VCAP", "5": "HSE_IN", "6": "HSE_OUT", "44": "USB_DN", "45": "USB_DP",
            "28": "BOOT1", "43": "USART1_RX"}
    mcu = Part("U1", "MCU_ST_STM32F4:STM32F446RETx", "STM32F446RET6", "Package_QFP:LQFP-64_10x10mm_P0.5mm",
               pins, "mcu", fields={"MPN": "STM32F446RET6"})
    parts = [
        C("C1", "100n", "+3V3", "GND", "mcu"), C("C2", "100n", "+3V3", "GND", "mcu"),
        C("C3", "100n", "+3V3", "GND", "mcu"), C("C4", "100n", "+3V3", "GND", "mcu"),
        C("C5", "4.7u", "+3V3", "GND", "mcu", fp=C0603),
        C("C6", "100n", "+3.3VA", "GND", "mcu"), C("C7", "1u", "+3.3VA", "GND", "mcu", fp=C0603),
        C("C8", "4.7u", "VCAP", "GND", "mcu", fp=C0603,
          description="VCAP_1: low-ESR ceramic, value per ST datasheet for single-VCAP packages"),
        Part("Y1", "Device:Crystal_GND24", "8MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
             {"1": "HSE_IN", "3": "HSE_OUT", "2": "GND", "4": "GND"}, "mcu",
             fields={"MPN": "X32258MSB4SI"},
             description="8 MHz, CL 20 pF: matches QMK's generic STM32F446 clock tree; libhmk takes any whole MHz"),
        C("C9", "30p", "HSE_IN", "GND", "mcu"), C("C10", "30p", "HSE_OUT", "GND", "mcu"),
        R("R1", "10k", "BOOT", "GND", "mcu", description="BOOT0 pull-down"),
        R("R2", "10k", "BOOT1", "GND", "mcu",
          description="PB2/BOOT1 pull-down: BOOT0 = 1 only reaches the DFU bootloader with BOOT1 = 0 (RM0390)"),
        R("R3", "10k", "USART1_RX", "+3V3", "mcu",
          description="Holds the bootloader's unused USART1 RX (PA10) idle so noise can't select it (AN2606)"),
        C("C11", "100n", "NRST", "GND", "mcu"),
    ]
    return _module("vgacorne-module-f446", "VGACorne MCU module - STM32F446RET6 (QMK / libhmk, USB FS)", mcu, parts,
                   ["USB full-speed on PA11/PA12 (1 kHz polling).",
                    "QMK: GENERIC_STM32_F446XE board, 8 MHz HSE. libhmk: driver stm32f446xx, hse_value 8000000."])


BOARDS = {"main": main, "satellite": satellite, "link": link,
          "module_at32": module_at32, "module_f446": module_f446}
