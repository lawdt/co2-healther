"""CO2 monitor enclosure: base and lid for HW-364A + SCD41 + buzzer + button + 2 LEDs.

Coordinates in mm. Origin is the inner bottom-left corner of the base:
X along the board length (USB on the +X wall), Y along the board width,
Z up (lid on top, display looks up through the lid).

All wiring is soldered (no Dupont connectors), so the box is only as tall
as the board stack. The left part of the box ("bay") holds the sensor,
buzzer, button and LEDs behind a partition, so the board heat does not
skew the SCD41 temperature.
"""

import adsk.core
import adsk.fusion

# --- Walls ---
WALL = 2.0
FLOOR = 2.0
LID = 2.0
FIT = 0.2  # clearance between lid lip and walls

# --- HW-364A board ---
BOARD_L = 59.0
BOARD_W = 30.8
PCB_T = 1.3
UNDER = 5.0         # room under the PCB for solder joints and wires
TOP_CLEAR = 4.5     # PCB top to lid underside (antenna is 3 mm)
BOARD_GAP = 0.5     # gap between board edge and walls
HOLE_INSET = 2.5    # mounting hole center from board edges
STANDOFF_D = 6.0
STANDOFF_PILOT = 2.6  # for M3 self-tapping screws
STANDOFF_PILOT_DEPTH = 6.0

# OLED visible area, relative to the board (USB edge on the right)
OLED_FROM_RIGHT = 7.0
OLED_FROM_BOTTOM = 12.0
OLED_W = 23.0
OLED_H = 13.0
WINDOW_MARGIN = 0.5
BEZEL_MARGIN = 1.5
BEZEL_DEPTH = 1.0

# USB-C opening in the +X wall, centered on USB_Y from the board bottom edge
USB_Y = 11.0
USB_W = 12.5
USB_H = 8.0

# --- Bay with sensor, buzzer, button, LEDs ---
BAY_L = 36.0
PARTITION = 2.0
WIRE_SLOT_W = 10.0
WIRE_SLOT_Z = (0.5, 4.5)

# SCD41 module lies flat in the back of the bay, air inlet facing up
SENSOR_L = 21.8
SENSOR_W = 13.8
SENSOR_POS = (3.0, 19.5)   # PCB corner
SENSOR_RAISE = 2.0          # posts under the PCB for solder joints
SENSOR_FIT = 0.3
SENSOR_RIM = 3.0            # height of the retaining corners above the PCB bottom

VENT_W = 1.6
VENT_STEP = 3.6
BACK_VENT_Z = (2.5, 8.5)

BUTTON_POS = (9.5, 9.5)
BUTTON_HOLE = 12.0     # cap is 11.5
BUTTON_BODY = 12.4     # 12x12 body + clearance
BUTTON_FRAME = 1.3
BUTTON_FRAME_DEPTH = 4.0

BUZZER_POS = (27.0, 9.5)
BUZZER_D = 12.4        # 12 mm body + clearance
BUZZER_RING = 1.3
BUZZER_RING_DEPTH = 4.0
BUZZER_GRILLE_D = 1.6
BUZZER_GRILLE_R = 3.0

LED_RED_POS = (31.0, 23.0)
LED_YELLOW_POS = (31.0, 30.0)
LED_HOLE = 5.2

LIP_H = 3.0
LIP_T = 1.2

# --- Derived ---
INNER_W = BOARD_W + 2 * 1.6
BOARD_X = BAY_L + PARTITION + BOARD_GAP
INNER_L = BOARD_X + BOARD_L + BOARD_GAP
BOARD_Y = (INNER_W - BOARD_W) / 2
PCB_Z = UNDER
INNER_H = UNDER + PCB_T + TOP_CLEAR

MM = 0.1  # Fusion API works in cm


def pt(x, y, z):
    return adsk.core.Point3D.create(x * MM, y * MM, z * MM)


