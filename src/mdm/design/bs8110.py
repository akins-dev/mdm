import math
from typing import Tuple, List

# Clause and Table References
REF_EFFECTIVE_DEPTH = "Section properties"
REF_ULTIMATE_MOMENT = "Clause 3.4.4.4"
REF_STEEL_YIELD = "Clause 3.1.9"
REF_COMPRESSION_YIELD = "Clause 3.4.4.4"
REF_MIN_STEEL = "Table 3.25"
REF_MAX_STEEL = "Clause 3.12.6.1"
REF_SHEAR_CAPACITY = "Table 3.8"
REF_DEPTH_FACTOR = "Table 3.8 Note 2"
REF_SHEAR_LINKS = "Table 3.7"
REF_MAX_SHEAR = "Clause 3.4.5.2"
REF_MAX_SPACING = "Clause 3.12.11"
REF_DEFLECTION_BASIC = "Table 3.9"
REF_DEFLECTION_MF = "Table 3.10"
REF_MODIFICATION_FACTOR = "Equation 7"
REF_BAR_SELECTION = "Detailing"

# Safety Factors and Limits
PARTIAL_SAFETY_STEEL = 0.95  # 1/1.05 after Amendment 3 (previously 0.87)
LIMIT_D_PRIME_X = 0.37       # For fy = 460
K_PRIME = 0.156

# ---------------------------------------------------------------------------
# Column effective-length factor beta  (BS 8110-1:1997 Tables 3.19 & 3.20)
# Keyed [cond_top][cond_bot]; symmetric, so (i,j) == (j,i). None = not permitted
# (condition 4 pairs only with condition 1). le = beta * l0, l0 = clear height.
# ---------------------------------------------------------------------------
BETA_BRACED = {
    1: {1: 0.75, 2: 0.80, 3: 0.90},
    2: {1: 0.80, 2: 0.85, 3: 0.95},
    3: {1: 0.90, 2: 0.95, 3: 1.00},
}
BETA_UNBRACED = {
    1: {1: 1.2, 2: 1.3, 3: 1.6, 4: 2.2},
    2: {1: 1.3, 2: 1.5, 3: 1.8},
    3: {1: 1.6, 2: 1.8},
    4: {1: 2.2},
}

def beta_effective_length(braced: bool, cond_top: int, cond_bot: int) -> float:
    """Return beta from Table 3.19 (braced) or 3.20 (unbraced).

    The tables are symmetric in top/bottom. Condition 4 (unrestrained) is only
    tabulated against condition 1; any other pairing with 4 is not permitted and
    conservatively falls back to the largest tabulated value.
    """
    table = BETA_BRACED if braced else BETA_UNBRACED
    ct, cb = int(cond_top), int(cond_bot)
    val = table.get(ct, {}).get(cb)
    if val is None:
        val = table.get(cb, {}).get(ct)  # symmetry
    if val is None:
        # Not permitted combination (e.g. cond 4 against 2/3): use worst tabulated.
        val = 1.0 if braced else 2.2
    return val

# Biaxial bending coefficient beta (BS 8110-1:1997 Table 3.22), as a function of
# N/(b h fcu). Linear interpolation between the tabulated break-points.
_BIAXIAL_BETA_TABLE = [
    (0.000, 1.00), (0.100, 0.88), (0.200, 0.77), (0.300, 0.65),
    (0.400, 0.53), (0.500, 0.42), (0.600, 0.30),
]

def biaxial_beta(n_ratio: float) -> float:
    """Interpolate beta for biaxial bending from Table 3.22 given N/(b*h*fcu)."""
    pts = _BIAXIAL_BETA_TABLE
    if n_ratio <= pts[0][0]:
        return pts[0][1]
    if n_ratio >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= n_ratio <= x1:
            t = (n_ratio - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return pts[-1][1]

STANDARD_BAR_AREAS = {
    6: [28.3, 56.6, 84.9, 113, 142, 170, 198, 226, 255, 283],
    8: [50.3, 101, 151, 201, 252, 302, 352, 402, 453, 503],
    10: [78.5, 157, 236, 314, 393, 471, 550, 628, 707, 785],
    12: [113, 226, 339, 452, 566, 679, 792, 905, 1020, 1130],
    16: [201, 402, 603, 804, 1010, 1210, 1410, 1610, 1810, 2010],
    20: [314, 628, 943, 1260, 1570, 1890, 2200, 2510, 2830, 3140],
    25: [491, 982, 1470, 1960, 2450, 2950, 3440, 3930, 4420, 4910],
    32: [804, 1610, 2410, 3220, 4020, 4830, 5630, 6430, 7240, 8040],
    40: [1260, 2510, 3770, 5030, 6280, 7540, 8800, 10100, 11300, 12600],
    50: [1960, 3930, 5890, 7850, 9820, 11800, 13700, 15700, 17700, 19600]
}

def get_bar_area(diameter: int, count: int = 1) -> float:
    if diameter in STANDARD_BAR_AREAS and 1 <= count <= 10:
        return STANDARD_BAR_AREAS[diameter][count - 1]
    return count * math.pi * (diameter ** 2) / 4.0

def select_bar_arrangement(required_area: float, b: float, cover: float, link_dia: float, max_agg_size: float = 20.0, is_compression: bool = False, target_dia: int = None) -> Tuple[List[int], int, float]:
    """
    Find the optimal bar arrangement (layer_counts, diameter, area_provided) that provides at least the required area
    and satisfies the spacing requirements in 1 or 2 layers.
    Returns (layer_counts, diameter, area_provided) or ([], 0, 0.0) if none found.
    """
    best_arrangement = None
    min_area_surplus = float('inf')
    
    if is_compression:
        dias_to_try = [12, 16, 20]
    else:
        dias_to_try = [20, 25, 16]
        
    if target_dia and target_dia in STANDARD_BAR_AREAS:
        if target_dia in dias_to_try:
            dias_to_try.remove(target_dia)
        dias_to_try.insert(0, target_dia)
        
    for dia in dias_to_try:
        count = 2 # Minimum 2 bars
        area_provided = 0.0
        while count <= 20:
            area_provided = get_bar_area(dia, count)
            if area_provided >= required_area:
                break
            count += 1
        
        if count > 20 or area_provided < required_area:
            continue
            
        min_spacing = max(max_agg_size + 5.0, float(dia))
        available_width = b - 2 * cover - 2 * link_dia
        
        max_n_layer = int((available_width + min_spacing) // (dia + min_spacing))
        
        if max_n_layer < 2:
            continue
            
        if count <= max_n_layer:
            layer_counts = [count]
        elif count <= 2 * max_n_layer:
            l1 = max_n_layer
            l2 = count - max_n_layer
            if l2 < 2:
                if l1 > 2:
                    l1 -= 1
                    l2 += 1
                else:
                    continue
            layer_counts = [l1, l2]
        else:
            continue
            
        surplus = area_provided - required_area
        penalty = 0.0 if len(layer_counts) == 1 else required_area * 0.1
        
        if (surplus + penalty) < min_area_surplus:
            min_area_surplus = surplus + penalty
            best_arrangement = (layer_counts, dia, area_provided)
                
    if best_arrangement:
        return best_arrangement
    return [], 0, 0.0
