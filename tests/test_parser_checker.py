"""Checker-side tests: the parser reads raw text; expected values hand-computed."""
import json
import pytest

from epr import spec_parser, checker

TOL = json.load(open("config/tolerances.json"))


def test_pouch_with_mixed_units_and_gusset():
    # face 6.5 in x 9 in = 165.1 x 228.6 mm ; gusset 3.5 in = 88.9 mm
    # area = 2*165.1*228.6 + 165.1*88.9 = 75,483.72 + 14,677.39 = 90,161.11 mm^2 = 0.0901611 m^2
    # 48 ga PET = 12.192 um x 1.39 = 16.94688 g/m^2
    # 0.35 mil foil = 8.89 um x 2.70 = 24.003 g/m^2
    # 3 mil LLDPE = 76.2 um x 0.92 = 70.104 g/m^2
    # adhesive 2 x 1.8 = 3.6 g/m^2      total = 114.65388 g/m^2
    # mass = 0.0901611 x 114.65388 = 10.3373 g
    t = ('Stand-up pouch (doypack). Face size 6.5" W x 9" H, bottom gusset 3.5 in (fully opened). '
         'Structure (out→in): 48 ga PET / 0.35 mil Al foil / 3 mil LLDPE; adhesive laminated, 2 x 1.8 gsm PU adhesive.')
    p = spec_parser.parse_component(t, TOL)
    assert not p.uncertain
    assert p.has_foil and not p.has_metallization
    assert p.mass_nominal_g == pytest.approx(10.3373, rel=1e-4)
    assert p.derived_category == "Multi-material flexible laminate"


def test_metallized_mono_pp_bag():
    # flat pouch 100 x 150 mm -> 2*100*150 = 30,000 mm^2 = 0.03 m^2
    # BOPP 20 um x 0.905 = 18.1 ; met BOPP 18 um x 0.905 = 16.29 ; 40 nm Al = 0.108 ; adhesive 1.0
    # total 35.498 g/m^2 x 0.03 = 1.06494 g ; adhesive share 1.0/35.498 = 2.8 % (< 5 %) -> mono PP
    t = "Flat pouch — Laminate: 20 µm BOPP / 18 µm metallized BOPP (~40 nm Al). Solventless adhesive 1 g/m² per interface. Dimensions per face 100 x 150 mm."
    p = spec_parser.parse_component(t, TOL)
    assert not p.uncertain
    assert p.has_metallization and not p.has_foil
    assert p.mass_nominal_g == pytest.approx(1.06494, rel=1e-4)
    assert p.derived_category == "PP flexible"
    # With 2.0 g/m^2 adhesive: 2.0/36.498 = 5.48 % >= 5 % -> adhesive becomes 'significant' under the
    # PLACEHOLDER rule, so the category flips to multi-material. (A real rulebook may treat adhesives differently.)
    p2 = spec_parser.parse_component(t.replace("1 g/m²", "2 g/m²"), TOL)
    assert p2.mass_nominal_g == pytest.approx(1.09494, rel=1e-4)
    assert p2.derived_category == "Multi-material flexible laminate"


def test_carton_by_basis_weight():
    # 60 lb/3000 ft2 = 97.6486 g/m^2 ; sheet 10 in x 4 in = 254 x 101.6 mm = 0.0258064 m^2
    # mass = 2.51996 g
    p = spec_parser.parse_component("Wrap-around paper label, 60 lb/3000 ft² uncoated; label size 10 in x 4 in.", TOL)
    assert p.mass_nominal_g == pytest.approx(2.51996, rel=1e-4)
    assert p.derived_category == "Paper/paperboard"


def test_capacity_is_not_weight():
    # '16 oz capacity' is a volume; the part weight is 9.5 oz = 269.3205 g
    p = spec_parser.parse_component("Flint glass jar, 16 oz capacity; part weight 9.5 oz.", TOL)
    assert p.stated_weight_g == pytest.approx(269.3205, abs=1e-3)
    assert p.derived_category == "Glass"


def test_rigid_surface_in2():
    # 50 in^2 = 322.58 cm^2 = 0.032258 m^2 ; 12 mil = 304.8 um x 1.39 = 423.672 g/m^2 -> 13.6668 g
    p = spec_parser.parse_component("PET bottle; surface area 50 in², average wall 12 mil PET.", TOL)
    assert p.mass_nominal_g == pytest.approx(13.6668, rel=1e-4)


def test_missing_unit_is_inconclusive_not_guessed():
    p = spec_parser.parse_component("Clear OPP wrap label, 60; label size 87 x 91 mm.", TOL)
    assert p.uncertain and p.mass_range_g is None


def _item(**kw):
    base = dict(sku="AAA-1111", component_id="C1", layers=[{"material": "PET", "form": "film"}],
                category="PET flexible", weight_g=1.0)
    base.update(kw)
    return base


def test_checker_flags_oz_confusion():
    p = spec_parser.parse_component("PP screw cap 28 mm; part weight 2.5 g.", TOL)
    u, ph = checker.check_unit_and_physics(2.5 * 28.3495, p)
    assert ph["status"] == "FAIL" and u["status"] == "FAIL" and "oz" in u["explanation"]


def test_checker_flags_metallized_reported_as_foil():
    p = spec_parser.parse_component(
        "Flat pouch — Laminate: 20 µm BOPP / 18 µm metallized BOPP. Dimensions per face 100 x 150 mm.", TOL)
    it = _item(layers=[{"material": "BOPP", "form": "film"}, {"material": "aluminium foil", "form": "foil", "thickness_um": 7}])
    assert checker.check_metal(it, p)["status"] == "FAIL"


def test_checker_flags_missing_foil_layer():
    p = spec_parser.parse_component(
        "Sachet — Spec: 12 µm PET / 9 µm Al foil / 75 µm LLDPE. Face size 50 x 80 mm.", TOL)
    it = _item(layers=[{"material": "PET", "form": "film"}, {"material": "LLDPE", "form": "film"}],
               category="Multi-material flexible laminate")
    r = checker.check_structure(it, p)
    assert r["status"] == "FAIL" and "foil" in r["explanation"].lower()
