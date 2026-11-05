Corrosion: CO2 Corrosion Rate
================================

Description
---------------------------

The ``gemini_model.corrosion.co2_corrosion.CO2Corrosion`` model is a
dispatcher that computes the internal CO2 corrosion rate of a pipe or well
tubular, delegating the calculation to one of three industry-standard
correlations selected via the ``corrosion_model`` parameter. The corrosion
rate is returned in mm/year, representing the expected wall loss rate of
carbon steel tubulars exposed to a CO2-containing brine at the given
pressure, temperature, and flow conditions.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - ``corrosion_model``
     - Correlation
   * - ``DLD``
     - de Waard-Lotz-Dugstad (1995)
   * - ``DLM``
     - de Waard-Lotz-Milliams (1991)
   * - ``NORSOK``
     - NORSOK M-506

All three correlations follow the common ``Model`` interface used across
GEMINI: provide inputs ``u`` (and optional state ``x``), and set
``parameters`` including ``corrosion_model`` plus any correlation-specific
parameters (e.g. ``diameter``, ``roughness``).

DLD -- de Waard-Lotz-Dugstad (1995)
---------------------------------------

``gemini_model.corrosion.correlation.dld_model.DLD`` combines a
reaction-controlled and a mass-transfer-controlled corrosion rate in series,
then applies a protective-scale correction factor.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``diameter``
     - Pipe inner diameter :math:`D` (m)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure``
     - Total system pressure :math:`p` (bar)
   * - ``temperature``
     - Temperature :math:`T` (°C)
   * - ``co2_fraction``
     - CO2 mole fraction in the gas phase (-), optional if
       ``co2_partial_pressure`` is given
   * - ``co2_partial_pressure``
     - CO2 partial pressure (bar), optional if ``co2_fraction`` is given
   * - ``flow_rate``
     - Flow rate :math:`v`-basis volumetric flow (m³/s)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``corrosion_rate``
     - CO2 corrosion rate :math:`CR` (mm/yr)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each correlation first converts the CO2 partial pressure to a fugacity,
accounting for non-ideal gas behaviour at elevated pressure (this fugacity
calculation is shared by DLD, DLM, and NORSOK below):

.. math::

    \varphi = \begin{cases}
        10^{\,p\,(0.0031 - 1.4/T)} & p \le 250\ \text{bar} \\
        10^{\,250\,(0.0031 - 1.4/T)} & p > 250\ \text{bar}
    \end{cases}
    \qquad
    f_{CO2} = \varphi \cdot p_{CO2}

where :math:`p_{CO2} = x_{CO2}\cdot p` if the CO2 mole fraction is given
instead of the partial pressure directly, and :math:`T` is the temperature
in Kelvin.

The DLD reaction- and mass-transfer-controlled rates are combined as
resistances in series, then corrected by a scaling factor:

.. math::

    CR_r = 10^{\,4.93 - 1119/T + 0.58\log_{10} f_{CO2}}
    \qquad \text{(reaction-controlled, mm/yr)}

.. math::

    CR_m = 2.45\,\frac{v^{0.8}}{D^{0.2}}\,f_{CO2}
    \qquad \text{(mass-transfer-controlled, mm/yr)}

.. math::

    CR = \left(\frac{1}{CR_r} + \frac{1}{CR_m}\right)^{-1} \cdot F_{scale}

The scaling correction factor (protective FeCO3 scale forming above a
temperature threshold that depends on fugacity) is:

.. math::

    T_{scale} = \frac{2400}{6.7 + 0.6\log_{10}f_{CO2}}
    \qquad
    F_{scale} = \begin{cases}
        \min\!\big(10^{\,2400/T - 0.44\log_{10}f_{CO2} - 6.7},\ 1\big) & T \ge T_{scale} \\
        1 & T < T_{scale}
    \end{cases}

Reference: de Waard, Lotz & Dugstad (1995), *Influence of liquid flow
velocity on CO2 corrosion: A semi-empirical model*.
https://www.osti.gov/biblio/106125

DLM -- de Waard-Lotz-Milliams (1991)
---------------------------------------

``gemini_model.corrosion.correlation.dlm_model.DLM`` uses a single
temperature/fugacity correlation (no explicit flow-velocity term) with the
same scaling correction concept as DLD.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This model has no configuration parameters beyond ``corrosion_model``.

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure``
     - Total system pressure :math:`p` (bar)
   * - ``temperature``
     - Temperature :math:`T` (°C)
   * - ``co2_fraction``
     - CO2 mole fraction in the gas phase (-), optional if
       ``co2_partial_pressure`` is given
   * - ``co2_partial_pressure``
     - CO2 partial pressure (bar), optional if ``co2_fraction`` is given

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``corrosion_rate``
     - CO2 corrosion rate :math:`CR` (mm/yr)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using the CO2 fugacity :math:`f_{CO2}` from the shared calculation
described above:

.. math::

    CR = 10^{\,5.8 - 1710/T + 0.67\log_{10}f_{CO2}} \cdot F_{scale}

.. math::

    T_{scale} = \frac{2400}{6.7 + 0.6\log_{10}f_{CO2}}
    \qquad
    F_{scale} = \begin{cases}
        \min\!\big(10^{\,2400/T - 0.6\log_{10}f_{CO2} - 6.7},\ 1\big) & T \ge T_{scale} \\
        1 & T < T_{scale}
    \end{cases}

