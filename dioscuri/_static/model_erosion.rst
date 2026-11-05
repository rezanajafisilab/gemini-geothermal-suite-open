Erosion: Erosional Velocity/Rate
===================================

Description
---------------------------

The ``gemini_model.erosion.erosion_model`` module is a dispatcher that
computes either an erosional rate (mm/year, for a metal-loss correlation) or
an erosional velocity limit (m/s, for the API velocity-based approach),
depending on the selected ``erosion_model`` parameter. Rate-based
correlations (DNVGL, OKA, E/CRC Tulsa) return an erosion rate in mm/year,
representing expected wall loss due to solid-particle or sand erosion. The
API correlation instead returns a maximum recommended flow velocity (m/s)
below which erosion risk is considered acceptable.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - ``erosion_model``
     - Correlation
   * - ``DNVGL``
     - DNV GL RP-O501 erosion rate correlation
   * - ``OKA``
     - Oka erosion rate correlation
   * - ``E/CRC Tulsa``
     - University of Tulsa E/CRC erosion rate correlation
   * - ``API``
     - API RP 14E erosional velocity limit

Use ``normalize_model_name(name)`` to resolve a user-facing spelling (e.g.
``"DNV"``, ``"ECRC"``) to its canonical form, and
``is_velocity_model(name)`` to check whether a model produces a velocity
limit (``API``) rather than an erosion rate.

Common flow terms
---------------------------

All three rate correlations first derive the particle/fluid mass flow and
mixture impact velocity from the volumetric flow rate, via the shared
helper ``gemini_model.erosion.correlation._common.mass_flow_and_velocity``:

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Symbol
     - Name
     - Description
   * - :math:`Q`
     - ``flowRate``
     - Fluid flow rate (input, m³/h)
   * - :math:`\rho_f`
     - ``rho_fluid``
     - Mixture density of the fluid (input, kg/m³)
   * - :math:`D`
     - ``diameter``
     - Inner diameter of the pipe (input, m)
   * - :math:`\dot{m}_p`
     - --
     - Particle/fluid mass flow (kg/s)
   * - :math:`U_p`
     - --
     - Mixture impact velocity (m/s)
   * - :math:`A`
     - --
     - Pipe cross-sectional area (m²)

.. math::

    \dot{m}_p = \frac{Q\,\rho_f}{3600} \qquad
    A = \frac{\pi}{4}D^2 \qquad
    U_p = \frac{\dot{m}_p}{\rho_f\,A}

API RP 14E (velocity limit)
---------------------------------

``gemini_model.erosion.correlation.API.ErosionAPI`` computes the maximum
recommended flow velocity to limit erosion, using the classic API RP 14E
"C-factor" approach.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This model has no configuration parameters.

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``rho_fluid``
     - Mixture density of the fluid :math:`\rho_f` (kg/m³)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``erosion_velocity_ms``
     - Maximum erosion-limited flow velocity :math:`U_{erosion}` (m/s)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    U_{erosion} = C_{unit} \cdot \frac{C}{\sqrt{\rho_f}}
    \qquad C = 125,\quad C_{unit} = \frac{0.3048}{\sqrt{0.0283/0.454}}

DNV GL RP-O501
---------------------------

``gemini_model.erosion.correlation.DNV.ErosionDNV`` computes erosion rate
for a given pipe material and particle impact angle, using material-specific
constants :math:`K`, :math:`n`, and pipe density :math:`\rho_{pipe}`.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``mater``
     - Pipe material: ``steel``, ``titanium``, ``GRP/epoxy``,
       ``GRP/vinyl ester``

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``alpha``
     - Particle impact angle :math:`\alpha` (deg)
   * - ``flowRate``, ``rho_fluid``, ``diameter``
     - Shared flow terms, see "Common flow terms" above

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``erosion_rate_mm_yr``
     - Erosion rate :math:`EL` (mm/yr)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Material-dependent constants:

.. list-table::
   :header-rows: 1
   :widths: 30 20 20 30

   * - ``mater``
     - :math:`K`
     - :math:`n`
     - :math:`\rho_{pipe}` (kg/m³)
   * - ``steel``
     - :math:`2\times10^{-9}`
     - 2.6
     - 7800
   * - ``titanium``
     - :math:`2\times10^{-9}`
     - 2.6
     - 4500
   * - ``GRP/epoxy``
     - :math:`0.3\times10^{-9}`
     - 3.6
     - 1800
   * - ``GRP/vinyl ester``
     - :math:`0.6\times10^{-9}`
     - 3.6
     - 1800

Impact-angle function (with :math:`\alpha` in radians):

.. math::

    F(\alpha) = \alpha\big(9.37 + \alpha(-42.295 + \alpha(110.864 +
        \alpha(-175.804 + \alpha(170.137 + \alpha(-98.398 + \alpha(31.211 -
        4.17\alpha)))))))\big)

