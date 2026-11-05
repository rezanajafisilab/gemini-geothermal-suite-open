Well Integrity
===========================

Description
---------------------------
The Well Integrity Monitoring application (WIMS) provides monitoring and
forecasting tools for well integrity in geothermal wells. It combines
multi-finger caliper log processing (joint detection, QA/QC and per-joint
remaining-thickness statistics), a well-integrity **Dashboard** (schematic with
Well Barrier Envelope colouring, operational limits, history, maintenance
checklist, annulus monitoring and WBE tracking), a **Wall thickness forecast**
based on a calibrated CO2 corrosion model, and an **Erosion** analysis for the
production flow path.

Layout
---------------------------
Select a well from **Well Name** at the top of the page. The app is then
organised into three cards:

* **Dashboard** — schematic, operational limits, history, maintenance checklist, and the WIMS subcards (Overall Integrity status, Annulus monitoring, Well Barrier Envelope, WBE Risk).
* **Wall thickness forecast** — caliper log management (upload / detect joints / process) and the corrosion forecast (Optimize / Predict / Years to minimum thickness).
* **Erosion** — ESP geometry and erosion calculation for the production flow path.

Workflow (per Well Integrity Monitoring app)
---------------------------------------------
1. **Select well** — On opening the app, the plant is loaded. Choose **Well Name** from the dropdown to view WIMS for that well.

2. **Manage caliper logs** — In the **Wall thickness forecast** card, **Wall integrity logs** subcard (**Multi-Finger Caliper Logs**):

   * **Upload log** — Add a LAS caliper log (up to ``MAX_WELL_LOGS`` = 5 logs per well).
   * **Log info** — Click a log to open the **Log info** modal and set its metadata: date, baseline flag, finger units, joint identification marker, depth-corrected flag, finger name, and the max / min / average column names. A log cannot be processed until its required metadata is filled. Each log shows a status: *inputs required*, *unprocessed*, *detected*, or *processed*. Logs can be removed here.
   * **Detect Joints** — Run joint detection to propose joint-boundary candidates.
   * **QA/QC** — Open the **Joint Detection QA/QC** modal to review candidates against the depth chart and **Approve** the correct joints per log.
   * **Process Logs** — Run processing (uses the approved joints when available) to produce per-joint statistics.

        .. image:: images/application_wims_1.png
            :width: 100%
            :align: center

3. **Review processed logs** — Select one or more processed logs to chart. Pick a column to plot (per-joint statistic), and open **Finger Detail** to inspect per-finger measurements for a chosen joint.

4. **Well schematic** — Create the well schematic in the **Well Schematics** application and add a well tally in Well Parameters. The Dashboard schematic and WIMS subcards appear when the selected well has at least one saved schematic.

5. **Dashboard** — Select a **saved schematic** in the Dashboard header. Fill in operational limits, history, maintenance and the WIMS subcards (see `Dashboard`_). Click **Save dashboard** to persist the configuration.

        .. image:: images/application_wims_2.png
            :width: 100%
            :align: center

        .. image:: images/application_wims_4.png
            :width: 100%
            :align: center


6. **Forecast** — In the **Forecast** subcard, click **Optimize** to calibrate
   the corrosion model against processed logs, then choose a **Prediction**
   method (*Current wall thickness* or *Years to minimum thickness*) and click
   **Run** (see `Wall thickness forecast`_).

        .. image:: images/application_wims_6.png
            :width: 100%
            :align: center

7. **Erosion** — In the **Erosion** card, define the ESP geometry, choose a correlation and production window, and click **Run erosion** (see `Erosion`_).

Inputs
--------------------------------------
* **Caliper log** — LAS format (up to 2.0 supported). The file should have a ``DATE`` or ``PID`` mnemonic for the logging date. Finger channels should be named ``D01``, ``D02``, etc.

