"""CO2 monitor enclosure for HW-364A + SCD41 + buzzer + button + 2 LEDs.

Builds a parametric model in a new Fusion document: every size is a user
parameter (Modify > Change Parameters), every feature is a sketch with
dimensions driven by those parameters plus an extrude in the timeline.

Model origin is the outer bottom-left corner of the base: X along the
board length (USB-C on the +X wall), Y along the board width (up when the
device hangs on the wall), Z out of the wall (lid with the display on top).
Expressions below are written in inner coordinates and shifted by the wall
and floor thickness.

All wiring is soldered, so the box is only as tall as the board stack.
The left part ("bay") holds the sensor, buzzer, button and LEDs behind a
partition, so the board heat does not skew the SCD41 temperature.
Two hooks on the back fit IKEA SKADIS pegboard slots.
"""

import adsk.core
import adsk.fusion

PARAMS = [
    # Walls
    ('WALL', '2 mm', 'Side wall thickness'),
    ('FLOOR', '2 mm', 'Base floor thickness'),
    ('LID', '2 mm', 'Lid plate thickness'),
    ('FIT', '0.2 mm', 'Clearance between lid lip and walls'),
    ('CORNER_R', '3 mm', 'Outer vertical corner radius'),
    ('LIP_H', '3 mm', 'Lid lip height'),
    ('LIP_T', '1.2 mm', 'Lid lip thickness'),
    ('LIP_NOTCH_CLEAR', '0.3 mm', 'Clearance under the lip in the partition notches'),
    # HW-364A board
    ('BOARD_L', '59 mm', 'Board length'),
    ('BOARD_W', '30.8 mm', 'Board width'),
    ('PCB_T', '1.3 mm', 'Board thickness'),
    ('UNDER', '5 mm', 'Room under the board for solder joints'),
    ('TOP_CLEAR', '4.5 mm', 'Board top to lid underside'),
    ('BOARD_GAP', '0.5 mm', 'Gap at board short edges'),
    ('BOARD_SIDE_GAP', '1.6 mm', 'Gap at board long edges'),
    ('HOLE_INSET', '2.5 mm', 'Mounting hole center from board edges'),
    ('STANDOFF_D', '6 mm', 'Standoff diameter'),
    ('STANDOFF_PILOT', '2.6 mm', 'Pilot hole for M3 self-tapping screw'),
    ('STANDOFF_PILOT_DEPTH', '6 mm', 'Pilot hole depth'),
    # OLED visible area relative to the board, USB edge on the right
    ('OLED_FROM_RIGHT', '7 mm', 'Visible area to the USB-side board edge'),
    ('OLED_FROM_BOTTOM', '12 mm', 'Visible area to the bottom board edge'),
    ('OLED_W', '23 mm', 'Visible area width'),
    ('OLED_H', '13 mm', 'Visible area height'),
    ('WINDOW_MARGIN', '0.5 mm', 'Display window margin'),
    ('BEZEL_MARGIN', '1.5 mm', 'Bezel margin around the window'),
    ('BEZEL_DEPTH', '1 mm', 'Bezel depth'),
    # USB-C receptacle opening (8.94 x 3.26 receptacle + clearance)
    ('USB_Y', '11 mm', 'USB center from the bottom board edge'),
    ('USB_W', '9.6 mm', 'USB opening width'),
    ('USB_H', '3.8 mm', 'USB opening height'),
    ('USB_Z_OFF', 'PCB_T / 2 + 1.63 mm', 'USB center above the board mid-plane'),
    ('USB_LIP_GAP', '1 mm', 'Lid lip gap around the receptacle'),
    # Bay
    ('BAY_L', '36 mm', 'Bay length'),
    ('PARTITION', '2 mm', 'Partition thickness'),
    ('WIRE_SLOT_W', '14 mm', 'Wire slot width in the partition'),
    ('WIRE_SLOT_Z0', '0.5 mm', 'Wire slot bottom above the floor'),
    ('WIRE_SLOT_H', '4 mm', 'Wire slot height'),
    # SCD41 module, flat with the air inlet up
    ('SENSOR_L', '21.8 mm', 'Sensor board length'),
    ('SENSOR_W', '13.8 mm', 'Sensor board width'),
    ('SENSOR_X', '3 mm', 'Sensor board corner X'),
    ('SENSOR_Y', '19.5 mm', 'Sensor board corner Y'),
    ('SENSOR_RAISE', '2 mm', 'Posts under the sensor board'),
    ('SENSOR_POST', '3 mm', 'Post size'),
    ('SENSOR_FIT', '0.3 mm', 'Sensor board clearance'),
    ('SENSOR_RIM', '3 mm', 'Retaining corner height above the posts'),
    ('SENSOR_ARM', '4 mm', 'Retaining corner arm length'),
    ('SENSOR_WALL', '1.2 mm', 'Retaining corner thickness'),
    # Vents
    ('VENT_W', '1.6 mm', 'Vent slot width'),
    ('VENT_STEP', '3.6 mm', 'Vent slot pitch'),
    ('BACK_VENT_COUNT', '6', 'Vents in the back wall'),
    ('BACK_VENT_Z0', '2.5 mm', 'Back vents bottom above the floor'),
    ('BACK_VENT_H', '6 mm', 'Back vents height'),
    ('LID_VENT_COUNT', '5', 'Vents in the lid above the sensor'),
    ('LID_VENT_INSET', '2.5 mm', 'Lid vents inset from sensor board edges'),
    # Button, 12x12 tactile switch with an 11.5 mm cap
    ('BUTTON_X', '9.5 mm', 'Button center X'),
    ('BUTTON_Y', '9.5 mm', 'Button center Y'),
    ('BUTTON_HOLE', '12 mm', 'Hole for the cap'),
    ('BUTTON_BODY', '12.4 mm', 'Pocket for the body'),
    ('BUTTON_FRAME', '1.3 mm', 'Frame wall'),
    ('BUTTON_FRAME_DEPTH', '4 mm', 'Frame depth'),
    ('BUTTON_STACK', '12.5 mm', 'Body bottom to cap top, without legs'),
    ('BUTTON_PROTRUDE', '4 mm - LID', 'Cap above the lid: 4 mm cap above its rim, rim under the lid'),
    ('BUTTON_PEDESTAL', '8 mm', 'Pedestal under the body, leaves room for the legs'),
    # Buzzer TMB12A05, 12 x 9.5 mm
    ('BUZZER_X', '27 mm', 'Buzzer center X'),
    ('BUZZER_Y', '9.5 mm', 'Buzzer center Y'),
    ('BUZZER_D', '12.4 mm', 'Buzzer ring inner diameter'),
    ('BUZZER_RING', '1.3 mm', 'Buzzer ring wall'),
    ('BUZZER_RING_DEPTH', '4 mm', 'Buzzer ring depth'),
    ('GRILLE_D', '1.6 mm', 'Grille hole diameter'),
    ('GRILLE_R', '3 mm', 'Grille hole offset from the center'),
    # LEDs, 5 mm
    ('LED_X', '31 mm', 'LEDs center X'),
    ('LED_RED_Y', '23 mm', 'Red LED center Y'),
    ('LED_YELLOW_Y', '30 mm', 'Yellow LED center Y'),
    ('LED_HOLE', '5.2 mm', 'LED hole'),
    # IKEA SKADIS hooks: 5 x 15 mm slots, 40 mm apart in a row, 5 mm board
    ('SKADIS_PITCH', '40 mm', 'Distance between the hooks'),
    ('SKADIS_T', '5 mm', 'Pegboard thickness'),
    ('HOOK_CLEAR', '0.8 mm', 'Clearance over the pegboard thickness'),
    ('HOOK_W', '4.4 mm', 'Hook width across the slot'),
    ('HOOK_STEM_D', '4 mm', 'Hook stem depth along the slot'),
    ('HOOK_TIP', '8 mm', 'Hook tip length down behind the board'),
    ('HOOK_TIP_T', '3 mm', 'Hook tip thickness'),
    ('HOOK_TOP_MARGIN', '6 mm', 'Hook stem from the top outer edge'),
    ('SKADIS_ROW', '20 mm', 'Vertical offset of the staggered slot row'),
    ('HOOK_FLANGE_L', '10 mm', 'Flange length against the back of the base'),
    ('HOOK_FLANGE_T', '1.5 mm', 'Flange thickness'),
    ('HOOK_R', '1 mm', 'Rounding of the hook and peg edges'),
    ('SLOT_CLEAR', '0.15 mm', 'Floor slot clearance around the tenons'),
    ('PEG_W', '4.4 mm', 'Locating peg width across the slot'),
    ('PEG_H', '5 mm', 'Locating peg height along the slot'),
    ('PEG_LEN', '4 mm', 'Locating peg length, below the pegboard thickness'),
    ('PEG_GAP', '0.5 mm', 'Peg clearance above the slot bottom'),
    # Derived
    ('INNER_W', 'BOARD_W + 2 * BOARD_SIDE_GAP', 'Inner width'),
    ('BOARD_X', 'BAY_L + PARTITION + BOARD_GAP', 'Board left edge'),
    ('BOARD_Y', 'BOARD_SIDE_GAP', 'Board bottom edge'),
    ('INNER_L', 'BOARD_X + BOARD_L + BOARD_GAP', 'Inner length'),
    ('INNER_H', 'UNDER + PCB_T + TOP_CLEAR', 'Inner height'),
    ('OUTER_L', 'INNER_L + 2 * WALL', 'Outer length'),
    ('OUTER_W', 'INNER_W + 2 * WALL', 'Outer width'),
    ('LID_Z', 'FLOOR + INNER_H', 'Lid underside height'),
    ('OLED_X', 'BOARD_X + BOARD_L - OLED_FROM_RIGHT - OLED_W', 'Visible area left edge'),
    ('OLED_Y', 'BOARD_Y + OLED_FROM_BOTTOM', 'Visible area bottom edge'),
    ('PART_CLEAR', 'FIT + LIP_T + 0.2 mm', 'Partition gap for the lid lip'),
    ('HOOK_Y', 'OUTER_W - HOOK_TOP_MARGIN - HOOK_STEM_D', 'Hook stem bottom edge'),
    ('HOOK_CX', 'OUTER_L / 2', 'Center between the hooks'),
    ('PEG_CX', 'HOOK_CX', 'Peg center X'),
    ('PEG_Y', 'HOOK_Y - SKADIS_ROW + PEG_GAP', 'Peg bottom edge'),
]