The impacted-area projection and erosion rate are:

.. math::

    A_t = \frac{A}{\sin\alpha}
    \qquad
    EL = \frac{31.5576\times10^6\,\dot{m}_p\,K\,U_p^{\,n}\,F(\alpha)}{\rho_{pipe}\,A_t}
    \quad \text{[mm/yr]}

Reference: DNV GL, *Recommended Practice RP-O501, Erosive Wear in Piping
Systems*.

Oka
---------------------------

``gemini_model.erosion.correlation.OKA.ErosionOKA`` uses reference particle
velocity/diameter and material-hardness-dependent exponents.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``mater_particle``
     - Particle material: ``SIO2``, ``SIC``, ``GLASS``

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``alpha``
     - Particle impact angle :math:`\alpha` (deg)
   * - ``Hv``
     - Particle Vickers hardness :math:`H_v` (GPa)
   * - ``diameter_particle``
     - Particle diameter :math:`d_p` (mm)
   * - ``flowRate``, ``rho_fluid``, ``diameter``
     - Shared flow terms, see "Common flow terms" above

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``erosion_rate_mm_yr``
     - Erosion rate :math:`EL` (mm/yr)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Particle-material-dependent constants:

.. list-table::
   :header-rows: 1
   :widths: 25 15 30 30

   * - ``mater_particle``
     - :math:`K`
     - Exponents :math:`(k_1, k_2, k_3)`
     - Reference :math:`(U_{p,ref}\,[\text{m/s}], d_{p,ref}\,[\mu\text{m}])`
   * - ``SIO2``
     - 65
     - :math:`(-0.12,\ 2.3\,H_v^{0.038},\ 0.19)`
     - (104, 326)
   * - ``SIC``
     - 45
     - :math:`(-0.05,\ 3\,H_v^{0.085},\ 0.19)`
     - (99, 326)
   * - ``GLASS``
     - 27
     - :math:`(-0.16,\ 2.1,\ 0.19)`
     - (100, 200)

.. math::

    E(\alpha) = K\,(H_v)^{k_1} \left(\frac{U_p}{U_{p,ref}}\right)^{k_2}
        \left(\frac{d_p}{d_{p,ref}}\right)^{k_3}
    \qquad \text{[mm}^3\text{/kg]}

.. math::

    A_t = \frac{A}{\sin\alpha}
    \qquad
    EL = (3600 \cdot 24 \cdot 365.25)\,\frac{\dot{m}_p}{A_t}\,E(\alpha)
    \quad \text{[mm/yr]}

Reference: Oka, Y.I. et al. (2005), *Practical estimation of erosion damage
caused by solid particle impact*, Wear 259.
https://www.sciencedirect.com/science/article/pii/S0043164805000979

E/CRC Tulsa
---------------------------

``gemini_model.erosion.correlation.TULSA.ErosionTULSA`` uses a Vickers-to-
Brinell hardness conversion and a particle-shape factor.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``rho_pipe``
     - Pipe material density :math:`\rho_{pipe}` (kg/m³)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``alpha``
     - Particle impact angle :math:`\alpha` (deg)
   * - ``Hv``
     - Particle Vickers hardness :math:`H_v` (GPa)
   * - ``fs``
     - Particle shape factor :math:`F_s`, 0.2 (rounded) - 1 (sharp) (-)
   * - ``flowRate``, ``rho_fluid``, ``diameter``
     - Shared flow terms, see "Common flow terms" above

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``erosion_rate_mm_yr``
     - Erosion rate :math:`EL` (mm/yr)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Impact-angle function (with :math:`\alpha` in radians):

.. math::

    F(\alpha) = 5.4\alpha - 10.11\alpha^2 + 10.93\alpha^3 - 6.33\alpha^4 + 1.42\alpha^5

Vickers-to-Brinell hardness conversion:

.. math::

    H_{v}' = \frac{H_v}{0.009807} \qquad
    H_{b}' = 0.95057\,H_v' - 0.03743

Erosion ratio and rate:

.. math::

    ER = C\,H_b'^{\,-0.59}\,F_s\,U_p^{\,n}\,F(\alpha)
    \qquad C = 2.17\times10^{-7},\ n = 2.41 \qquad \text{[kg/kg]}

.. math::

    A_t = \frac{A}{\sin\alpha}
    \qquad
    EL = (3600\cdot 24\cdot 365.25)\,\frac{ER\,\dot{m}_p}{\rho_{pipe}\,A_t}
    \quad \text{[mm/yr]}

Reference: University of Tulsa Erosion/Corrosion Research Center (E/CRC).
http://www.ecrc.utulsa.edu/