class Builder:
    def __init__(self):
        self.tbm = adsk.fusion.TemporaryBRepManager.get()

    def box(self, x0, y0, z0, x1, y1, z1):
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        z0, z1 = sorted((z0, z1))
        obb = adsk.core.OrientedBoundingBox3D.create(
            pt((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
            adsk.core.Vector3D.create(1, 0, 0),
            adsk.core.Vector3D.create(0, 1, 0),
            (x1 - x0) * MM, (y1 - y0) * MM, (z1 - z0) * MM)
        return self.tbm.createBox(obb)

    def cyl(self, x, y, z0, z1, d):
        return self.tbm.createCylinderOrCone(pt(x, y, z0), d / 2 * MM, pt(x, y, z1), d / 2 * MM)

    def join(self, target, tool):
        self.tbm.booleanOperation(target, tool, adsk.fusion.BooleanTypes.UnionBooleanType)

    def cut(self, target, tool):
        self.tbm.booleanOperation(target, tool, adsk.fusion.BooleanTypes.DifferenceBooleanType)


def board_holes():
    for hx in (HOLE_INSET, BOARD_L - HOLE_INSET):
        for hy in (HOLE_INSET, BOARD_W - HOLE_INSET):
            yield BOARD_X + hx, BOARD_Y + hy


def sensor_box():
    x0, y0 = SENSOR_POS
    return x0, y0, x0 + SENSOR_L, y0 + SENSOR_W


def build_base(b):
    base = b.box(-WALL, -WALL, -FLOOR, INNER_L + WALL, INNER_W + WALL, INNER_H)
    b.cut(base, b.box(0, 0, 0, INNER_L, INNER_W, INNER_H + 1))

    # Partition between the bay and the board; ends are left open for the lid lip
    lip_clear = FIT + LIP_T + 0.2
    part = b.box(BAY_L, lip_clear, 0, BAY_L + PARTITION, INNER_W - lip_clear, INNER_H)
    mid = INNER_W / 2
    b.cut(part, b.box(BAY_L - 0.1, mid - WIRE_SLOT_W / 2, WIRE_SLOT_Z[0],
                      BAY_L + PARTITION + 0.1, mid + WIRE_SLOT_W / 2, WIRE_SLOT_Z[1]))
    b.join(base, part)

    # Board standoffs with pilot holes going into the floor
    for x, y in board_holes():
        b.join(base, b.cyl(x, y, 0, PCB_Z, STANDOFF_D))
        b.cut(base, b.cyl(x, y, PCB_Z - STANDOFF_PILOT_DEPTH, PCB_Z + 0.1, STANDOFF_PILOT))

    # USB-C opening; the connector sticks ~2 mm past the board edge into the wall
    usb_y = BOARD_Y + USB_Y
    usb_z = PCB_Z + PCB_T / 2
    b.cut(base, b.box(INNER_L - 0.1, usb_y - USB_W / 2, max(usb_z - USB_H / 2, 0.5),
                      INNER_L + WALL + 0.1, usb_y + USB_W / 2, usb_z + USB_H / 2))

    # Sensor: four corner posts it rests on, with L-shaped retaining corners
    sx0, sy0, sx1, sy1 = sensor_box()
    f = SENSOR_FIT
    for cx, cy, dx, dy in ((sx0, sy0, 1, 1), (sx1, sy0, -1, 1), (sx0, sy1, 1, -1), (sx1, sy1, -1, -1)):
        b.join(base, b.box(cx, cy, 0, cx + dx * 3, cy + dy * 3, SENSOR_RAISE))
        corner = b.box(cx - dx * (f + 1.2), cy - dy * (f + 1.2), 0,
                       cx + dx * 4, cy + dy * 4, SENSOR_RAISE + SENSOR_RIM)
        b.cut(corner, b.box(cx - dx * f, cy - dy * f, 0, cx + dx * 4.1, cy + dy * 4.1, SENSOR_RAISE + SENSOR_RIM + 0.1))
        b.join(base, corner)

    # Vents in the back wall next to the sensor
    n = int((SENSOR_L - VENT_W) // VENT_STEP) + 1
    start = sx0 + (SENSOR_L - (n - 1) * VENT_STEP) / 2
    for i in range(n):
        x = start + i * VENT_STEP
        b.cut(base, b.box(x - VENT_W / 2, INNER_W - 0.1, BACK_VENT_Z[0],
                          x + VENT_W / 2, INNER_W + WALL + 0.1, BACK_VENT_Z[1]))

    return base


def build_lid(b):
    top = INNER_H + LID
    lid = b.box(-WALL, -WALL, INNER_H, INNER_L + WALL, INNER_W + WALL, top)

    # Locating lip on three sides; the USB side stays open
    lz = INNER_H - LIP_H
    o, i = FIT, FIT + LIP_T
    b.join(lid, b.box(o, o, lz, i, INNER_W - o, INNER_H))
    b.join(lid, b.box(o, o, lz, INNER_L - o, i, INNER_H))
    b.join(lid, b.box(o, INNER_W - i, lz, INNER_L - o, INNER_W - o, INNER_H))

    # Display window with a shallow bezel
    wx0 = BOARD_X + BOARD_L - OLED_FROM_RIGHT - OLED_W
    wy0 = BOARD_Y + OLED_FROM_BOTTOM
    wx1, wy1 = wx0 + OLED_W, wy0 + OLED_H
    m = WINDOW_MARGIN
    b.cut(lid, b.box(wx0 - m, wy0 - m, INNER_H - 0.1, wx1 + m, wy1 + m, top + 0.1))
    m = BEZEL_MARGIN
    b.cut(lid, b.box(wx0 - m, wy0 - m, top - BEZEL_DEPTH, wx1 + m, wy1 + m, top + 0.1))

    # Vent slots above the sensor
    sx0, sy0, sx1, sy1 = sensor_box()
    n = int((SENSOR_L - 4 - VENT_W) // VENT_STEP) + 1
    start = sx0 + (SENSOR_L - (n - 1) * VENT_STEP) / 2
    for k in range(n):
        x = start + k * VENT_STEP
        b.cut(lid, b.box(x - VENT_W / 2, sy0 + 2.5, INNER_H - 0.1, x + VENT_W / 2, sy1 - 2.5, top + 0.1))

    # Button: round hole for the cap and a square frame holding the body
    bx, by = BUTTON_POS
    b.cut(lid, b.cyl(bx, by, INNER_H - 0.1, top + 0.1, BUTTON_HOLE))
    h = BUTTON_BODY / 2
    f = h + BUTTON_FRAME
    frame = b.box(bx - f, by - f, INNER_H - BUTTON_FRAME_DEPTH, bx + f, by + f, INNER_H)
    b.cut(frame, b.box(bx - h, by - h, INNER_H - BUTTON_FRAME_DEPTH - 0.1, bx + h, by + h, INNER_H + 0.1))
    b.join(lid, frame)

    # Buzzer: ring to glue it in and a small grille above it
    zx, zy = BUZZER_POS
    ring = b.cyl(zx, zy, INNER_H - BUZZER_RING_DEPTH, INNER_H, BUZZER_D + 2 * BUZZER_RING)
    b.cut(ring, b.cyl(zx, zy, INNER_H - BUZZER_RING_DEPTH - 0.1, INNER_H + 0.1, BUZZER_D))
    b.join(lid, ring)
    grille = [(0, 0), (BUZZER_GRILLE_R, 0), (-BUZZER_GRILLE_R, 0), (0, BUZZER_GRILLE_R), (0, -BUZZER_GRILLE_R)]
    for dx, dy in grille:
        b.cut(lid, b.cyl(zx + dx, zy + dy, INNER_H - 0.1, top + 0.1, BUZZER_GRILLE_D))

    # LEDs
    for x, y in (LED_RED_POS, LED_YELLOW_POS):
        b.cut(lid, b.cyl(x, y, INNER_H - 0.1, top + 0.1, LED_HOLE))

    return lid


def run(_context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    root = design.rootComponent

    b = Builder()
    bodies = (("Base", build_base(b)), ("Lid", build_lid(b)))

    if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
        feature = root.features.baseFeatures.add()
        feature.startEdit()
        for name, body in bodies:
            root.bRepBodies.add(body, feature).name = name
        feature.finishEdit()
    else:
        for name, body in bodies:
            root.bRepBodies.add(body).name = name

    app.activeViewport.fit()
    print('Inner {:.1f} x {:.1f} x {:.1f} mm, outer {:.1f} x {:.1f} x {:.1f} mm'.format(
        INNER_L, INNER_W, INNER_H,
        INNER_L + 2 * WALL, INNER_W + 2 * WALL, INNER_H + FLOOR + LID))
