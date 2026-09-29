"""The optional trackpad on the main half: which pad, where it sits, how it connects.

MODEL picks one of PADS. Everything that depends on it reads from here: the case
pocket (mechanical.py), the FFC connector and support parts on the main PCB
(circuits.py, pcb.py), the QMK driver settings (qmk.py) and the render.

Positions are in the left-half Corne frame, like geometry.py, and are mirrored
onto the main half.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import Point, Polygon, box

from . import geometry as geo


@dataclass(frozen=True)
class Pad:
    """A trackpad as mounted: a flush top (the module itself, or a larger overlay
    with the module bonded underneath) in a counterbore, over a well for the rest."""
    name: str
    mpn: str
    shape: str                      # module outline: "circle" or "rect"
    size: tuple[float, float]       # (d, d) or (width, height) as mounted, mm
    corner_r: float
    centre: tuple[float, float]     # left-half Corne frame
    board_t: float                  # what sits in the counterbore, flush with the case top
    parts: float                    # depth the well must clear below the counterbore
    well_grow: float                # well outline vs the module: < 0 leaves a ledge for its rim
    fpc: tuple[float, float]        # FFC connector on top of the main PCB (tab or pad tongue)
    fpc_mouth: tuple[float, float]  # which way the connector opens
    channel: tuple[float, float, float, float] | None  # extra well area for the FFC, x0 y0 x1 y1
    connector_fp: str
    connector_mpn: str
    connector_pins: dict[str, str]  # connector pin -> net ("MP" = mounting pads)
    connector_note: str
    qmk_driver: str
    qmk_defines: list[str] = field(default_factory=list)
    overlay_margin: float = 0.0     # overlay beyond the module on every side (0: the module is the top)
    gap: float = 0.2                # pocket clearance round the top
    gloss: bool = False             # render: etched glass overlay rather than textured plastic

    def top(self, side: str = geo.MAIN_SIDE, grow: float = 0.0) -> Polygon:
        """What's flush with the case top."""
        return self.outline(side, self.overlay_margin + grow)

    def outline(self, side: str = geo.MAIN_SIDE, grow: float = 0.0) -> Polygon:
        """The module."""
        cx, cy = geo.corne(*self.centre)
        w, h = self.size
        if self.shape == "circle":
            p = Point(cx, cy).buffer(w / 2 + grow, 64)
        else:
            r = self.corner_r
            p = box(cx - w / 2 + r, cy - h / 2 + r, cx + w / 2 - r, cy + h / 2 - r).buffer(r + grow, 16)
        return geo.mirror(p) if side == "right" else p

    def well(self, side: str = geo.MAIN_SIDE) -> Polygon:
        w = self.outline(side, self.well_grow)
        if self.channel:
            c = box(*(geo.corne(*self.channel[:2]) + geo.corne(*self.channel[2:])))
            w = w.union(geo.mirror(c) if side == "right" else c)
        return w


PADS = {
    # Cirque Pinnacle Gen2, 40 mm round, flat overlay (TM040040 spec 1.2): 0.99 mm
    # board + overlay, 4.1 mm of parts kept 2 mm in from the rim, 12-pin 0.5 mm FFC.
    # Beside Y/H/N like the TPS65. Cirque asks for no metal bezel: a plastic ring
    # (overlay_margin) is worth trying.
    "cirque40": Pad(
        name="Cirque TM040040 (Gen2, flat overlay)", mpn="TM040040-2023-302",
        shape="circle", size=(40.0, 40.0), corner_r=20.0, centre=(0.8, 9.5),
        board_t=1.0, parts=4.1, well_grow=-2.0,  # rim on a 2 mm ledge; parts keep 2 mm in
        fpc=(-12.0, 8.0), fpc_mouth=(1, 0), channel=None,
        connector_fp="Connector_FFC-FPC:Hirose_FH12-12S-0.5SH_1x12-1MP_P0.50mm_Horizontal",
        connector_mpn="FH12-12S-0.5SH(55)",
        connector_pins={"9": "I2C_SCL", "10": "I2C_SDA", "11": "GND", "12": "+3V3", "MP": "GND"},
        connector_note="12-pin 0.5 mm FFC to a Cirque TM0xx0xx Gen2 pad: 9 SCL, 10 SDA, 11 GND, 12 VDD "
                       "(pad-side numbering; check pin 1 against your FFC type)",
        qmk_driver="cirque_pinnacle_i2c",
        qmk_defines=["CIRQUE_PINNACLE_DIAMETER_MM 40", "CIRQUE_PINNACLE_TAP_ENABLE",
                     "POINTING_DEVICE_GESTURES_SCROLL_ENABLE // circular scroll round the rim"],
    ),
    # Azoteq TPS65 (IQS550), 65 x 49 mm, landscape, right beside Y/H/N (3 mm of
    # aluminium between them) over the tab, spanning the three rows: the index
    # finger slides straight onto it. geometry.BAY_BACKSET makes room behind it;
    # the tilted thumb key sets how low it can go. Azoteq EOL'd it in 2024
    # (Keycapsss still sells them; GR-Trackpad65 is an open clone). The -201A
    # variant has no overlay, so it is bonded under a 1 mm non-metal overlay 3 mm
    # bigger all round: that overlay is what sits flush, and it keeps the aluminium
    # ~4 mm from the electrodes (Azoteq: ground within 5 mm costs edge sensitivity).
    # Module 2.03 mm with adhesive; its 2 mm ZIF (J1) and the FFC's fold under it
    # need ~4.7 mm below the overlay. J1 sits 9.2 mm in from a long edge, 25.3 mm
    # from an end: turn the module so that is the back edge and the end nearer the
    # keys, which puts J1 right over J5 on the PCB tongue under the pad.
    "tps65": Pad(
        name="Azoteq TPS65 under a 1 mm overlay", mpn="TPS65-201A-S",
        shape="rect", size=(65.0, 49.0), corner_r=3.8, centre=(16.14, 6.2),
        board_t=1.0, parts=4.7, well_grow=0.3, overlay_margin=3.0, gloss=True,
        fpc=(8.9, -12.8), fpc_mouth=(0, 1), channel=None,
        connector_fp="Connector_FFC-FPC:Jushuo_AFC07-S06FCA-00_1x6-1MP_P0.50_Horizontal",
        connector_mpn="AFC07-S06FCA-00 (LCSC C262553)",
        connector_pins={"2": "TP_NRST", "3": "GND", "4": "+3V3", "5": "I2C_SCL", "6": "I2C_SDA", "MP": "GND"},
        connector_note="6-pin 0.5 mm FFC to the TPS65's J1: 1 RDY (unused), 2 NRST, 3 GND, 4 VDDHI, 5 SCL, 6 SDA. "
                       "Same-side (type A) cable folded back under the module; check the pin order on a paper mock-up",
        qmk_driver="azoteq_iqs5xx",
        qmk_defines=["AZOTEQ_IQS5XX_TPS65 // landscape; if both axes come out reversed add AZOTEQ_IQS5XX_ROTATION_180"],
    ),
}

MODEL = PADS["tps65"]
