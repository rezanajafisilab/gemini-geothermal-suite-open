Surface Equipment
==============================================

Description
---------------------------

The surface-equipment models describe the above-ground assets of a
geothermal doublet: separators, filters, heat exchangers, pumps,
gas-fired heat/power units, and the adder/splitter network junctions
used to merge or divide flows between them.
All models are **static models** (``gemini_model.model_abstract.StaticModel``):
outputs are computed directly from the current inputs, with no internal
state.

Each model exposes a common output pattern where relevant -- ``power_el``
(electrical power, W), ``power_th`` (thermal power, W), and ``emission``
(CO2 emissions, kg/s) -- so surface-equipment outputs can be aggregated
consistently across a project diagram, alongside the equipment-specific
pressure/temperature outputs.

Separator
---------------------------

``gemini_model.separator.separator.Separator`` estimates the pressure and
temperature drop across a surface separator vessel, using a linear
flow-dependent pressure resistance and a fixed temperature drop.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``flow_resistance``
     - Linear pressure-resistance coefficient :math:`R_1` (Pa/(m³/s))
   * - ``temperature_drop``
     - Fixed temperature drop across the vessel :math:`\Delta T` (K)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure``
     - Known inlet (or outlet) pressure :math:`P_{in}` (Pa)
   * - ``temperature``
     - Known inlet (or outlet) temperature :math:`T_{in}` (K)
   * - ``flow_rate``
     - Volumetric flow rate through the vessel :math:`Q` (m³/s)
   * - ``direction``
     - ``"forward"``/``"backward"``: whether the inlet or outlet state
       is the known input

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``pressure``
     - Computed outlet (or inlet) pressure :math:`P_{out}` (Pa)
   * - ``temperature``
     - Computed outlet (or inlet) temperature :math:`T_{out}` (K)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    P_{out} = P_{in} - Q \cdot R_1 \qquad T_{out} = T_{in} - \Delta T

Filter
---------------------------

``gemini_model.filter.filter.Filter`` behaves like the Separator, but its
flow resistance increases with flow rate to approximate fouling/clogging of
the filter element.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``base_resistance``
     - Baseline flow resistance at zero flow :math:`R_0` (Pa/(m³/s))
   * - ``fouling_coeff_a``
     - Fouling resistance asymptote :math:`a` (Pa/(m³/s))
   * - ``fouling_coeff_b``
     - Fouling growth rate coefficient :math:`b` (s/m³)
   * - ``temperature_drop``
     - Fixed temperature drop across the filter :math:`\Delta T` (K)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same as the Separator model above: ``pressure``, ``temperature``,
``flow_rate``, ``direction``.

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Same as the Separator model above: ``pressure``, ``temperature``.

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    R_1 = a \left(1 - e^{-bQ}\right) + R_0 \qquad
    P_{out} = P_{in} - Q \cdot R_1

Heat Exchanger
---------------------------

``gemini_model.heat_exchanger.heat_exchanger.HeatExchanger`` models a plate
heat exchanger: a linear pressure drop on the primary side, and outlet
temperatures on both sides computed with the NTU-effectiveness method for a
parallel- or counter-flow configuration.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``flow_resistance``
     - Primary-side pressure-drop coefficient (Pa/(m³/s))
   * - ``heat_transfer_coefficient``
     - Overall heat-transfer conductance :math:`UA` (W/K)
   * - ``flow_configuration``
     - ``"parallel"`` or ``"counter"`` flow arrangement
   * - ``fluid_density``, ``specific_heat``
     - *(optional)* fluid properties :math:`\rho`, :math:`c_p`, default to
       water at STP

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure_in``
     - Primary-side inlet pressure :math:`P_{in}` (Pa)
   * - ``primary_temperature_in``
     - Primary-side inlet temperature :math:`T_{p,in}` (K)
   * - ``secondary_temperature_in``
     - Secondary-side inlet temperature :math:`T_{s,in}` (K)
   * - ``primary_flow_rate``
     - Primary-side volumetric flow rate :math:`\dot{V}_p` (m³/s)
   * - ``secondary_flow_rate``
     - Secondary-side volumetric flow rate :math:`\dot{V}_s` (m³/s)
   * - ``secondary_valve_position``
     - Fraction (0-1) of secondary flow routed through the exchanger

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``pressure_out``
     - Primary-side outlet pressure (Pa)
   * - ``primary_temperature_out``
     - Primary-side outlet temperature :math:`T_{p,out}` (K)
   * - ``secondary_temperature_out``
     - Secondary-side outlet temperature :math:`T_{s,out}` (K)
   * - ``heat_duty`` / ``power_th``
     - Heat transferred between the two sides (W)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Primary-side pressure drop:

.. math::

    P_{out} = P_{in} - \dot{V}_p \cdot R_1

