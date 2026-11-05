Reservoir Performance Models
==============================

Description
---------------------------

The ``gemini_model.reservoir`` package groups models used to characterize
reservoir performance from production/injection data: inflow performance,
injectivity/productivity indices, reservoir pressure estimation, and
bottomhole pressure-drop with skin.

These models underpin the :doc:`application_production_well_performance` and
:doc:`application_injectivity` applications.

Inflow Performance Relationship (IPR)
---------------------------------------

``gemini_model.reservoir.inflow_performance.IPR`` computes bottomhole
pressure for production or injection cases using a linear
productivity/injectivity relation.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``type``
     - ``"production_reservoir"`` or ``"injection_reservoir"``
   * - ``reservoir_pressure``
     - Reservoir pressure :math:`P_{res}` (Pa)
   * - ``productivity_index``
     - Productivity index :math:`PI` (m³/s/Pa), used when
       ``type = "production_reservoir"``
   * - ``injectivity_index``
     - Injectivity index :math:`II` (m³/s/Pa), used when
       ``type = "injection_reservoir"``

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``flow``
     - Flow rate :math:`Q` (m³/s)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``bottomhole_pressure``
     - Bottomhole pressure :math:`P_{bh}` (Pa)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    P_{bh} = P_{res} - \frac{Q}{PI} \quad \text{(production)}
    \qquad
    P_{bh} = P_{res} + \frac{Q}{II} \quad \text{(injection)}

Reference: Tarek Ahmed, *Reservoir Engineering Handbook* (5th ed.), Chapter 7
- Oil Well Performance.

Injectivity Index
---------------------------

``gemini_model.reservoir.injectivity_index.injectivity_index`` computes the
injectivity index from measured bottomhole pressure and injection flow rate,
i.e. the flow rate achievable per unit of pressure differential.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``reservoir_pressure``
     - Reservoir pressure :math:`P_{res}` (Pa)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``flow``
     - Injection flow rate :math:`Q` (m³/s)
   * - ``bottomhole_pressure``
     - Measured bottomhole pressure :math:`P_{bh}` (Pa)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``injectivity_index``
     - Injectivity index :math:`II` (m³/s/Pa)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    \Delta P = P_{bh} - P_{res} \qquad II = \frac{Q}{\Delta P}

Reference: R. Arnold (2021), *Analytics-Driven Method for Injectivity
Analysis in Tight and Heterogeneous Waterflooded Reservoir*, Proceedings
joint convention Bandung.

Reservoir Pressure Estimation
---------------------------------

``gemini_model.reservoir.reservoir_pressure_estimation.reservoir_pressure``
estimates (static) reservoir pressure using a linear regression on
:math:`p/Q` vs. :math:`1/Q`, derived from a series of flow and bottomhole
pressure measurements (a "slope plot" or Hall-type analysis).

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This model has no configuration parameters; it operates directly on the
input measurement arrays.

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``flow``
     - Array of flow rate measurements :math:`Q_i` (m³/s)
   * - ``bottomhole_pressure``
     - Array of bottomhole pressure measurements :math:`P_{bh,i}` (Pa)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``reservoir_pressure``
     - Estimated reservoir pressure :math:`P_{res}` (Pa)
   * - ``r_squared``
     - Coefficient of determination :math:`R^2` of the linear fit (-)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    \frac{P_{bh,i}}{Q_i} = m \cdot \frac{1}{Q_i} + b \qquad
    P_{res} = m

where :math:`m` and :math:`b` are obtained from a least-squares linear fit
across the measurement series :math:`i`, and the fitted slope :math:`m` is
taken as the estimated reservoir pressure. Fit quality is reported via the
coefficient of determination:

.. math::

    R^2 = 1 - \frac{\sum_i \left(\frac{P_{bh,i}}{Q_i} -
        \widehat{\frac{P_{bh,i}}{Q_i}}\right)^2}
        {\sum_i \left(\frac{P_{bh,i}}{Q_i} - \overline{\frac{P_{bh}}{Q}}\right)^2}

Reference: Akin (2019), *Geothermal re-injection performance evaluation
using surveillance analysis methods*, Renewable Energy.

Bottomhole and Reservoir Pressure Drop (with Skin)
-----------------------------------------------------

``gemini_model.reservoir.reservoir_pressuredrop.bottomhole_skin_dp`` computes
the pressure components due to radial (Darcy) flow, near-wellbore skin, and
the hydrostatic fluid column, for given reservoir rock/fluid parameters.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``reservoir_pressure``
     - Reservoir pressure :math:`P_{res}` (Pa)
   * - ``reservoir_radius``
     - Reservoir (drainage) radius :math:`r_e` (m)
   * - ``reservoir_permeability``
     - Reservoir permeability :math:`k` (m²)
   * - ``reservoir_thickness``
     - Reservoir thickness :math:`h` (m)
   * - ``reservoir_top``
     - Depth to top of reservoir, for the hydrostatic column :math:`z_{top}` (m)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``flow``
     - Flow rate :math:`Q` (m³/s)
   * - ``viscosity``
     - Fluid viscosity :math:`\mu` (Pa.s)
   * - ``density``
     - Fluid density :math:`\rho` (kg/m³)
   * - ``well_radius``
     - Wellbore radius :math:`r_w` (m)
   * - ``skin_factor``
     - Near-wellbore skin factor :math:`S` (-)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``Hydrostatic_dp``
     - Hydrostatic pressure drop :math:`\Delta P_{HH}` (Pa)
   * - ``skin_dp``
     - Skin pressure drop :math:`\Delta P_{skin}` (Pa)
   * - ``bottomhole_dp``
     - Radial (Darcy) flow pressure drop :math:`\Delta P_{flow}` (Pa)
   * - ``reservoir_dp``
     - Total reservoir pressure :math:`\Delta P_{res}` (Pa)

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    \Delta P_{flow} = \frac{Q\,\mu\,\ln(r_e/r_w)}{2\pi\,k\,h}
    \qquad
    \Delta P_{skin} = \frac{Q\,\mu\,S}{2\pi\,k\,h}
    \qquad
    \Delta P_{HH} = z_{top}\,\rho\,g

.. math::

    \Delta P_{res} = P_{res} + \Delta P_{flow} + \Delta P_{skin}

Reference: Akin (2019), *Geothermal re-injection performance evaluation
using surveillance analysis methods*, Renewable Energy.
