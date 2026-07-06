import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from mdm.design.design import design_section

# Test 1: Span (is_support=False) with a very small sagging moment
# This should trigger As_min. We want to see if the deflection check is included in the html output.
report = design_section(
    name="Test Span",
    M=1.0,  # Very small moment
    V=10.0,
    is_support=False,
    fcu=30.0, fy=460.0, fyv=250.0, b=230.0, h=450.0, cover=30.0,
    main_bar_dia=20.0, link_dia=10.0,
    span_length=4000.0,
    support_cond="Continuous",
    highlight_title="",
    bg_color="",
    show_position=True,
    notes=None,
    skip_shear=False,
    skip_drawing=True
)

html = report["html"]
print("--- TEST 1: SPAN (M=1.0) ---")
print("Does it use As,min?", "A_{s,min}" in html)
print("Does it check deflection?", "Deflection Check" in html)

# Test 2: Cantilever Span 
# The cantilever span might not be evaluated with sagging moment, but let's see what happens for a support task
report_support = design_section(
    name="Test Support",
    M=-10.0,  # Hogging moment
    V=10.0,
    is_support=True,
    fcu=30.0, fy=460.0, fyv=250.0, b=230.0, h=450.0, cover=30.0,
    main_bar_dia=20.0, link_dia=10.0,
    span_length=2000.0,
    support_cond="Cantilever",
    highlight_title="",
    bg_color="",
    show_position=True,
    notes=None,
    skip_shear=False,
    skip_drawing=True
)

html_supp = report_support["html"]
print("\n--- TEST 2: SUPPORT (M=-10.0) ---")
print("Does it use As,min?", "A_{s,min}" in html_supp)
print("Does it check deflection?", "Deflection Check" in html_supp)
