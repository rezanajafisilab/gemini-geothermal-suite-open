Well: Pressure and Temperature Hydraulics
==========================================

Description
---------------------------

The ``gemini_model.well.pressure_drop.DPDT`` model computes the pressure and
temperature profile along a multi-section wellbore, for single- or two-phase
flow, in either the production (upward) or injection (downward) direction.

The well is discretized into a series of cells (with length, diameter,
inclination, and roughness defined per cell). For each cell, the model
selects a friction-pressure-drop correlation depending on whether the flow is
single-phase liquid or a gas/liquid mixture, and adds a hydrostatic pressure
term and a heat-loss-driven temperature change. Results are accumulated along
the well to give the total pressure drop and the outlet (wellhead or
bottomhole) pressure/temperature.

This model underpins the :doc:`application_production_well_performance`
application (VLP calculations) and the ESP model's inlet/outlet pressure
estimates in :doc:`application_esp`.

Fluid properties (density, viscosity, gas mass fraction, etc.) required for
these calculations are obtained from a PVT model, see :doc:`model_fluid_pvt`.

Parameters
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Parameter
     - Description
   * - ``length``
     - Length of each well cell (m), array
   * - ``angle``
     - Inclination of each cell (rad), array
   * - ``diameter``
     - Diameter of each cell (m), array
   * - ``roughness``
     - Pipe roughness of each cell (mm), array
   * - ``friction_correlation``
     - Single-phase correlation name (``"darcy_weisbach"``)
   * - ``friction_correlation_2p``
     - Two-phase correlation name (``"BeggsBrill"``)
   * - ``correction_factors``
     - 2-element list ``[gain, offset]`` applied to the final outlet pressure

Inputs
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Input
     - Description
   * - ``direction``
     - ``"up"`` (production) or ``"down"`` (injection)
   * - ``pressure``
     - Inlet pressure (Pa)
   * - ``temperature``
     - Inlet temperature (K)
   * - ``flowrate``
     - Volumetric flow rate (m³/s)
   * - ``temperature_ambient``
     - Ambient/formation temperature (K)

Outputs
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Output
     - Description
   * - ``pressure_output``
     - Outlet pressure (Pa), after applying correction factors
   * - ``temperature_output``
     - Outlet temperature (K)
   * - ``pressuredrop_fric_output``
     - Total frictional pressure drop (Pa)
   * - ``pressuredrop_grav_output``
     - Total gravitational (hydrostatic) pressure drop (Pa)
   * - ``section_pressure_output``
     - Pressure at each cell along the well (Pa)
   * - ``section_temperature_output``
     - Temperature at each cell along the well (K)

Correlations
---------------------------

For each well cell, ``DPDT`` computes the fluid mixture properties with the
PVT model (see :doc:`model_fluid_pvt`), then selects between two
friction/gravity correlations depending on whether a gas phase is present
(``gemini_model.well.correlation``), plus a separate temperature-drop
correlation:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Correlation
     - Used for
   * - ``DarcyWeisbach``
     - Single-phase friction pressure drop and hydrostatic pressure change,
       used when no gas phase is present (:math:`m_g = 0`)
   * - ``BeggsBrill``
     - Two-phase (gas/liquid) friction and hydrostatic pressure drop,
       used when a gas phase is present
   * - ``TemperatureDrop``
     - Along-well temperature change due to heat transfer with the
       surrounding formation, based on cell heat-transfer coefficient and
       surface area

Darcy-Weisbach (single-phase)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``gemini_model.well.correlation.darcyweisbach.DarcyWeisbach`` computes the
friction and gravity pressure-drop terms for single-phase liquid flow, using
the Swamee-Jain explicit approximation of the Colebrook-White friction
factor.

Reference: Swamee, P. K., & Jain, A. K. (1976). *Explicit equations for
pipe-flow problems*. Journal of the Hydraulics Division, 102(5), 657-664.

.. math::

    Re = \frac{|u_{s,l}| \, \rho_l \, D}{\eta_l}

.. math::

    f = \frac{0.25}{\left[\log_{10}\left(\dfrac{K}{3.7 D} +
        \dfrac{5.74}{Re^{0.9}}\right)\right]^2}