AXES = {'x': 0, 'y': 1, 'z': 2}
H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


def X(e):
    return 'WALL + ({})'.format(e)


def Y(e):
    return 'WALL + ({})'.format(e)


def Z(e):
    return 'FLOOR + ({})'.format(e)


def vec_comp(v, axis):
    return (v.x, v.y, v.z)[AXES[axis]]


class Model:
    def __init__(self, design):
        self.design = design
        self.root = design.rootComponent
        self.units = design.unitsManager
        self.planes = {
            'xy': (self.root.xYConstructionPlane, 'x', 'y'),
            'xz': (self.root.xZConstructionPlane, 'x', 'z'),
            'yz': (self.root.yZConstructionPlane, 'y', 'z'),
        }

    def val(self, expr):
        return self.units.evaluateExpression(expr, 'mm')

    def body(self, name):
        return self.root.bRepBodies.itemByName(name)


class Sketch:
    """Sketch on an origin plane; every shape is dimensioned from the origin."""

    def __init__(self, model, plane, name):
        self.m = model
        construction, self.u_axis, self.v_axis = model.planes[plane]
        self.sk = model.root.sketches.add(construction)
        self.sk.name = name
        self.sk.isComputeDeferred = True
        self.normal = construction.geometry.normal
        # Which sketch direction each model axis maps to
        self.u_orient = H if abs(vec_comp(self.sk.xDirection, self.u_axis)) > 0.5 else V
        self.v_orient = V if self.u_orient == H else H

    def _jitter(self):
        # Fusion refuses a second dimension between points created with an
        # equal coordinate, so shapes start slightly off and dimensions snap them
        self.shapes = getattr(self, 'shapes', 0) + 1
        return 0.0013 * self.shapes

    def to_sketch(self, u, v, jitter=0.0):
        u, v = u + jitter, v + jitter
        c = [0.0, 0.0, 0.0]
        c[AXES[self.u_axis]] = u
        c[AXES[self.v_axis]] = v
        return self.sk.modelToSketchSpace(adsk.core.Point3D.create(*c))

    def _dim(self, p1, p2, orient, expr, value, text):
        dims = self.sk.sketchDimensions
        cons = self.sk.geometricConstraints
        if abs(value) < 1e-6:
            if orient == H:
                cons.addVerticalPoints(p1, p2)
            else:
                cons.addHorizontalPoints(p1, p2)
            return
        d = dims.addDistanceDimension(p1, p2, orient, text)
        d.parameter.expression = expr if value > 0 else '-({})'.format(expr)

    def _text(self, p, du, dv):
        return adsk.core.Point3D.create(p.x + du, p.y + dv, 0)

    def rect(self, u0, v0, du, dv):
        u0v, v0v, duv, dvv = (self.m.val(e) for e in (u0, v0, du, dv))
        j = self._jitter()
        a = self.to_sketch(u0v, v0v, j)
        b = self.to_sketch(u0v + duv, v0v + dvv, j)
        lines = self.sk.sketchCurves.sketchLines.addTwoPointRectangle(a, b)
        pts = []
        for i in range(lines.count):
            line = lines.item(i)
            s, e = line.startSketchPoint.geometry, line.endSketchPoint.geometry
            if abs(e.x - s.x) > abs(e.y - s.y):
                self.sk.geometricConstraints.addHorizontal(line)
            else:
                self.sk.geometricConstraints.addVertical(line)
            for p in (line.startSketchPoint, line.endSketchPoint):
                if p not in pts:
                    pts.append(p)
        pa = min(pts, key=lambda p: p.geometry.distanceTo(a))
        pb = min(pts, key=lambda p: p.geometry.distanceTo(b))
        o = self.sk.originPoint
        self._dim(o, pa, self.u_orient, u0, u0v, self._text(a.asVector().asPoint(), 0, -0.3))
        self._dim(o, pa, self.v_orient, v0, v0v, self._text(a.asVector().asPoint(), -0.3, 0))
        self._dim(pa, pb, self.u_orient, du, duv, self._text(b.asVector().asPoint(), 0, 0.3))
        self._dim(pa, pb, self.v_orient, dv, dvv, self._text(b.asVector().asPoint(), 0.3, 0))

    def circle(self, uc, vc, d):
        ucv, vcv, dv = (self.m.val(e) for e in (uc, vc, d))
        c = self.to_sketch(ucv, vcv, self._jitter())
        circ = self.sk.sketchCurves.sketchCircles.addByCenterRadius(c, dv / 2)
        o = self.sk.originPoint
        self._dim(o, circ.centerSketchPoint, self.u_orient, uc, ucv, self._text(c, 0, -0.3))
        self._dim(o, circ.centerSketchPoint, self.v_orient, vc, vcv, self._text(c, -0.3, 0))
        dim = self.sk.sketchDimensions.addDiameterDimension(circ, self._text(c, dv, dv))
        dim.parameter.expression = d

    def extrude(self, op, axis, start, length, direction=1, body=None, name=None, only=None):
        """Extrude profiles along the model axis from coordinate `start`.

        All profiles by default; `only` filters them, e.g. to skip the
        region enclosed by a ring.
        """
        self.sk.isComputeDeferred = False
        profiles = adsk.core.ObjectCollection.create()
        for p in self.sk.profiles:
            if only is None or only(p):
                profiles.add(p)

        n = vec_comp(self.normal, axis)
        features = self.m.root.features.extrudeFeatures
        inp = features.createInput(profiles, op)
        start_expr = start if n > 0 else '-({})'.format(start)
        inp.startExtent = adsk.fusion.OffsetStartDefinition.create(
            adsk.core.ValueInput.createByString(start_expr))
        extent_dir = (adsk.fusion.ExtentDirections.PositiveExtentDirection if n * direction > 0
                      else adsk.fusion.ExtentDirections.NegativeExtentDirection)
        inp.setOneSideExtent(
            adsk.fusion.DistanceExtentDefinition.create(adsk.core.ValueInput.createByString(length)),
            extent_dir)
        if body is not None:
            inp.participantBodies = [self.m.body(body)]
        feature = features.add(inp)
        feature.name = name or self.sk.name
        return feature