Heat capacity rates on the primary and (valve-throttled) secondary side:

.. math::

    C_p = \dot{V}_p \rho c_p \qquad
    C_s = v \cdot \dot{V}_s \rho c_p \qquad
    C_{min} = \min(C_p, C_s) \qquad C_{max} = \max(C_p, C_s)

Number of transfer units, capacity ratio, and maximum possible heat duty:

.. math::

    NTU = \frac{UA}{C_{min}} \qquad C_r = \frac{C_{min}}{C_{max}} \qquad
    \dot{Q}_{max} = C_{min} \left|T_{s,in} - T_{p,in}\right|

Outlet temperatures and heat duty, once the effectiveness :math:`\varepsilon`
is known (see Correlations below):

.. math::

    \dot{Q} = \varepsilon \, \dot{Q}_{max} \qquad
    T_{p,out} = T_{p,in} - \frac{\dot{Q}}{C_p} \qquad
    T_{s,out} = T_{s,in} + \frac{\dot{Q}}{C_s}

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Effectiveness-NTU correlations (Kays & London), selected by
``flow_configuration``.

Parallel-flow:

.. math::

    \varepsilon = \frac{1 - e^{-NTU(1+C_r)}}{1+C_r}

Counter-flow:

.. math::

    \varepsilon = \begin{cases}
        \dfrac{NTU}{1+NTU} & C_r = 1 \\[6pt]
        1 - e^{-NTU} & C_r < 0.01 \\[6pt]
        \dfrac{1 - e^{-NTU(1+C_r)}}{1 - C_r e^{-NTU(1+C_r)}} & \text{otherwise}
    \end{cases}

Booster Pump
---------------------------

``gemini_model.booster_pump.booster_pump.BoosterPump`` estimates the
pressure change and temperature drop across a surface booster pump using a
linear flow-dependent characteristic curve, in either flow direction.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``flow_resistance``
     - Linear pressure-resistance coefficient :math:`R_1` (Pa/(m³/s))
   * - ``temperature_drop``
     - Fixed temperature drop across the pump :math:`\Delta T` (K)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure``
     - Known inlet (or outlet) pressure :math:`P_{in}` (Pa)
   * - ``temperature``
     - Known inlet (or outlet) temperature :math:`T_{in}` (K)
   * - ``flow_rate``
     - Volumetric flow rate through the pump :math:`Q` (m³/s)
   * - ``direction``
     - ``"forward"``/``"backward"``: whether the inlet or outlet state
       is the known input

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``pressure``
     - Computed outlet (or inlet) pressure :math:`P_{out}` (Pa)
   * - ``temperature``
     - Computed outlet (or inlet) temperature :math:`T_{out}` (K)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    P_{out} = P_{in} - Q \cdot R_1 \qquad T_{out} = T_{in} - \Delta T

Injector Pump
---------------------------

``gemini_model.injector_pump.injector_pump.InjectorPump`` computes the
electrical power and CO2 emissions of an injection pump boosting flow from
an inlet to a (higher) outlet pressure.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``efficiency_factor``
     - Pump efficiency :math:`\eta`, 0-1 (-)
   * - ``electricity_emission_factor``
     - Grid-electricity CO2 emission factor :math:`f_{emission}` (kg CO2/kWh)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``pressure_in``
     - Inlet pressure :math:`P_{in}` (Pa)
   * - ``pressure_out``
     - Outlet pressure :math:`P_{out}` (Pa)
   * - ``flow_rate``
     - Volumetric flow rate :math:`Q` (m³/s)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``power_el``
     - Electrical power consumed :math:`P_{el}` (W)
   * - ``emission``
     - CO2 emission rate :math:`\dot{m}_{CO2}` (kg/s)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    P_{el} = \frac{Q \cdot \max(0,\, P_{out} - P_{in})}{\eta} \qquad
    \dot{m}_{CO2} = \frac{f_{emission}}{3.6 \times 10^6} \cdot P_{el}

Boiler
---------------------------