.. math::

    \Delta p_{fric} = f \, \frac{\rho_l \, L}{D} \, \frac{|u_{s,l}| \, u_{s,l}}{2}
    \qquad
    \Delta p_{grav} = \rho_l \, g \, L \, \sin(\theta)

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Symbol
     - Name
     - Description
   * - :math:`u_{s,l}`
     - --
     - Superficial liquid velocity (m/s)
   * - :math:`\rho_l`
     - --
     - Liquid density (kg/m³)
   * - :math:`\theta`
     - ``angle``
     - Cell inclination (rad)
   * - :math:`\eta_l`
     - --
     - Liquid viscosity (Pa.s)
   * - :math:`D`
     - ``diameter``
     - Cell (pipe) diameter (m)
   * - :math:`K`
     - ``roughness``
     - Cell roughness (m)
   * - :math:`L`
     - ``length``
     - Cell length (m)
   * - :math:`Re`
     - --
     - Reynolds number (-)
   * - :math:`f`
     - --
     - Darcy friction factor (-)
   * - :math:`\Delta p_{fric}`
     - --
     - Frictional pressure drop (Pa)
   * - :math:`\Delta p_{grav}`
     - --
     - Gravitational pressure drop (Pa)

Beggs-Brill (two-phase)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``gemini_model.well.correlation.beggsbrill.BeggsBrill`` computes the
friction and gravity pressure-drop terms for two-phase (gas/liquid) flow,
following the Beggs-Brill correlation as presented in Shoham, O. (2006),
*Mechanistic Modeling of Gas-Liquid Two-Phase Flow in Pipes*, p. 59.
Internally, inputs are converted to US field units for the correlation and
results are converted back to SI.

Reference: Shoham, O. (2006), *Mechanistic Modeling of Gas-Liquid Two-Phase
Flow in Pipes*, Society of Petroleum Engineers, p. 59.

**Step 1 — Flow parameters.** The superficial gas/liquid velocities
:math:`u_{s,g}`, :math:`u_{s,l}` give the mixture velocity, no-slip liquid
holdup, liquid velocity number, and mixture Froude number:

.. math::

    u_m = u_{s,l} + u_{s,g}
    \qquad
    \lambda_l = \frac{u_{s,l}}{u_m}

.. math::

    N_{Lv} = 1.938\, u_{s,l} \left(\frac{\rho_l}{\sigma}\right)^{0.25}
    \qquad
    Fr_m^2 = \frac{u_m^2}{g \, D}

**Step 2 — Flow-regime boundaries.** Regime boundaries :math:`L_1`-:math:`L_4`
are functions of :math:`\lambda_l` only:

.. math::

    L_1 = 316\,\lambda_l^{0.302}
    \qquad
    L_2 = 0.0009252\,\lambda_l^{-2.4684}

.. math::

    L_3 = 0.10\,\lambda_l^{-1.4516}
    \qquad
    L_4 = 0.5\,\lambda_l^{-6.738}

Comparing :math:`\lambda_l` and :math:`Fr_m^2` against :math:`L_1`-:math:`L_4`
classifies the flow into one of four regimes: **segregated**,
**intermittent**, **distributed**, or **transition** (interpolated between
segregated and intermittent).

**Step 3 — Liquid holdup.** A horizontal-flow holdup :math:`H_{l,0}` is
first computed with regime-dependent coefficients :math:`(a, b, c)`:

.. math::

    H_{l,0} = a\,\frac{\lambda_l^{\,b}}{Fr_m^{2c}}

.. list-table::
   :header-rows: 1
   :widths: 25 25 25 25

   * - Regime
     - :math:`a`
     - :math:`b`
     - :math:`c`
   * - Segregated
     - 0.98
     - 0.4846
     - 0.0868
   * - Intermittent
     - 0.845
     - 0.5351
     - 0.0173
   * - Distributed
     - 1.065
     - 0.5824
     - 0.0609

:math:`H_{l,0}` is then corrected for pipe inclination:

.. math::

    C = \max\!\big(0,\ (1-\lambda_l)\ln(d\,\lambda_l^{\,e}\,N_{Lv}^{\,f}\,Fr_m^{2h})\big)

.. math::

    \psi = 1 + C\left[\sin(1.8\theta) - \tfrac{1}{3}\sin^3(1.8\theta)\right]
    \qquad
    H_l = H_{l,0}\,\psi