JOIN = adsk.fusion.FeatureOperations.JoinFeatureOperation
CUT = adsk.fusion.FeatureOperations.CutFeatureOperation
NEW = adsk.fusion.FeatureOperations.NewBodyFeatureOperation


def pattern_x(m, feature, count, spacing, name):
    entities = adsk.core.ObjectCollection.create()
    entities.add(feature)
    patterns = m.root.features.rectangularPatternFeatures
    inp = patterns.createInput(
        entities, m.root.xConstructionAxis,
        adsk.core.ValueInput.createByString(count),
        adsk.core.ValueInput.createByString(spacing),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
    p = patterns.add(inp)
    p.name = name
    return p


def add_params(design):
    params = design.userParameters
    for name, expr, comment in PARAMS:
        units = '' if expr.strip().replace('.', '').isdigit() else 'mm'
        existing = params.itemByName(name)
        if existing:
            existing.expression = expr
        else:
            params.add(name, adsk.core.ValueInput.createByString(expr), units, comment)


def build_base(m):
    s = Sketch(m, 'xy', 'Base outline')
    s.rect('0 mm', '0 mm', 'OUTER_L', 'OUTER_W')
    s.extrude(NEW, 'z', '0 mm', 'FLOOR + INNER_H').bodies.item(0).name = 'Base'

    s = Sketch(m, 'xy', 'Base cavity')
    s.rect(X('0 mm'), Y('0 mm'), 'INNER_L', 'INNER_W')
    s.extrude(CUT, 'z', 'FLOOR', 'INNER_H + 1 mm', body='Base')

    s = Sketch(m, 'xy', 'Partition')
    s.rect(X('BAY_L'), Y('0 mm'), 'PARTITION', 'INNER_W')
    s.extrude(JOIN, 'z', 'FLOOR', 'INNER_H', body='Base')

    # Notches at the top corners of the partition let the lid lip pass
    s = Sketch(m, 'xy', 'Partition notches')
    s.rect(X('BAY_L - 0.5 mm'), Y('0 mm'), 'PARTITION + 1 mm', 'PART_CLEAR')
    s.rect(X('BAY_L - 0.5 mm'), Y('INNER_W - PART_CLEAR'), 'PARTITION + 1 mm', 'PART_CLEAR')
    s.extrude(CUT, 'z', 'LID_Z - LIP_H - LIP_NOTCH_CLEAR', 'LIP_H + LIP_NOTCH_CLEAR + 1 mm', body='Base')

    s = Sketch(m, 'xy', 'Wire slot')
    s.rect(X('BAY_L - 0.5 mm'), Y('INNER_W / 2 - WIRE_SLOT_W / 2'), 'PARTITION + 1 mm', 'WIRE_SLOT_W')
    s.extrude(CUT, 'z', Z('WIRE_SLOT_Z0'), 'WIRE_SLOT_H', body='Base')

    holes = [(X('BOARD_X + HOLE_INSET'), Y('BOARD_Y + HOLE_INSET')),
             (X('BOARD_X + BOARD_L - HOLE_INSET'), Y('BOARD_Y + HOLE_INSET')),
             (X('BOARD_X + HOLE_INSET'), Y('BOARD_Y + BOARD_W - HOLE_INSET')),
             (X('BOARD_X + BOARD_L - HOLE_INSET'), Y('BOARD_Y + BOARD_W - HOLE_INSET'))]
    s = Sketch(m, 'xy', 'Standoffs')
    for x, y in holes:
        s.circle(x, y, 'STANDOFF_D')
    s.extrude(JOIN, 'z', 'FLOOR', 'UNDER', body='Base')

    s = Sketch(m, 'xy', 'Standoff pilots')
    for x, y in holes:
        s.circle(x, y, 'STANDOFF_PILOT')
    s.extrude(CUT, 'z', Z('UNDER - STANDOFF_PILOT_DEPTH'), 'STANDOFF_PILOT_DEPTH + 0.1 mm', body='Base')

    # USB-C: obround matching the receptacle
    s = Sketch(m, 'yz', 'USB opening')
    yc, zc = 'BOARD_Y + USB_Y', 'UNDER + PCB_T / 2 + USB_Z_OFF'
    s.rect(Y('{} - (USB_W - USB_H) / 2'.format(yc)), Z('{} - USB_H / 2'.format(zc)), 'USB_W - USB_H', 'USB_H')
    s.circle(Y('{} - (USB_W - USB_H) / 2'.format(yc)), Z(zc), 'USB_H')
    s.circle(Y('{} + (USB_W - USB_H) / 2'.format(yc)), Z(zc), 'USB_H')
    s.extrude(CUT, 'x', 'WALL + INNER_L - 0.5 mm', 'WALL + 1 mm', body='Base')

    # SCD41: posts under the board corners and L-shaped retaining corners
    corners = [('SENSOR_X', 'SENSOR_Y', 1, 1),
               ('SENSOR_X + SENSOR_L', 'SENSOR_Y', -1, 1),
               ('SENSOR_X', 'SENSOR_Y + SENSOR_W', 1, -1),
               ('SENSOR_X + SENSOR_L', 'SENSOR_Y + SENSOR_W', -1, -1)]
    s = Sketch(m, 'xy', 'Sensor posts')
    for cx, cy, dx, dy in corners:
        x0 = cx if dx > 0 else '{} - SENSOR_POST'.format(cx)
        y0 = cy if dy > 0 else '{} - SENSOR_POST'.format(cy)
        s.rect(X(x0), Y(y0), 'SENSOR_POST', 'SENSOR_POST')
    s.extrude(JOIN, 'z', 'FLOOR', 'SENSOR_RAISE', body='Base')

    s = Sketch(m, 'xy', 'Sensor corners')
    outer = '(SENSOR_FIT + SENSOR_WALL)'
    for cx, cy, dx, dy in corners:
        x_out = '{} - {}'.format(cx, outer) if dx > 0 else '{} + SENSOR_FIT'.format(cx)
        y_out = '{} - {}'.format(cy, outer) if dy > 0 else '{} + SENSOR_FIT'.format(cy)
        x_span = '{} - {}'.format(cx, outer) if dx > 0 else '{} - SENSOR_ARM'.format(cx)
        y_span = '{} - {}'.format(cy, outer) if dy > 0 else '{} - SENSOR_ARM'.format(cy)
        span = '{} + SENSOR_ARM'.format(outer)
        s.rect(X(x_span), Y(y_out), span, 'SENSOR_WALL')
        s.rect(X(x_out), Y(y_span), 'SENSOR_WALL', span)
    s.extrude(JOIN, 'z', 'FLOOR', 'SENSOR_RAISE + SENSOR_RIM', body='Base')

    # Button pedestal: presses go into the floor, not into glue
    s = Sketch(m, 'xy', 'Button pedestal')
    s.rect(X('BUTTON_X - BUTTON_PEDESTAL / 2'), Y('BUTTON_Y - BUTTON_PEDESTAL / 2'),
           'BUTTON_PEDESTAL', 'BUTTON_PEDESTAL')
    s.extrude(JOIN, 'z', 'FLOOR', 'LID_Z + LID + BUTTON_PROTRUDE - BUTTON_STACK - FLOOR', body='Base')

    s = Sketch(m, 'xz', 'Back vent')
    first = 'SENSOR_X + SENSOR_L / 2 - (BACK_VENT_COUNT - 1) * VENT_STEP / 2 - VENT_W / 2'
    s.rect(X(first), Z('BACK_VENT_Z0'), 'VENT_W', 'BACK_VENT_H')
    vent = s.extrude(CUT, 'y', 'WALL + INNER_W - 0.5 mm', 'WALL + 1 mm', body='Base')
    pattern_x(m, vent, 'BACK_VENT_COUNT', 'VENT_STEP', 'Back vents')

    # Floor slots for the tenons of the separately printed hooks and peg
    c = 'SLOT_CLEAR'
    s = Sketch(m, 'xy', 'Hanger slots')
    for x in HOOK_X:
        s.rect('{} - {}'.format(x, c), 'HOOK_Y - {}'.format(c), 'HOOK_W + 2 * {}'.format(c), 'HOOK_STEM_D + 2 * {}'.format(c))
    s.rect('PEG_CX - PEG_W / 2 - {}'.format(c), 'PEG_Y - {}'.format(c), 'PEG_W + 2 * {}'.format(c), 'PEG_H + 2 * {}'.format(c))
    s.extrude(CUT, 'z', '-0.1 mm', 'FLOOR + 0.2 mm', body='Base')


# SKADIS hooks 40 mm apart; the peg goes into the staggered slot row between and below them
HOOK_X = ['HOOK_CX - SKADIS_PITCH / 2 - HOOK_W / 2', 'HOOK_CX + SKADIS_PITCH / 2 - HOOK_W / 2']


def fillet(m, body, radius, keep, name):
    edges = adsk.core.ObjectCollection.create()
    for e in m.body(body).edges:
        if keep(e):
            edges.add(e)
    if edges.count == 0:
        return None
    fillets = m.root.features.filletFeatures
    inp = fillets.createInput()
    inp.edgeSetInputs.addConstantRadiusEdgeSet(edges, adsk.core.ValueInput.createByString(radius), True)
    f = fillets.add(inp)
    f.name = name
    return f


def round_corners(m):
    """Round the four vertical outer corners of the base and the lid."""
    length, width = m.val('OUTER_L'), m.val('OUTER_W')
    eps = 1e-4

    def outer_vertical(e):
        a, b = e.startVertex.geometry, e.endVertex.geometry
        if abs(a.x - b.x) > eps or abs(a.y - b.y) > eps:
            return False
        on_x = abs(a.x) < eps or abs(a.x - length) < eps
        on_y = abs(a.y) < eps or abs(a.y - width) < eps
        return on_x and on_y

    for body in ('Base', 'Lid'):
        fillet(m, body, 'CORNER_R', outer_vertical, '{} corners'.format(body))


def build_hangers(m):
    """Hooks and the peg print on their side without supports and get glued into the floor slots.

    Each part has a tenon in the floor slot, a flange against the back of the
    base, and the working part outside: a stem with a tip for the hooks, a
    straight pin for the peg.
    """
    flange_out = '-(HOOK_FLANGE_T)'
    stem_end = '-(HOOK_FLANGE_T + SKADIS_T + HOOK_CLEAR)'

    s = Sketch(m, 'yz', 'Hook profile')
    s.rect('HOOK_Y', '0 mm', 'HOOK_STEM_D', 'FLOOR')
    s.rect('HOOK_Y + HOOK_STEM_D / 2 - HOOK_FLANGE_L / 2', flange_out, 'HOOK_FLANGE_L', 'HOOK_FLANGE_T')
    s.rect('HOOK_Y', stem_end, 'HOOK_STEM_D', 'SKADIS_T + HOOK_CLEAR')
    s.rect('HOOK_Y - HOOK_TIP', '-(HOOK_FLANGE_T + SKADIS_T + HOOK_CLEAR + HOOK_TIP_T)',
           'HOOK_TIP + HOOK_STEM_D', 'HOOK_TIP_T')
    for i, x in enumerate(HOOK_X):
        name = 'Hook {}'.format('LR'[i])
        s.extrude(NEW, 'x', x, 'HOOK_W', name=name).bodies.item(0).name = name

    s = Sketch(m, 'yz', 'Peg profile')
    s.rect('PEG_Y', '0 mm', 'PEG_H', 'FLOOR')
    s.rect('PEG_Y + PEG_H / 2 - HOOK_FLANGE_L / 2', flange_out, 'HOOK_FLANGE_L', 'HOOK_FLANGE_T')
    s.rect('PEG_Y', '-(HOOK_FLANGE_T + PEG_LEN)', 'PEG_H', 'PEG_LEN')
    s.extrude(NEW, 'x', 'PEG_CX - PEG_W / 2', 'PEG_W', name='Peg').bodies.item(0).name = 'Peg'

    # Round everything that goes into the pegboard; the flange and tenon stay sharp to sit flush
    limit = m.val('-(HOOK_FLANGE_T)') - 1e-4
    outside = lambda e: e.boundingBox.maxPoint.z < limit
    for body in ('Hook L', 'Hook R', 'Peg'):
        fillet(m, body, 'HOOK_R', outside, '{} rounding'.format(body))


def build_lid(m):
    s = Sketch(m, 'xy', 'Lid outline')
    s.rect('0 mm', '0 mm', 'OUTER_L', 'OUTER_W')
    s.extrude(NEW, 'z', 'LID_Z', 'LID').bodies.item(0).name = 'Lid'

    # Locating lip around the whole perimeter: only the ring between two rectangles
    s = Sketch(m, 'xy', 'Lid lip')
    s.rect(X('FIT'), Y('FIT'), 'INNER_L - 2 * FIT', 'INNER_W - 2 * FIT')
    s.rect(X('FIT + LIP_T'), Y('FIT + LIP_T'), 'INNER_L - 2 * FIT - 2 * LIP_T', 'INNER_W - 2 * FIT - 2 * LIP_T')
    s.extrude(JOIN, 'z', 'LID_Z - LIP_H', 'LIP_H', body='Lid', only=lambda p: p.profileLoops.count == 2)

    # Gap in the lip over the USB-C receptacle at the board edge
    s = Sketch(m, 'xy', 'Lip USB gap')
    s.rect(X('INNER_L - FIT - LIP_T - 0.5 mm'), Y('BOARD_Y + USB_Y - USB_W / 2 - USB_LIP_GAP'),
           'FIT + LIP_T + 0.5 mm', 'USB_W + 2 * USB_LIP_GAP')
    s.extrude(CUT, 'z', 'LID_Z - LIP_H - 0.1 mm', 'LIP_H + 0.1 mm', body='Lid')

    through = ('LID_Z - 0.1 mm', 'LID + 0.2 mm')

    s = Sketch(m, 'xy', 'Display window')
    s.rect(X('OLED_X - WINDOW_MARGIN'), Y('OLED_Y - WINDOW_MARGIN'),
           'OLED_W + 2 * WINDOW_MARGIN', 'OLED_H + 2 * WINDOW_MARGIN')
    s.extrude(CUT, 'z', *through, body='Lid')

    s = Sketch(m, 'xy', 'Display bezel')
    s.rect(X('OLED_X - BEZEL_MARGIN'), Y('OLED_Y - BEZEL_MARGIN'),
           'OLED_W + 2 * BEZEL_MARGIN', 'OLED_H + 2 * BEZEL_MARGIN')
    s.extrude(CUT, 'z', 'LID_Z + LID - BEZEL_DEPTH', 'BEZEL_DEPTH + 0.1 mm', body='Lid')

    s = Sketch(m, 'xy', 'Sensor vent')
    first = 'SENSOR_X + SENSOR_L / 2 - (LID_VENT_COUNT - 1) * VENT_STEP / 2 - VENT_W / 2'
    s.rect(X(first), Y('SENSOR_Y + LID_VENT_INSET'), 'VENT_W', 'SENSOR_W - 2 * LID_VENT_INSET')
    vent = s.extrude(CUT, 'z', *through, body='Lid')
    pattern_x(m, vent, 'LID_VENT_COUNT', 'VENT_STEP', 'Sensor vents')

    # Button: square frame holding the body, round hole for the cap
    frame_z = 'LID_Z - BUTTON_FRAME_DEPTH'
    s = Sketch(m, 'xy', 'Button frame')
    s.rect(X('BUTTON_X - BUTTON_BODY / 2 - BUTTON_FRAME'), Y('BUTTON_Y - BUTTON_BODY / 2 - BUTTON_FRAME'),
           'BUTTON_BODY + 2 * BUTTON_FRAME', 'BUTTON_BODY + 2 * BUTTON_FRAME')
    s.extrude(JOIN, 'z', frame_z, 'BUTTON_FRAME_DEPTH', body='Lid')

    s = Sketch(m, 'xy', 'Button pocket')
    s.rect(X('BUTTON_X - BUTTON_BODY / 2'), Y('BUTTON_Y - BUTTON_BODY / 2'), 'BUTTON_BODY', 'BUTTON_BODY')
    s.extrude(CUT, 'z', frame_z + ' - 0.1 mm', 'BUTTON_FRAME_DEPTH + 0.1 mm', body='Lid')

    s = Sketch(m, 'xy', 'Button hole')
    s.circle(X('BUTTON_X'), Y('BUTTON_Y'), 'BUTTON_HOLE')
    s.extrude(CUT, 'z', *through, body='Lid')

    # Buzzer: ring to glue it in, grille above it
    ring_z = 'LID_Z - BUZZER_RING_DEPTH'
    s = Sketch(m, 'xy', 'Buzzer ring')
    s.circle(X('BUZZER_X'), Y('BUZZER_Y'), 'BUZZER_D + 2 * BUZZER_RING')
    s.extrude(JOIN, 'z', ring_z, 'BUZZER_RING_DEPTH', body='Lid')

    s = Sketch(m, 'xy', 'Buzzer pocket')
    s.circle(X('BUZZER_X'), Y('BUZZER_Y'), 'BUZZER_D')
    s.extrude(CUT, 'z', ring_z + ' - 0.1 mm', 'BUZZER_RING_DEPTH + 0.1 mm', body='Lid')

    s = Sketch(m, 'xy', 'Buzzer grille')
    s.circle(X('BUZZER_X'), Y('BUZZER_Y'), 'GRILLE_D')
    s.circle(X('BUZZER_X + GRILLE_R'), Y('BUZZER_Y'), 'GRILLE_D')
    s.circle(X('BUZZER_X - GRILLE_R'), Y('BUZZER_Y'), 'GRILLE_D')
    s.circle(X('BUZZER_X'), Y('BUZZER_Y + GRILLE_R'), 'GRILLE_D')
    s.circle(X('BUZZER_X'), Y('BUZZER_Y - GRILLE_R'), 'GRILLE_D')
    s.extrude(CUT, 'z', *through, body='Lid')

    s = Sketch(m, 'xy', 'LED holes')
    s.circle(X('LED_X'), Y('LED_RED_Y'), 'LED_HOLE')
    s.circle(X('LED_X'), Y('LED_YELLOW_Y'), 'LED_HOLE')
    s.extrude(CUT, 'z', *through, body='Lid')


def run(_context):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    # Reuse an empty active design, otherwise start a new document
    if design is None or design.rootComponent.bRepBodies.count or design.timeline.count:
        app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
        design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType

    add_params(design)
    m = Model(design)
    build_base(m)
    build_lid(m)
    build_hangers(m)
    round_corners(m)
    app.activeViewport.fit()