* **Per-log metadata** — Set in the **Log info** modal (stored in ``logs_information.json``): date, baseline flag (a single log per well can be the baseline), finger units (e.g. radius / double radius / diameter), joint identification marker (CCL, log markers, or tally), depth-corrected flag, finger name, and the max / min / average column names.

* **Well schematic** — Created in the Well Schematics application; select a saved schematic in the Dashboard.

* **Well tally** — Required for joint-based processing. Provide via Well Parameters (app builder). Format example:

    .. image:: images/application_wims_3.png
        :width: 100%
        :align: center

* **ESP geometry and production data** — Required for erosion (and for corrosion calibration/prediction, which use production flow, pressure and temperature over a time window). ESP geometry is edited/saved in the Erosion card.

Caliper log processing
--------------------------------------
Processing runs in three steps:

1. **Detect Joints** — Proposes joint-boundary candidates from the log using the configured *joint identification marker* (CCL collar peaks, log-curve markers, or the well tally as a fallback). Each candidate has a depth, kind, and score.

2. **QA/QC and Approve** — In the **Joint Detection QA/QC** modal, review the candidates against the depth chart and approve the correct joints. Approved joints are matched to the well tally.

3. **Process Logs** — For each well joint, computes:

   * Maximum, minimum and average radius [inch]
   * Maximum penetration [%] — ``100 x (max radius - nominal inner radius) / (nominal outer radius - nominal inner radius)``
   * Maximum wall loss [%] — circumferential loss averaged over the joint depth rows
   * Maximum penetration depth and minimum penetration depth [m]
   * Remaining wall thickness [inch] — ``nominal outer radius - maximum radius`` (one-sided, worst-case pit)

Log depths should be calibrated to the same depth reference prior to processing (set the *depth-corrected* flag in the Log info modal).

Dashboard
--------------------------------------
Select a saved schematic in the Dashboard header; the schematic image is shown
with Well Barrier Envelope colouring applied (primary elements blue, secondary
red, and failed elements highlighted yellow). Click **Save dashboard** to
persist all Dashboard state.

* **Operational Limits** — Table of Description, Casing, Min., Max. and Unit. Add via **Add limit** (description presets include minimum wall thickness, temperature, and annulus A/B/C pressure, plus a Custom option; casing-specific limits pick a casing from the tally).

* **History** — Dated event log. Add via **Add entry**; each entry can have a document attached (uploaded to the server and downloadable from the table).

* **Maintenance checklist** — Table of maintenance type, comments, interval, last maintenance date and a computed **Due status** (days remaining until the next due date, or days overdue). Add via **Add item**.

* **Overall Integrity status** — Overall status dot and a **Last update date**; legend: Failed (red), Not verified or other issues (amber), Verified and in good state (green).

* **Annulus monitoring** — Add monitors per annulus via **Add monitor** (choose the annulus from the schematic). Each monitor is a gauge: **Configure gauge** (select Tag, set Min and Max alert values) or **Delete monitor**. Tag values and recent time series are fetched from the application; when a value crosses an alert threshold an alarm is raised and can be acknowledged.

* **Well Barrier Envelope (WBE)** — Primary and Secondary barrier element tables. Each row: Element, Qualification, Monitoring, Status (Failed / Not verified / Verified), Remarks. Add elements from the schematic or as custom via **Add element**; click a row to edit or delete.

* **WBE Risk** — Table of Failure mode, Effect, Risk (Likelihood L, Effect E, Risk factor L x E), Action Plan, Response time (months) and Operate during failure. Add via **Add risk**; click a row to edit or delete.


Wall thickness forecast
--------------------------------------
The **Forecast** subcard uses a calibrated CO2 corrosion model rather than a
manual rate calculation.

* **Optimize** — Calibrates the corrosion model against the processed logs and production data, and persists the calibrated parameters (``corrosion_opt_params.json``). A "last optimized" note shows when calibration was last run. Optimization must be run before prediction.

