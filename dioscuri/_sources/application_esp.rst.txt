ESP Performance
===========================


Description
---------------------------

This application provides comprehensive monitoring, calibration, and failure prediction capabilities for Electric Submersible Pumps (ESP) in geothermal reservoirs.

ESPs are installed in production wells to provide additional lift when the reservoir pressure is not sufficient to bring the fluid to the surface. They increase pressure between the pump intake (inlet) and discharge (outlet).

The schematic below illustrates a typical pressure profile across a geothermal production well equipped with an ESP:

.. image:: images/application_esp_0.png
    :width: 40%
    :align: center

The application is organized into three tabs: **Monitoring**, **Calibration**,
and **Prediction**.


Monitoring Tab
---------------------------

The Monitoring tab provides real-time ESP performance visualization.

**ESP Pump Curve and Real-Time Data**

This section shows the ESP pump curve from the manufacturer, plotted as head versus flowrate. On top of this, real-time operating data is added to show actual pump performance.

The pump curve displays theoretical frequency lines (typically 30, 40, 50, and 60 Hz) as "Theoretical Frequency" in the legend. The real-time operational point is overlaid on the pump curve, allowing users to compare actual performance against expected behavior.

Because discharge pressure is often unavailable, pump head is estimated from:

* inlet pressure measured by a downhole sensor
* upper pressure difference (:math:`\Delta P^{1}`), calculated with VLP (see
  :doc:`application_production_well_performance`) from ESP top to wellhead

From these, we estimate the actual pressure increase provided by the pump. This gives us the real-time pump head, which is plotted with the flowrate on top of the manufacturer pump curve.

.. image:: images/application_esp_Mon_1.png
    :width: 100%

**Flow and Frequency Plot**

A time-series plot displays the measured flow rate and frequency over the selected date range. This helps users identify operational patterns and potential issues with pump performance.

.. image:: images/application_esp_Mon_2.png
    :width: 100%

**Note on Calibration**

If the measured operating point does not align with theoretical frequency lines,
the ESP model may require calibration.


Calibration Tab
---------------------------

The Calibration tab enables users to calibrate the ESP model by aligning calculated values with theoretical expectations.

**Calibration Process**

The calibration matches the linear fitting to the calculated pump head. The goal is to match the **calculated VLP head** to the **theoretical head** that comes from the pump curve.

By clicking "Run Calibration", the application performs a linear fit of the form :math:`ax+b` for a selected time period. The calibration coefficients :math:`a` and :math:`b` are displayed in the calibration window and can be saved in the Parameters Overview so the calibration is applied to future ESP performance evaluations.

**Comparison Plots**

This section compares real-time measurements with model-based values:

.. image:: images/application_esp_Calib_1.png
    :width: 100%

**Head Comparison**

This is the most critical plot, used in the calibration step. It includes:

- VLP Head: calculated using pressure drop from the top of the ESP to the wellhead (since no discharge sensor is available) and measured intake pressure.

- Theoretical Head: calculated from the manufacturer pump curve using current flow and frequency.

- Calibrated Head: VLP head adjusted using calibration coefficients (if applied) to better match the theoretical head.

.. image:: images/application_esp_Calib_2.png
    :width: 100%

If no calibration is applied, default values are used with :math:`a = 1` and :math:`b = 0`. This helps users to see the initial mismatch between measured and expected pump behavior.

**Outlet Pressure Comparison**

Since there is no discharge pressure sensor, it shows:

- VLP-based Outlet Pressure: calculated from the pressure drop above the ESP and wellhead pressure.

- Theoretical Outlet Pressure: calculated using the measured inlet pressure and theoretical pump head.

**Inlet Pressure Comparison**

This compares:

- Measured Inlet Pressure: from the ESP sensor at the pump intake.

- Calculated Inlet Pressure: calculated from IPR (using reservoir pressure and flowrate, as described in :doc:`application_production_well_performance`) and VLP (from reservoir to pump location, using bottomhole pressure and pressure drop in the lower stage of the ESP, :math:`\Delta P^{2}`).

These comparisons act as diagnostic tools to check consistency between measurements and expected values. Deviations in head, outlet, or inlet pressures may indicate uncalibrated models, measurement errors, or operational issues.

Prediction Tab
---------------------------

The Prediction tab provides ESP failure forecasting using a machine-learning
model trained on historical operating data.

**Prediction Modes**

The application supports two prediction modes:

- **Forward Prediction (Next 30 Days)**: Predicts failure probability for the next 30 days from a selected time point.

.. image:: images/application_esp_Pred_1.png
    :width: 100%
    
.. image:: images/application_esp_Pred_2.png
    :width: 100%

- **Historical Analysis (Full Period)**: Analyzes failure probability across the entire selected historical period.

.. image:: images/application_esp_Pred_3.png
    :width: 100%
    
.. image:: images/application_esp_Pred_4.png
    :width: 100%

**Failure Probability Plot**

The main prediction plot displays the failure probability over time with color-coded risk zones:

- **High Risk (Red)**: Probability > 0.7
- **Medium Risk (Orange)**: Probability between 0.3 and 0.7
- **Low Risk (Green)**: Probability < 0.3

For forward prediction mode, a vertical line indicates the current time point, with predictions shown for the future period.

**Features (Model Inputs)**

The application displays all sensor features used as inputs to the ML model in a consolidated plot with grouped subplots:

- **Pressures**: Wellhead pressure, Intake pressure (ESP), and Discharge pressure (ESP)
- **Temperatures**: ESP Motor temperature and Wellhead temperature
- **Vibration and Flow Rate**: Vibration and Brine flow rate

**Model Disclaimer**

The model was trained on limited examples from one well/ESP type. Interpret
predictions with caution, especially in unfamiliar operating envelopes.