Reference: de Waard, Lotz & Milliams (1991), *Predictive model for CO2
corrosion engineering in wet natural gas pipelines*.
https://doi.org/10.5006/1.3585212

NORSOK M-506
---------------------------

``gemini_model.corrosion.correlation.norsok_model.NORSOK`` implements the
NORSOK standard M-506 CO2 corrosion rate model, combining CO2 fugacity,
wall shear stress, and a pH- and temperature-dependent correction.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``diameter``
     - Pipe inner diameter :math:`D` (m)
   * - ``roughness``
     - Pipe roughness :math:`\varepsilon` (m)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure``
     - System pressure :math:`p` (bar)
   * - ``temperature``
     - Temperature :math:`T` (°C)
   * - ``co2_fraction``
     - CO2 mole fraction in the gas phase (-), optional if
       ``co2_partial_pressure`` is given
   * - ``co2_partial_pressure``
     - CO2 partial pressure (bar), optional if ``co2_fraction`` is given
   * - ``water_flow_rate``
     - Water flow rate :math:`Q_w` (m³/day)
   * - ``water_density``
     - Water density :math:`\rho` (kg/m³)
   * - ``water_viscosity``
     - Water viscosity :math:`\mu` (cP)
   * - ``bicarb_concentration``
     - Bicarbonate concentration (mg/l), used in the pH calculation
   * - ``ionic_strength``
     - Ionic strength (g/l), used in the pH calculation

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``corrosion_rate``
     - CO2 corrosion rate :math:`CR` (mm/yr)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using the CO2 fugacity :math:`f_{CO2}` from the shared calculation
described in the DLD section above, the NORSOK rate equation is:

.. math::

    CR = K_t \cdot f_{CO2}^{0.62} \cdot
        \left(\frac{\tau}{19}\right)^{0.146 + 0.0324\log_{10}f_{CO2}} \cdot f(pH_t)

**Temperature factor** :math:`K_t` is linearly interpolated from a fixed
lookup table over temperature (°C):

.. list-table::
   :header-rows: 1

   * - T (°C)
     - 5
     - 15
     - 20
     - 40
     - 60
     - 80
     - 90
     - 120
     - 150
   * - :math:`K_t`
     - 0.42
     - 1.59
     - 4.762
     - 8.927
     - 10.695
     - 9.949
     - 6.250
     - 7.770
     - 5.203

**Wall shear stress** :math:`\tau` uses a simplified single-phase
(water) friction-factor correlation:

.. math::

    v = \frac{Q_w}{A} \qquad
    f = 0.001375\left[1 + \left(20000\,\frac{\varepsilon}{D} +
        \frac{10^6\,\mu}{v\,D\,\rho}\right)^{0.33}\right]
    \qquad
    \tau = \tfrac{1}{2}\rho\,f\,v^2

**pH** is computed from a carbonate-equilibrium model (bicarbonate
concentration, ionic strength, CO2 partial pressure, temperature/pressure
-dependent equilibrium constants :math:`K_0, K_1, K_2, K_{sp,FeCO_3}, K_w`),
solved iteratively for :math:`[\text{H}^+]` via Newton-Raphson (the model
does genuinely iterate here, unlike the explicit friction-factor
correlations used elsewhere in GEMINI), then adjusted to a fixed reference
pH curve :math:`f(pH_t)` that is piecewise-fitted per temperature bin
(5-150 °C) to represent the effect of protective iron-carbonate scaling on
the corrosion rate.

Reference: NORSOK Standard M-506, *CO2 corrosion rate calculation model*.
https://www.standard.no

CO2 Partial Pressure (helper model)
---------------------------------------

``gemini_model.corrosion.correlation.co2_partial_pressure_model.CO2PartialPressureModel``
estimates the CO2 partial pressure of a system from gas composition and
sample/system conditions, for use as an input to the corrosion correlations
above when a direct measurement is not available.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This model has no configuration parameters; it operates directly on the
input measurements below.

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``gas_pressure``
     - Gas phase pressure at sample conditions :math:`p_{gas}` (bar)
   * - ``co2_mol_fraction``
     - CO2 mole fraction in the gas phase :math:`x_{CO2}` (-)
   * - ``gas_water_ratio``
     - Gas-water ratio :math:`GWR` (sm³/sm³)
   * - ``gas_density``
     - Gas phase density :math:`\rho_{gas}` (kg/m³)
   * - ``gas_molecular_weight``
     - Gas (average) molar weight :math:`M_{gas}` (g/mol)
   * - ``temperature_sample``
     - Temperature of the sample :math:`T_{sample}` (°C)
   * - ``temperature_system``
     - Temperature of the system :math:`T_{system}` (°C)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``"CO2 Partial Pressure [bar]"``
     - Estimated CO2 partial pressure :math:`p_{CO2}` (bar)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    K_H(T) = 0.0385\,\exp\!\left(2400\left(\frac{1}{T} - \frac{1}{293.15}\right)\right)
    \qquad \text{(Henry's constant, mol/(l.bar))}

.. math::

    C_{aq} = x_{CO2}\,K_H(T_{sample})\,p_{gas}
    \qquad \text{(CO2 dissolved in liquid, mol/l)}

.. math::

    C_{g} = x_{CO2}\,\frac{GWR \cdot \rho_{gas}}{M_{gas}}
    \qquad \text{(CO2 present in gas phase, mol/l)}

.. math::

    p_{CO2} = \frac{C_{aq} + C_g}{K_H(T_{system})}