* **Prediction method** — After optimization, choose a method and click **Run**:

  * **Current wall thickness** — Predicts the remaining wall thickness from the latest log up to now, using the calibrated model over the intervening production window. Result: predicted remaining wall thickness per joint.
  * **Years to minimum thickness (past-year production)** — Projects the calibrated model's trailing 12-month corrosion rate forward to estimate, per casing, the years until the casing reaches its minimum wall thickness (using the per-casing minimum thicknesses entered in the Dashboard). Reports the limiting joint and the worst joints per casing.

Erosion
--------------------------------------
The **Erosion** card estimates erosion along the production flow path from the
well tally, ESP geometry and production data.

* **ESP geometry** — Shows the ESP setting depth (from the plant) and the production casing ID (from the tally), and lets you set the production tubing ID [inch] and edit the geometry components (Type, Name, Length [m], OD [inch]). **Save ESP geometry** stores it per well.

* **Erosion calculation** — Choose a **Correlation** (DNVGL, OKA, API, or E/CRC Tulsa), a production **Start**/**End** date, the **Fluid density** [kg/m3] and a **Flow statistic** (Mean or Max), plus correlation-specific parameters (e.g. particle impact angle, hardness, particle/pipe material). Click **Run erosion**.

* **Results** — Per-segment flow velocity [m/s] and erosion rate [mm/year] (for DNVGL / OKA / E/CRC Tulsa), or an API velocity-limit comparison (erosional velocity limit, flow velocity, and whether it is exceeded). A summary aggregates the worst erosion rate per joint.


How the calculations work
--------------------------------------

Caliper processing method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
For each matched joint, finger-radius channels are sliced over the joint depth
interval and coupling spikes are excluded. From the cleaned radii, per joint:

* **Max / Min / Mean radius [inch]** — over the finger columns.
* **Max penetration [%]** — ``100 x (max radius - nominal inner radius) / (nominal outer radius - nominal inner radius)``, where nominal inner/outer radii are ``ID/2`` and ``OD/2`` from the matched tally row.
* **Max wall loss [%]** — circumferential wall loss averaged over the joint's depth rows.
* **Remaining wall thickness [inch]** — ``nominal outer radius - max radius`` (one-sided, deepest pit).

Corrosion forecast (calibrated model)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
* **Log-measured rate** — Between two dated logs (or from a baseline log), the wall-thickness change rate [mm/year] is derived from the change in **maximum inner radius** (worst pit) per joint over the elapsed time. The baseline is the log flagged as baseline, otherwise the earliest dated log. Remaining wall thickness at a log date is ``(OD/2 - max radius) x 25.4`` [mm].

* **Optimize (calibration)** — For each joint and log interval, the DLD CO2 corrosion model coefficients (A, B, C, D) are calibrated so the modelled rate matches the log-measured rate; the sign term (E) is derived from the measured trend. The modelled rate integrates the CO2 corrosion rate over the production window (flow, pressure, temperature per joint) between log dates.

* **Predict (current wall thickness)** — Starting from the latest processed log's maximum inner radius, the calibrated model is integrated over the production window from the latest log date to now, giving the predicted inner radius and remaining wall thickness [mm] per joint.

* **Years to minimum thickness** — The per-joint annual corrosion rate is taken from the calibrated model over the last 12 months of production; ``years to min = (remaining wall now [mm] - minimum wall [mm]) / rate [mm/year]``. Per casing, the soonest (limiting) joint sets the casing result.

Erosion method
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The production flow path is split into segments from the well tally and ESP
geometry (tubing interior, ESP-joint annulus, and tubing above the ESP). A
representative flow rate (mean or max of the production series) gives the flow
velocity ``v = (flow [m3/h] / 3600) / (pi x d^2 / 4)`` [m/s] per segment. The
selected correlation then gives, per segment, an erosion rate [mm/year] (DNVGL,
OKA, E/CRC Tulsa) or, for API, an erosional velocity limit [m/s] compared
against the flow velocity.
