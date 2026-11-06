"""Physics of packaging mass.

Key identity used everywhere:
    areal mass [g/m^2] = thickness [um] x density [g/cm^3]
because 1 um x 1 g/cm^3 = 1e-6 m x 1e6 g/m^3 = 1 g/m^2.

Component mass [g] = area [m^2] x sum(layer areal masses [g/m^2]).
"""
from dataclasses import dataclass, asdict
from typing import Optional

from . import materials


@dataclass
class Layer:
    material: str                 # canonical key, e.g. "PET", "ALUMINUM", "PAPER"
    kind: str                     # film | foil | metallization | paper | coating | adhesive | wall
    thickness_um: Optional[float] = None   # films, foils, rigid walls (metallization in um too)
    grammage_gsm: Optional[float] = None   # paper, coatings, adhesives

    def to_dict(self):
        return asdict(self)


def layer_areal_mass(layer, density_which="nominal", rel=0.0):
    """g/m^2 for one layer. `rel` scales the thickness/grammage (e.g. -0.10)."""
    if layer.grammage_gsm is not None:
        return layer.grammage_gsm * (1 + rel)
    rho = materials.density(layer.material, density_which)
    return layer.thickness_um * (1 + rel) * rho


# ---- geometry ---------------------------------------------------------------
# All dimensions in mm, returned area in m^2.
def area_m2(geometry, w_mm, h_mm, g_mm=0.0):
    """Film/paper blank area for the supported geometry models.

    flat_pouch       : two faces            -> 2*W*H
    standup_pouch    : two faces + bottom gusset panel (G = unfolded gusset depth)
                                            -> 2*W*H + W*G
    side_gusset_bag  : two faces + two side gussets (G = unfolded gusset width)
                                            -> 2*W*H + 2*G*H
    sheet            : one flat piece (wrap, lid, label, carton blank) -> W*H
    Seal areas are assumed to be INCLUDED in the stated dimensions (assumption).
    """
    mm2 = {
        "flat_pouch": 2 * w_mm * h_mm,
        "standup_pouch": 2 * w_mm * h_mm + w_mm * g_mm,
        "side_gusset_bag": 2 * w_mm * h_mm + 2 * g_mm * h_mm,
        "sheet": w_mm * h_mm,
    }[geometry]
    return mm2 / 1e6


def area_range_m2(geometry, w_mm, h_mm, g_mm, dim_rel):
    lo = area_m2(geometry, w_mm * (1 - dim_rel), h_mm * (1 - dim_rel), g_mm * (1 - dim_rel))
    hi = area_m2(geometry, w_mm * (1 + dim_rel), h_mm * (1 + dim_rel), g_mm * (1 + dim_rel))
    return lo, hi


# ---- component mass ---------------------------------------------------------
def layered_mass_g(area, layers, density_which="nominal"):
    return area * sum(layer_areal_mass(l, density_which) for l in layers)


def layer_rel_tol(layer, tol):
    if layer.kind == "metallization":
        return None  # handled by absolute nm bounds
    if layer.kind in ("coating", "adhesive"):
        return tol["coat_weight_rel"]
    if layer.grammage_gsm is not None:
        return tol["grammage_rel"]
    return tol["film_thickness_rel"]


def layer_areal_range(layer, tol):
    """(min, max) g/m^2 for one layer given tolerances and density range."""
    if layer.kind == "metallization":
        rho_lo = materials.density("ALUMINUM", "min")
        rho_hi = materials.density("ALUMINUM", "max")
        return (tol["metallization_nm_min"] / 1000 * rho_lo,
                tol["metallization_nm_max"] / 1000 * rho_hi)
    r = layer_rel_tol(layer, tol)
    if layer.grammage_gsm is not None:
        return layer.grammage_gsm * (1 - r), layer.grammage_gsm * (1 + r)
    return (layer.thickness_um * (1 - r) * materials.density(layer.material, "min"),
            layer.thickness_um * (1 + r) * materials.density(layer.material, "max"))


def layered_mass_range_g(geometry, w_mm, h_mm, g_mm, layers, tol):
    a_lo, a_hi = area_range_m2(geometry, w_mm, h_mm, g_mm, tol["dimension_rel"])
    lo = sum(layer_areal_range(l, tol)[0] for l in layers)
    hi = sum(layer_areal_range(l, tol)[1] for l in layers)
    return a_lo * lo, a_hi * hi


def rigid_mass_g(surface_cm2, wall_um, material, density_which="nominal"):
    """Rigid part from surface area x average wall thickness x density.
    cm^2 -> m^2 is /1e4; um*g/cm^3 -> g/m^2."""
    return surface_cm2 / 1e4 * wall_um * materials.density(material, density_which)


def rigid_mass_range_g(surface_cm2, wall_um, material, tol):
    a = tol["dimension_rel"]
    t = tol["film_thickness_rel"]
    # surface area is an area: (1 +/- dim_rel)^2
    lo = surface_cm2 * (1 - a) ** 2 / 1e4 * wall_um * (1 - t) * materials.density(material, "min")
    hi = surface_cm2 * (1 + a) ** 2 / 1e4 * wall_um * (1 + t) * materials.density(material, "max")
    return lo, hi


def family_mass_fractions(area, layers):
    """{family: fraction of component mass} using nominal values."""
    masses = {}
    for l in layers:
        fam = "METALLIZATION" if l.kind == "metallization" else materials.family(l.material)
        masses[fam] = masses.get(fam, 0.0) + area * layer_areal_mass(l)
    total = sum(masses.values())
    return {k: v / total for k, v in masses.items()}