``gemini_model.boiler.boiler.Boiler`` computes the heat output and CO2
emissions of a gas-fired boiler burning a mixture of gas co-produced with
the doublet's flow and gas supplied from the grid. The fraction :math:`u`
of available gas the boiler burns is set by ``burner_modulation``; the
remainder can supply a co-located CHP unit (see below).

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``gas_water_ratio``
     - Co-produced gas-to-water volume ratio :math:`r_{gw}` (-)
   * - ``efficiency_factor``
     - Boiler thermal efficiency :math:`\eta` (-)
   * - ``caloric_value``
     - Higher heating value of the gas :math:`HHV` (J/Nm³)
   * - ``gas_emission_factor``
     - CO2 emission factor of the gas (kg CO2/GJ)
   * - ``gas_density``, ``fluid_density``, ``specific_heat``
     - *(optional)* fluid/gas properties :math:`\rho_{gas}`, :math:`\rho`,
       :math:`c_p`

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``temperature_in``
     - Inlet fluid temperature :math:`T_{in}` (K)
   * - ``primary_flow_rate``
     - Primary volumetric flow rate :math:`Q_p` (m³/s)
   * - ``secondary_flow_rate``
     - Secondary volumetric flow rate :math:`Q_s` (m³/s)
   * - ``burner_modulation``
     - Fraction (0-1) of available gas burned :math:`u`
   * - ``secondary_valve_position``
     - Fraction (0-1) of secondary flow routed through the boiler
   * - ``grid_gas_flow_rate``
     - Supplementary grid gas flow rate :math:`Q_{grid}` (m³/s)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``power_th``
     - Heat output of the boiler :math:`P_{th}` (W)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    \dot{Q}_{gas} = \left(r_{gw} \cdot Q_p + Q_{grid}\right) \cdot \rho_{gas}
    \qquad
    P_{th} = \eta \cdot HHV \cdot u \cdot \dot{Q}_{gas}

Combined Heat and Power (CHP)
---------------------------------

``gemini_model.chp.chp.CHP`` shares the Boiler's fuel/flow accounting, but
burns the complementary gas fraction (:math:`1-u`) and secondary flow
fraction (:math:`1-v`), splitting the resulting fuel power into a fixed 1/3
electrical and 2/3 thermal share. Parameters and inputs mirror the Boiler
model above; a Boiler and a CHP unit are typically operated together on the
same gas and secondary-flow streams, using complementary
``burner_modulation``/``secondary_valve_position`` fractions.

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``power_el``
     - Electrical power generated, 1/3 of fuel power :math:`P_{el}` (W)
   * - ``power_th``
     - Heat output, 2/3 of fuel power :math:`P_{th}` (W)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    P_{fuel} = \eta \cdot HHV \cdot (1-u) \cdot \dot{Q}_{gas} \qquad
    P_{el} = \tfrac{1}{3} P_{fuel} \qquad P_{th} = \tfrac{2}{3} P_{fuel}

Compressor
---------------------------

``gemini_model.compressor.compressor.Compressor`` estimates the shaft power
of a multi-stage gas compressor, assuming ideal intercooling (gas cooled
back to inlet temperature between stages) and an equal pressure ratio per
stage.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``specific_heat_ratio``
     - Gas specific heat ratio, cp/cv :math:`k` (-)
   * - ``inlet_temperature``
     - Compressor inlet temperature :math:`T_1` (K)
   * - ``inlet_pressure``
     - Inlet pressure :math:`P_1` (Pa)
   * - ``outlet_pressure``
     - Outlet pressure :math:`P_2` (Pa)
   * - ``gas_constant``
     - Specific gas constant :math:`R` (J/(kg.K))
   * - ``mechanical_efficiency``
     - Mechanical efficiency :math:`\eta_m` (-)
   * - ``compressor_efficiency``
     - Isentropic compressor efficiency :math:`\eta_c` (-)
   * - ``number_of_stages``
     - Number of compression stages :math:`n` (-)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``mass_flow``
     - Gas mass flow rate :math:`\dot{m}` (kg/s)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``compressor_power``
     - Total shaft power over all stages :math:`P_{shaft}` (W)
   * - ``mass_flow``
     - Gas mass flow rate (pass-through, kg/s)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    r = \left(\frac{P_2}{P_1}\right)^{1/n} \qquad
    P_{shaft} = \frac{n \, \dot{m} \, R \, T_1}{(k-1) \, \eta_m \, \eta_c}
    \left(r^{\frac{k-1}{k}} - 1\right)

Heat Pump
---------------------------

