"""Physics tests. Every expected value is HAND-COMPUTED in the comment above it."""
import math
import pytest

from epr import units, physics, categories
from epr.physics import Layer

TOL = {"dimension_rel": 0.02, "film_thickness_rel": 0.10, "grammage_rel": 0.05,
       "coat_weight_rel": 0.25, "metallization_nm_min": 10, "metallization_nm_max": 100}


# ---------------- unit conversions ----------------
def test_gauge_to_um():
    # 48 ga x 0.254 um/ga = 12.192 um
    assert units.thickness_um(48, "ga") == pytest.approx(12.192)


def test_mil_to_um():
    # 3 mil x 25.4 = 76.2 um
    assert units.thickness_um(3, "mil") == pytest.approx(76.2)


def test_foil_inches_to_um():
    # 0.00035 in x 25400 um/in = 8.89 um
    assert units.thickness_um(0.00035, "in") == pytest.approx(8.89)


def test_oz_to_g():
    # avoirdupois ounce, exact definition
    assert units.mass_g(1, "oz") == pytest.approx(28.349523125)
    # 9.5 oz = 269.3205 g
    assert units.mass_g(9.5, "oz") == pytest.approx(269.3205, abs=1e-3)


def test_inch_to_mm():
    # 6.5 in x 25.4 = 165.1 mm
    assert units.length_mm(6.5, "in") == pytest.approx(165.1)


def test_basis_weight_lb3000_to_gsm():
    # 453.59237 g / (3000 x 0.3048^2 m^2) = 453.59237 / 278.70912 = 1.627476 g/m^2 per lb
    assert units.grammage_gsm(1, "lb3000") == pytest.approx(1.627476, abs=1e-5)
    # 60 lb -> 97.6486 g/m^2
    assert units.grammage_gsm(60, "lb3000") == pytest.approx(97.6486, abs=1e-3)


# ---------------- areal mass ----------------
def test_film_areal_mass():
    # 12 um PET x 1.39 g/cm3 = 16.68 g/m^2
    assert physics.layer_areal_mass(Layer("PET", "film", thickness_um=12)) == pytest.approx(16.68)


def test_foil_areal_mass():
    # 9 um Al x 2.70 = 24.3 g/m^2
    assert physics.layer_areal_mass(Layer("ALUMINUM", "foil", thickness_um=9)) == pytest.approx(24.3)


def test_metallization_areal_mass_is_negligible():
    # 40 nm = 0.04 um x 2.70 = 0.108 g/m^2  (vs 24.3 g/m^2 for 9 um foil: ~225x less)
    m = physics.layer_areal_mass(Layer("ALUMINUM", "metallization", thickness_um=0.04))
    assert m == pytest.approx(0.108)


def test_grammage_layer():
    # paper layer given in g/m^2 is used directly
    assert physics.layer_areal_mass(Layer("PAPER", "paper", grammage_gsm=80)) == 80


# ---------------- geometry ----------------
def test_flat_pouch_area_two_faces():
    # 2 x 150 mm x 200 mm = 60,000 mm^2 = 0.06 m^2
    assert physics.area_m2("flat_pouch", 150, 200) == pytest.approx(0.06)


def test_standup_pouch_area_with_gusset():
    # 2 x 150 x 200 + 150 x 80 = 60,000 + 12,000 = 72,000 mm^2 = 0.072 m^2
    assert physics.area_m2("standup_pouch", 150, 200, 80) == pytest.approx(0.072)


def test_side_gusset_bag_area():
    # 2 x 100 x 300 + 2 x 60 x 300 = 60,000 + 36,000 = 96,000 mm^2
    assert physics.area_m2("side_gusset_bag", 100, 300, 60) == pytest.approx(0.096)


# ---------------- component mass ----------------
def test_pet_foil_pe_pouch_mass():
    # PET 12 um: 16.68 ; Al 9 um: 24.3 ; LLDPE 75 um x 0.92 = 69.0 ; total 109.98 g/m^2
    # flat pouch 150 x 200 mm -> 0.06 m^2 -> 109.98 x 0.06 = 6.5988 g
    layers = [Layer("PET", "film", 12), Layer("ALUMINUM", "foil", 9), Layer("LLDPE", "film", 75)]
    a = physics.area_m2("flat_pouch", 150, 200)
    assert physics.layered_mass_g(a, layers) == pytest.approx(6.5988)


def test_carton_by_grammage():
    # blank 300 x 200 mm = 0.06 m^2 x 350 g/m^2 = 21.0 g
    a = physics.area_m2("sheet", 300, 200)
    assert physics.layered_mass_g(a, [Layer("PAPER", "paper", grammage_gsm=350)]) == pytest.approx(21.0)


def test_rigid_wall_mass():
    # 300 cm^2 = 0.03 m^2 ; 300 um PET x 1.39 = 417 g/m^2 ; 0.03 x 417 = 12.51 g
    assert physics.rigid_mass_g(300, 300, "PET") == pytest.approx(12.51)


def test_mass_range_single_film_sheet():
    # 100 x 100 mm sheet, 12 um PET, dim +/-2 %, thickness +/-10 %, PET 1.370-1.455
    # area lo 98x98 mm = 0.009604 m^2 ; hi 102x102 = 0.010404 m^2
    # areal lo 10.8 x 1.370 = 14.796 ; hi 13.2 x 1.455 = 19.206
    # mass lo 0.142101 g ; hi 0.199819 g
    lo, hi = physics.layered_mass_range_g("sheet", 100, 100, 0, [Layer("PET", "film", 12)], TOL)
    assert lo == pytest.approx(0.142101, rel=1e-5)
    assert hi == pytest.approx(0.199819, rel=1e-5)


# ---------------- placeholder categories ----------------
def test_metallized_mono_pp_stays_mono():
    # BOPP 20 um (18.1 g/m^2) + 40 nm Al (0.108) + met BOPP 18 um (16.29): Al fraction ~0.3 % -> ignored
    layers = [Layer("PP", "film", 20), Layer("PP", "film", 18), Layer("ALUMINUM", "metallization", 0.04)]
    f = physics.family_mass_fractions(1.0, layers)
    assert categories.assign("flexible", f) == "PP flexible"


def test_foil_laminate_is_multi_material():
    # foil is 24.3 / 109.98 = 22 % of mass -> significant
    layers = [Layer("PET", "film", 12), Layer("ALUMINUM", "foil", 9), Layer("LLDPE", "film", 75)]
    f = physics.family_mass_fractions(1.0, layers)
    assert f["ALUMINUM"] == pytest.approx(24.3 / 109.98)
    assert categories.assign("flexible", f) == "Multi-material flexible laminate"
