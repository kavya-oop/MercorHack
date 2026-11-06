"""Unit conversions used by both the generator and the checker.

Every factor below is either an exact legal definition or a stated
industry convention. Sources are noted inline so judges can audit them.
"""

# ---- length -> millimetres ----------------------------------------------
# 1 inch = 25.4 mm exactly (International Yard and Pound Agreement, 1959).
LENGTH_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4}

# ---- thickness -> micrometres --------------------------------------------
# 1 mil = 0.001 in = 25.4 um (exact, follows from the inch definition).
# 1 gauge (plastic film) = 0.01 mil = 0.254 um, i.e. "100 ga = 1 mil".
#   NOTE: gauge is a North-American flexible-packaging INDUSTRY CONVENTION,
#   not an SI/legal definition. Not independently sourced in this project.
#   (Sheet-metal gauge is a different, non-linear system and is NOT supported.)
THICKNESS_TO_UM = {
    "um": 1.0, "nm": 0.001, "mm": 1000.0, "in": 25400.0,
    "mil": 25.4, "ga": 0.254,
}

# ---- mass -> grams ----------------------------------------------------------
# avoirdupois ounce = 28.349523125 g and pound = 453.59237 g (exact, 1959).
MASS_TO_G = {"g": 1.0, "kg": 1000.0, "mg": 0.001,
             "oz": 28.349523125, "lb": 453.59237}

# ---- grammage (areal mass) -> g/m^2 ----------------------------------------
# "lb/3000 ft2" basis weight: 453.59237 g / (3000 * 0.09290304 m^2)
# 1 ft = 0.3048 m exactly, so 1 ft^2 = 0.09290304 m^2.
LB_PER_3000FT2_TO_GSM = 453.59237 / (3000 * 0.3048 ** 2)   # = 1.627476 g/m^2
GRAMMAGE_TO_GSM = {"gsm": 1.0, "lb3000": LB_PER_3000FT2_TO_GSM}


def length_mm(value, unit):
    return value * LENGTH_TO_MM[unit]


def thickness_um(value, unit):
    return value * THICKNESS_TO_UM[unit]


def mass_g(value, unit):
    return value * MASS_TO_G[unit]


def grammage_gsm(value, unit):
    return value * GRAMMAGE_TO_GSM[unit]


# Common unit-confusion factors the checker looks for (reported / true).
UNIT_CONFUSIONS = {
    "oz<->g (x28.35)": MASS_TO_G["oz"],
    "kg<->g or g<->mg (x1000)": 1000.0,
    "in<->mm (x25.4)": 25.4,
    "lb<->g (x453.6)": MASS_TO_G["lb"],
    "in^2<->mm^2 area (x645.16)": 25.4 ** 2,
    "cm<->mm (x10)": 10.0,
    "mil<->um (x25.4, same as in<->mm)": 25.4,
}
