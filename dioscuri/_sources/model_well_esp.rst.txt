Pump: Electrical Submersible Pump (ESP)
========================================

Description
---------------------------

The ``gemini_model.pump.esp.ESP`` model estimates the performance of an
Electrical Submersible Pump (ESP): the head it generates, the shaft power it
consumes, and its efficiency, as a function of flow rate and drive frequency.

ESPs are installed in production wells to provide additional lift when the
reservoir pressure is not sufficient to bring the fluid to the surface. The
model is a **static model**: given the current flow rate and frequency, it
returns the corresponding head/power/efficiency without needing any internal
state.

Reference: TNO 2022 R11363 *"Model-based monitoring of geothermal assets,
case study: electrical submersible pumps"*.

This model underpins the :doc:`application_esp` application.

Parameters
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``no_stages``
     - Number of pump stages (-)
   * - ``head_coeff``
     - 6 polynomial coefficients fitting head vs. flow (US units, bbl/d → ft)
   * - ``power_coeff``
     - 6 polynomial coefficients fitting power vs. flow (US units, bbl/d → bhp)
   * - ``pump_name``
     - *(optional)* pump model identifier, for reference only

Inputs
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pump_freq``
     - Drive frequency (Hz)
   * - ``pump_flow``
     - Flow rate through the pump (m³/s)

Outputs
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``pump_head``
     - Pump head (Pa)
   * - ``pump_power``
     - Shaft power (W)
   * - ``pump_eff``
     - Pump efficiency (%)

Correlations
---------------------------

The manufacturer performance curves are fitted (in US field units) as
6th-order polynomials in flow rate expressed in barrels per day. The input
flow rate is first converted from m³/s to bbl/d:

.. math::

    Q_{bbl/d} = Q\,\left(543439.650564\right)

The fitted polynomials are evaluated at :math:`Q_{bbl/d}`:

.. math::

    P_{head}(Q_{bbl/d}) = \sum_{i=0}^{5} a_i\,Q_{bbl/d}^{\,i}
    \qquad
    P_{power}(Q_{bbl/d}) = \sum_{i=0}^{5} b_i\,Q_{bbl/d}^{\,i}

where :math:`a_i` are the ``head_coeff`` and :math:`b_i` are the
``power_coeff``. Head and power scale with the drive frequency following the
pump affinity laws (head with :math:`n^2`, power with :math:`n^3`, where
:math:`n` is the frequency ratio to 60 Hz), and are converted to SI units:

.. math::

    H = N_{stages}\,\left(\frac{f}{60}\right)^2 P_{head}(Q_{bbl/d})
        \times 2988.30167 \quad \text{[Pa]}

.. math::

    P = N_{stages}\,\left(\frac{f}{60}\right)^3 P_{power}(Q_{bbl/d})
        \times 745.7 \quad \text{[W]}

Efficiency is derived from flow, head, and power using the standard
hydraulic power relation (with a unit-conversion factor and returned as a
percentage):

.. math::

    \eta = 100\,\frac{Q_{bbl/d}}{135773}\,\frac{H}{P}\,
        \frac{745.7}{2988.30167} \qquad \text{[\%]}

where :math:`\eta = 0` if :math:`P < 0.1` W to avoid division by
near-zero power.

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Symbol
     - Name
     - Description
   * - :math:`N_{stages}`
     - ``no_stages``
     - Number of pump stages (-)
   * - :math:`f`
     - ``pump_freq``
     - Drive frequency (input, Hz)
   * - :math:`Q`
     - ``pump_flow``
     - Flow rate through the pump (input, m³/s)
   * - :math:`H`
     - ``pump_head``
     - Pump head (output, Pa)
   * - :math:`P`
     - ``pump_power``
     - Shaft power (output, W)
   * - :math:`\eta`
     - ``pump_eff``
     - Pump efficiency (output, %)