``gemini_model.heatpump.heatpump_basic.HeatpumpBasic`` computes the
coefficient of performance (COP), outlet temperatures, thermal production,
and electrical consumption of a heat pump, using either a Carnot-efficiency
or a Lorenz-efficiency model. It solves the thermodynamic efficiency
equation together with the sink/source energy balance, and re-solves with
the source outlet temperature clamped at its allowed minimum if the
unconstrained solution would drop below it.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``mode``
     - ``"carnot"`` or ``"lorenz"`` efficiency model
   * - ``eta_carnot``
     - Carnot efficiency factor :math:`\eta_{carnot}`, 0-1 (-)
   * - ``eta_lorenz``
     - Lorenz efficiency factor :math:`\eta_{lorenz}`, 0-1 (-)
   * - ``COP_0``
     - Initial guess for COP used by the solver (-)
   * - ``Cp_h``, ``Cp_s``
     - Specific heat of the sink (hot) and source fluids (J/(kg.K))
   * - ``rho_h``, ``rho_s``
     - Density of the sink (hot) and source fluids (kg/m³)
   * - ``Th_out_target``
     - Target sink (hot) side outlet temperature (°C)
   * - ``Ts_in_minimum``
     - Minimum allowed source side outlet temperature (°C)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``Th_in``
     - Sink (hot) side inlet temperature :math:`T_{h,in}` (°C)
   * - ``Ts_in``
     - Source side inlet temperature :math:`T_{s,in}` (°C)
   * - ``qh``
     - Sink (hot) side volumetric flow rate :math:`\dot{V}_h` (m³/h)
   * - ``qs``
     - Source side volumetric flow rate :math:`\dot{V}_s` (m³/h)

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``COP``
     - Coefficient of performance (-)
   * - ``Th_out``
     - Sink (hot) side outlet temperature :math:`T_{h,out}` (°C)
   * - ``Ts_out``
     - Source side outlet temperature :math:`T_{s,out}` (°C)
   * - ``Thermal_production``
     - Heat delivered on the sink side :math:`\dot{Q}_h` (W)
   * - ``electrical_consumption``
     - Electrical power drawn by the compressor :math:`P_{el}` (W)

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sink- and source-side heat duties, from the energy balance:

.. math::

    \dot{Q}_h = C_{p,h} \left(T_{h,out} - T_{h,in}\right) \dot{m}_h \qquad
    \dot{Q}_s = C_{p,s} \left(T_{s,in} - T_{s,out}\right) \dot{m}_s

The COP couples the efficiency equation (see Correlations below) with the
energy balance across the compressor:

.. math::

    COP = \frac{\dot{Q}_h}{\dot{Q}_h - \dot{Q}_s} \qquad
    P_{el} = \frac{\dot{Q}_h}{COP}

The model solves for :math:`(COP, T_{s,out})` at the target
:math:`T_{h,out}` by minimizing the residual of both equations
simultaneously. If the resulting :math:`T_{s,out}` falls below
``Ts_in_minimum``, it is instead solved for :math:`(COP, T_{h,out})` with
:math:`T_{s,out}` fixed at ``Ts_in_minimum``.

Correlations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Carnot-efficiency COP, using the sink and source temperatures directly as
constant condenser/evaporator temperatures (Carnot, 1824):

.. math::

    COP = \eta_{carnot} \cdot \frac{T_{h,out}}{T_{h,out} - T_{s,in}}

Lorenz-efficiency COP, using the logarithmic mean temperatures of the sink
and source glide, which extends the Carnot cycle to non-isothermal heat
exchange (Lorenz, 1894):

.. math::

    COP = \eta_{lorenz} \cdot \frac{\bar{T}_h}{\bar{T}_h - \bar{T}_s}
    \qquad
    \bar{T}_h = \frac{T_{h,in} - T_{h,out}}{\ln\left(T_{h,in}/T_{h,out}\right)}
    \qquad
    \bar{T}_s = \frac{T_{s,in} - T_{s,out}}{\ln\left(T_{s,in}/T_{s,out}\right)}

Adder
---------------------------

``gemini_model.adder.adder.Adder`` sums an arbitrary number of numbered
inputs into a single output, representing a physical merge point such as
several production wells joining a shared header. It applies to any
extensive (conserved) quantity -- e.g. flow rate, mass flow, or power --
where the combined total is simply the sum of its parts; it is not
applicable to intensive quantities such as temperature or pressure, which
do not add linearly.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``num_inputs``
     - Number of numbered inputs to sum, :math:`N` (-)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``input_0`` .. ``input_{N-1}``
     - The :math:`N` numbered input values to sum :math:`x_0, ..., x_{N-1}`

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``output``
     - Sum of all :math:`N` inputs :math:`y`

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    y = \sum_{i=0}^{N-1} x_i

Splitter
---------------------------

``gemini_model.splitter.splitter.Splitter`` splits a single input into an
arbitrary number of numbered outputs by fixed fractions, representing a
physical split point such as a control valve dividing secondary flow
between a Boiler and a CHP. As with the Adder, it applies to extensive
(conserved) quantities such as flow rate, mass flow, or power; a split
quantity's temperature or pressure is unaffected by the split and is not
computed by this model.

Parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Parameter
     - Description
   * - ``split_fractions``
     - List of :math:`N` fractions :math:`f_0, ..., f_{N-1}`, summing to 1
       (-)

Inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Input
     - Description
   * - ``input``
     - The value to split :math:`x`

Outputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Output
     - Description
   * - ``output_0`` .. ``output_{N-1}``
     - The :math:`N` split output values :math:`y_0, ..., y_{N-1}`

Equations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. math::

    y_i = f_i \cdot x \qquad \text{for } i = 0, ..., N-1
