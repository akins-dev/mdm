"""
BS 8110-1:1997 Constants and References Module
"""

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