with regime- and flow-direction-dependent coefficients :math:`(d,e,f,h)`
(distributed flow uses :math:`\psi = 1`, i.e. no inclination correction; for
the transition regime, :math:`H_l` is interpolated between the segregated
and intermittent values using the same weighting factor as the regime
boundaries). :math:`H_l` is clamped to :math:`[0, 1]`.

**Step 4 — Two-phase friction factor ratio.** With
:math:`y = \lambda_l/H_l^2`:

.. math::

    s = \begin{cases}
        \ln(2.2y - 1.2) & 1 < y < 1.2 \\[4pt]
        \dfrac{\ln y}{-0.0523 + 3.182\ln y - 0.8725(\ln y)^2 + 0.01853(\ln y)^4}
            & \text{otherwise}
    \end{cases}
    \qquad f_{tp}/f_n = e^s

**Step 5 — Pressure gradients.** Mixture properties use the no-slip holdup
:math:`\lambda_l` for the friction term and the (slip) liquid holdup
:math:`H_l` for the gravity term:

.. math::

    \rho_m = \lambda_l \rho_l + (1-\lambda_l)\rho_g
    \qquad
    \eta_m = \lambda_l \eta_l + (1-\lambda_l)\eta_g
    \qquad
    Re_m = \frac{u_m \rho_m D}{\eta_m}

.. math::

    \lambda_{fric} = \left[-0.8685\ln\!\left(\frac{1.964\ln(Re_m) - 3.8215}{Re_m}
        + \frac{\varepsilon}{3.71 D}\right)\right]^{-2}

.. math::

    \Delta p_{fric} = \tfrac{1}{2}\rho_m\,u_m|u_m|\;\lambda_{fric}\;
        (f_{tp}/f_n)\;\frac{L}{D}

.. math::

    \Delta p_{grav} = \big[H_l\rho_l + (1-H_l)\rho_g\big]\,g\,L\,\sin(\theta)

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Symbol
     - Name
     - Description
   * - :math:`u_{s,g}`, :math:`u_{s,l}`
     - --
     - Superficial gas / liquid velocity (m/s)
   * - :math:`\rho_g`, :math:`\rho_l`
     - --
     - Gas / liquid density (kg/m³)
   * - :math:`\theta`
     - ``angle``
     - Cell inclination (rad)
   * - :math:`\eta_g`, :math:`\eta_l`
     - --
     - Gas / liquid viscosity (Pa.s)
   * - :math:`\sigma`
     - --
     - Gas-liquid surface tension (N/m)
   * - :math:`D`
     - ``diameter``
     - Cell (pipe) diameter (m)
   * - :math:`\varepsilon`
     - ``roughness``
     - Cell roughness (m)
   * - :math:`L`
     - ``length``
     - Cell length (m)
   * - :math:`\lambda_l`, :math:`H_l`
     - --
     - No-slip / slip liquid holdup (-)
   * - :math:`\Delta p_{fric}`
     - --
     - Frictional pressure drop (Pa)
   * - :math:`\Delta p_{grav}`
     - --
     - Gravitational pressure drop (Pa)

Temperature Drop
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``gemini_model.well.correlation.temperaturedrop.TemperatureDrop`` computes
the along-cell temperature change from heat exchange with the surrounding
formation/ambient, using a lumped heat-transfer coefficient and the mixture
heat capacity:

.. math::

    c_{p,mix} = \frac{m_l}{m_l+m_g}\,c_{p,l} + \frac{m_g}{m_l+m_g}\,c_{p,g}

.. math::

    \dot{Q} = U \, A \, (T_{in} - T_{ambient})
    \qquad
    \Delta T = \frac{\dot{Q}}{(m_l + m_g)\,c_{p,mix}}

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Symbol
     - Name
     - Description
   * - :math:`T_{in}`
     - ``temperature``
     - Cell inlet temperature (K)
   * - :math:`U`
     - --
     - Heat transfer coefficient (W/m².K)
   * - :math:`m_l`, :math:`m_g`
     - --
     - Liquid / gas mass flow rate (kg/s)
   * - :math:`c_{p,l}`, :math:`c_{p,g}`
     - --
     - Liquid / gas heat capacity (J/kg.K)
   * - :math:`A`
     - --
     - Cell surface area (m²)
   * - :math:`T_{ambient}`
     - ``temperature_ambient``
     - Ambient/formation temperature (K)
   * - :math:`\Delta T`
     - --
     - Cell temperature change (K)
