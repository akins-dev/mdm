# BS 8110-1:1997 Column Design and Detailing Reference

This document extracts and summarizes all primary clauses from BS 8110-1:1997 related to the design and detailing of reinforced concrete columns.

## 1. Classification of Columns (Section 3.8.1)

### 1.1 Short vs. Slender Columns (3.8.1.3)
A column may be considered as **short** when both the ratios $l_{ex}/h$ and $l_{ey}/b$ are less than:
*   **15** for braced columns
*   **10** for unbraced columns
It should otherwise be considered as **slender**.

### 1.2 Braced vs. Unbraced Columns (3.8.1.5)
A column may be considered **braced** in a given plane if lateral stability to the structure as a whole is provided by walls or bracing designed to resist all lateral forces in that plane. It should otherwise be considered as **unbraced**.

### 1.3 Effective Height ($l_e$) (3.8.1.6)
The effective height, $l_e$, of a column in a given plane may be obtained from:
$l_e = \beta l_0$
Where $\beta$ is a coefficient based on end conditions:
*   **Condition 1:** Connected monolithically to beams at least as deep as the column.
*   **Condition 2:** Connected monolithically to beams or slabs shallower than the column.
*   **Condition 3:** Connected to members that provide some nominal restraint.
*   **Condition 4:** Unrestrained against lateral movement and rotation (e.g., cantilever).

### 1.4 Slenderness Limits (3.8.1.7 & 3.8.1.8)
*   **General:** The clear distance $l_0$ between end restraints should not exceed 60 times the minimum thickness of the column.
*   **Unbraced:** If one end is unrestrained, $l_0 \le 60b$ or $100b^2/h$, whichever is less.

## 2. Moments and Forces in Columns (Section 3.8.2)

### 2.1 Axial Forces
The axial force in a column may be calculated on the assumption that beams and slabs transmitting force into it are simply supported.

### 2.2 Minimum Eccentricity (3.8.2.4)
At no section in a column should the design moment be taken as less than that produced by considering the design ultimate axial load as acting at a minimum eccentricity, $e_{min}$, equal to **0.05 times the overall dimension** of the column in the plane of bending considered, but **not more than 20 mm**.

## 3. Design of Column Section for ULS (Section 3.8.4)

### 3.1 Short Braced Columns with Symmetrical Beams (3.8.4.4)
For a short column supporting an approximately symmetrical arrangement of beams (spans not differing by more than 15%, uniformly distributed imposed loads), the design ultimate axial load may be calculated as:
$N = 0.35f_{cu}A_c + 0.7A_{sc}f_y$

### 3.2 Short Columns Resisting Moments and Axial Forces (3.8.4.3)
Where a column cannot be subjected to significant moments, it may be designed so that the ultimate axial load does not exceed:
$N = 0.4f_{cu}A_c + 0.8A_{sc}f_y$

### 3.3 Biaxial Bending (3.8.4.5)
When it is necessary to consider biaxial bending, symmetrically reinforced rectangular sections may be designed to withstand an increased moment about one axis:
*   If $M_x/h' \ge M_y/b'$: design for $M'_x = M_x + \beta \frac{h'}{b'} M_y$
*   If $M_x/h' < M_y/b'$: design for $M'_y = M_y + \beta \frac{b'}{h'} M_x$
Where $\beta$ is a coefficient derived from $N / (bhf_{cu})$.

### 3.4 Shear in Columns (3.8.4.6)
The design shear strength of columns may be checked in accordance with beam shear. For rectangular sections in compression, no check is required provided that $M/N$ does not exceed $0.6h$ and $v$ does not exceed the maximum value (lesser of $0.8\sqrt{f_{cu}}$ or $5$ N/mm²).

## 4. Slender Columns (Section 3.8.3)

### 4.1 Additional Moments ($M_{add}$)
Slender columns must be designed for an additional moment induced by their deflection at the ultimate limit state:
$a_u = \beta_a K h$
$M_{add} = N a_u$
Where $K$ is a reduction factor correcting deflection for the influence of axial load, and $\beta_a = \frac{1}{2000}(\frac{l_e}{b'})^2$.

### 4.2 Design Moments in Braced Slender Columns
The maximum design moment for the column will be the greatest of:
1.  $M_2$ (the larger initial end moment from the frame analysis)
2.  $M_i + M_{add}$
3.  $M_1 + M_{add}/2$
4.  $e_{min}N$

### 4.3 Additional Moments on Attached Members (3.8.3.9)
Where a highly slender column ($l_e/h > 20$) is connected monolithically to other members (like beams, slabs, or bases), those connecting members must be designed to withstand the additional design moments ($M_{add}$) applied by the ends of the column.
*   If there are columns both above and below a joint, the beams or slabs must be designed to withstand the **sum** of the additional moments from both columns.

## 5. Detailing Rules (Section 3.12)

### 5.1 Minimum Reinforcement (3.12.5.3, Table 3.25)
*   **Rectangular columns:** $100A_{sc} / A_c \ge 0.4\%$
*   Minimum number of longitudinal bars: 4 in rectangular, 6 in circular.
*   Minimum bar size: 12 mm.

### 5.2 Maximum Reinforcement (3.12.6.2)
The longitudinal reinforcement should not exceed:
*   Vertically-cast columns: **6%**
*   Horizontally-cast columns: **8%**
*   At laps: **10%**

### 5.3 Containment / Links (3.12.7.1)
Links or ties must be provided to contain compression reinforcement:
*   **Size:** At least 1/4 the size of the largest compression bar or 6 mm (whichever is greater).
*   **Spacing:** Maximum spacing of 12 times the size of the smallest compression bar.
*   **Arrangement:** Every corner bar, and each alternate bar (or bundle) in an outer layer should be supported by a link passing round it with an included angle $\le 135^\circ$. No bar within a compression zone should be further than 150 mm from a restrained bar.
