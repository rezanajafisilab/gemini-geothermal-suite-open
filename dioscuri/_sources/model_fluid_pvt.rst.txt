Fluid: PVT Properties
==============================

Description
---------------------------

The ``gemini_model.fluid.pvt_water_stp.PVTConstantSTP`` model provides
representative water/CO2-brine PVT (pressure-volume-temperature) properties
used by other models (well hydraulics, corrosion, erosion) that need fluid
density, viscosity, heat capacity, or surface tension.

The current implementation returns **constant properties**, valid near
standard conditions (STP), rather than a full equation-of-state calculation.
It exposes valid pressure/temperature ranges so calling models can flag
extrapolation.

Parameters
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Parameter
     - Description
   * - ``pressure_min`` / ``pressure_max``
     - Valid pressure range (Pa)
   * - ``temperature_min`` / ``temperature_max``
     - Valid temperature range (K)
   * - ``RHOG`` / ``RHOL``
     - Gas / liquid density (kg/m³)
   * - ``GMF``
     - Gas mass fraction (-)
   * - ``VISG`` / ``VISL``
     - Gas / liquid viscosity (Pa.s)
   * - ``CPG`` / ``CPL``
     - Gas / liquid heat capacity (J/kg.K)
   * - ``HG`` / ``HL``
     - Gas / liquid enthalpy (kJ/kg)
   * - ``TCG`` / ``TCL``
     - Gas / liquid thermal conductivity (W/m.K)
   * - ``SIGMA``
     - Surface tension (N/m)
   * - ``SG`` / ``SL``
     - Gas / liquid entropy (kJ/kg.K)

Outputs
---------------------------

Calling ``get_pvt(pressure, temperature)`` returns the tuple
``(rho_g, rho_l, gmf, eta_g, eta_l, cp_g, cp_l, K_g, K_l, sigma)`` used
directly by the well hydraulics model (see :doc:`model_well_hydraulics`) to
compute mixture density, friction, and heat transfer.
