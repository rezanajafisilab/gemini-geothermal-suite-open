var e=`data: {"type": "RUN_STARTED", "timestamp": 1793185756680, "threadId": "v-rdesign", "runId": "f8a6fa2948"}

data: {"type": "STEP_STARTED", "timestamp": 1793185756681, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185757040, "stepName": "intake", "metadata": {"tokens": 893, "relevant": true, "intent": "design", "screened": false, "seconds": 0.359}}

data: {"type": "CUSTOM", "timestamp": 1793185757041, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 818, "output_tokens": 75, "seconds": 0.359, "load_seconds": 0.006, "prompt_seconds": 0.049, "output_seconds": 0.293, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793185757041, "stepName": "plan", "metadata": {"label": "Plan the study", "kind": "model", "code": "plan(brief, options)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185757041, "stepName": "plan", "metadata": {"decided_by": "rules", "reason": "You named the doublet depths, so I simulate those.", "alternatives": ["1 km doublet"], "not_modelled": [], "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793185757041, "stepName": "doublet", "metadata": {"label": "Solve the doublet", "kind": "tool", "code": "solve_doublet(depth_m=1000)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185757042, "toolCallId": "285f9fb1f3", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185757042, "toolCallId": "285f9fb1f3", "delta": "{\\"depth_m\\": 1000.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185757042, "toolCallId": "285f9fb1f3"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185757042, "messageId": "285f9fb1f3-result", "toolCallId": "285f9fb1f3", "content": "{\\"cached\\": true, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 1000.0, \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 1.93}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793185757042, "stepName": "doublet", "metadata": {"calls": 1, "failed": 0, "seconds": 0.001}}

data: {"type": "STEP_STARTED", "timestamp": 1793185757043, "stepName": "simulate", "metadata": {"label": "Simulate the year", "kind": "tool", "code": "simulate_year(D1)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185757043, "toolCallId": "66a165943a", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185757043, "toolCallId": "66a165943a", "delta": "{\\"alternative\\": {\\"code\\": \\"D1\\", \\"name\\": \\"1 km doublet\\", \\"depth_m\\": 1000.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 1.0, \\"min_cool_coverage\\": 1.0, \\"excluded\\": [\\"boiler\\", \\"chiller\\", \\"heat_pump\\"], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185757043, "toolCallId": "66a165943a"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185757043, "messageId": "66a165943a-result", "toolCallId": "66a165943a", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"D1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 39.8, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 0.0, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.0, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 1.93}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793185757044, "stepName": "simulate", "metadata": {"calls": 1, "failed": 0, "seconds": 0.001}}

data: {"type": "STEP_STARTED", "timestamp": 1793185757044, "stepName": "economics", "metadata": {"label": "Cost and CO₂", "kind": "tool", "code": "economics(D1)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185757044, "toolCallId": "600e4d96b4", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185757044, "toolCallId": "600e4d96b4", "delta": "{\\"alternative\\": \\"D1\\", \\"year\\": {\\"alternative\\": \\"D1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 39.8, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 0.0, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.0, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 1.93}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185757044, "toolCallId": "600e4d96b4"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185757044, "messageId": "600e4d96b4-result", "toolCallId": "600e4d96b4", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"D1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 9999.0, \\"lcoc_eur_per_mwh\\": null, \\"capex_meur\\": 9.2, \\"co2_saving_vs_gas\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793185757044, "stepName": "economics", "metadata": {"calls": 1, "failed": 0, "seconds": 0.001}}

data: {"type": "STEP_STARTED", "timestamp": 1793185757045, "stepName": "verify", "metadata": {"label": "Check the physics", "kind": "check", "code": "verify_design(D1)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185757045, "stepName": "verify", "metadata": {"passed": 1, "total": 1, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793185757045, "stepName": "reflect", "metadata": {"label": "Choose fixes to try", "kind": "model", "code": "reflect(shortfall, fixes)"}}

data: {"type": "CUSTOM", "timestamp": 1793185758866, "name": "usage", "value": {"purpose": "reflect", "model": "qwen3.5:9b", "prompt_tokens": 268, "output_tokens": 127, "seconds": 1.82, "load_seconds": 0.001, "prompt_seconds": 0.158, "output_seconds": 1.546, "ok": true, "error": ""}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185758867, "stepName": "reflect", "metadata": {"decided_by": "model", "reason": "The deeper option provides a more robust thermal solution by increasing brine temperature closer to the network requirement without relying solely on auxiliary equipment.", "steps": ["Current design fails due to insufficient depth (0% coverage) and low brine temperature (39.8°C vs 70°C needed).", "Increasing depth to 2.2km ('deeper') directly addresses the temperature deficit while respecting existing limits.", "Adding heat pumps ('allow') compensates for low inlet temperature but requires external energy input."], "try": ["deeper", "allow"], "seconds": 1.822}}

data: {"type": "STEP_STARTED", "timestamp": 1793185758868, "stepName": "options", "metadata": {"label": "Simulate the fixes", "kind": "tool", "code": "simulate_year(O1, O2)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185758868, "toolCallId": "beab10def6", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185758868, "toolCallId": "beab10def6", "delta": "{\\"alternative\\": {\\"code\\": \\"O1\\", \\"name\\": \\"1 km doublet\\", \\"depth_m\\": 1000.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.0, \\"min_cool_coverage\\": 0.0, \\"excluded\\": [], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185758868, "toolCallId": "beab10def6"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185758868, "messageId": "beab10def6-result", "toolCallId": "beab10def6", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"O1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 20.37, \\"boiler\\": 41.38}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 2.68, \\"boiler_mw\\": 11.5, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 7609.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 5.65, \\"brine_heat_gwh\\": 14.72, \\"brine_capacity_mw\\": 1.93}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185758869, "toolCallId": "13725f1753", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185758869, "toolCallId": "13725f1753", "delta": "{\\"alternative\\": \\"O1\\", \\"year\\": {\\"alternative\\": \\"O1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 20.37, \\"boiler\\": 41.38}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 2.68, \\"boiler_mw\\": 11.5, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 7609.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 5.65, \\"brine_heat_gwh\\": 14.72, \\"brine_capacity_mw\\": 1.93}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185758869, "toolCallId": "13725f1753"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185758869, "messageId": "13725f1753-result", "toolCallId": "13725f1753", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"O1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 70.8, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 14.7, \\"co2_saving_vs_gas\\": 0.134}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185758870, "toolCallId": "43a589c5a3", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185758870, "toolCallId": "43a589c5a3", "delta": "{\\"alternative\\": {\\"code\\": \\"O2\\", \\"name\\": \\"1 km doublet\\", \\"depth_m\\": 2200.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.0, \\"min_cool_coverage\\": 0.0, \\"excluded\\": [\\"boiler\\", \\"chiller\\", \\"heat_pump\\"], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185758870, "toolCallId": "43a589c5a3"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185758870, "messageId": "43a589c5a3-result", "toolCallId": "43a589c5a3", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"O2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 77.8, \\"wellhead_c\\": 76.8, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 45.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 40.38, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.6538, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 40.38, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 6.28, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 4370.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 40.38, \\"brine_capacity_mw\\": 9.24}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793185758871, "toolCallId": "5163915ea9", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793185758871, "toolCallId": "5163915ea9", "delta": "{\\"alternative\\": \\"O2\\", \\"year\\": {\\"alternative\\": \\"O2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 77.8, \\"wellhead_c\\": 76.8, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 45.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 40.38, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.6538, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 40.38, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 6.28, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 4370.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 40.38, \\"brine_capacity_mw\\": 9.24}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793185758871, "toolCallId": "5163915ea9"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793185758871, "messageId": "5163915ea9-result", "toolCallId": "5163915ea9", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"O2\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 41.3, \\"lcoc_eur_per_mwh\\": null, \\"capex_meur\\": 16.4, \\"co2_saving_vs_gas\\": 0.941}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793185758871, "stepName": "options", "metadata": {"options": 2, "seconds": 0.004}}

data: {"type": "STEP_STARTED", "timestamp": 1793185758872, "stepName": "write", "metadata": {"label": "Write the answer", "kind": "model", "code": "write(draft, facts)"}}

data: {"type": "CUSTOM", "timestamp": 1793185761993, "name": "usage", "value": {"purpose": "write", "model": "qwen3.5:9b", "prompt_tokens": 419, "output_tokens": 247, "seconds": 3.121, "load_seconds": 0.002, "prompt_seconds": 0.123, "output_seconds": 2.891, "ok": true, "error": ""}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185761994, "stepName": "write", "metadata": {"decided_by": "model", "reason": "Rewrote the answer from the facts.", "steps": ["User asks for 100% heating/cooling with one 1 km doublet and no heat pumps or boilers.", "Facts show the doublet covers 0% of heat, is short 61.8 GWh, and brine reaches only 39.8 °C.", "Draft states no design meets 100% without boilers/chillers/pumps; a 2.2 km doublet covers 65.4% at 41.3 €/MWh."], "seconds": 3.122}}

data: {"type": "STEP_STARTED", "timestamp": 1793185761995, "stepName": "report", "metadata": {"label": "Check the answer's numbers", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185761995, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793185761995, "messageId": "b19a4f3c95", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793185761995, "messageId": "b19a4f3c95", "delta": "No single 1 km doublet can cover 100% of heating and cooling without heat pumps, boilers, or chillers. The brine reaches only 39.8 °C at the wellhead, below the required 70 °C. This design covers 0% of the heat demand and is short by 61.8 GWh a year. A 2.2 km doublet under the same limits covers 65.4% of the heat at 41.3 €/MWh, while adding heat pumps and a peak boiler achieves 100% coverage at 70.8 €/MWh."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793185761995, "messageId": "b19a4f3c95"}

data: {"type": "CUSTOM", "timestamp": 1793185761996, "name": "result", "value": {"alternative": "D1", "name": "1 km doublet", "source": "mock", "verified": false, "checks": {"passed": 10, "total": 12}, "kpis": [{"id": "heat_coverage", "label": "Heat covered", "value": 0.0, "unit": "%"}, {"id": "cool_coverage", "label": "Cold covered", "value": 0.0, "unit": "%"}, {"id": "lcoh", "label": "Cost of heat", "value": 9999.0, "unit": "€/MWh"}, {"id": "lcoc", "label": "Cost of cold", "value": null, "unit": "€/MWh"}, {"id": "co2", "label": "CO₂ against gas", "value": 0, "unit": "%"}, {"id": "flh", "label": "Doublet in use", "value": 0.0, "unit": "full-load hours"}], "heat_split_gwh": {"geo": 0.0, "hp": 0.0, "boiler": 0.0}, "cool_split_gwh": {"abs": 0.0, "chill": 0.0}, "sizes_mw": {"heat_exchanger": 0.0, "heat_pump": 0.0, "boiler": 0.0, "absorption": 0.0, "chillers": 0.0}, "temperatures_c": {"wellhead": 39.8, "heat_exchanger_out": 39.8, "reinjection": 39.8}, "demand_gwh": {"heat": 61.76, "cold": 13.67}}}

data: {"type": "CUSTOM", "timestamp": 1793185761997, "name": "checks", "value": [{"name": "Heat adds up", "passed": true, "detail": "0.0 GWh from the sources, 0.0 GWh delivered", "requirement": false}, {"name": "Cold adds up", "passed": true, "detail": "0.0 GWh from the sources, 0.0 GWh delivered", "requirement": false}, {"name": "No more heat than demand", "passed": true, "detail": "0.0 of 61.8 GWh", "requirement": false}, {"name": "No more cold than demand", "passed": true, "detail": "0.0 of 13.7 GWh", "requirement": false}, {"name": "Brine cools along its path", "passed": true, "detail": "39.8 → 39.8 → 39.8 °C", "requirement": false}, {"name": "Reinjection at or above 30 °C", "passed": true, "detail": "39.8 °C", "requirement": false}, {"name": "No unit gives more than its size allows", "passed": true, "detail": "heat exchanger: 0.0 of 0.0 GWh possible at 0 MW", "requirement": false}, {"name": "Brine gives no more heat than it carries", "passed": true, "detail": "0.0 of 16.9 GWh a year", "requirement": false}, {"name": "Heating supply above return", "passed": true, "detail": "70/40 °C", "requirement": false}, {"name": "Cooling return above supply", "passed": true, "detail": "6/12 °C", "requirement": false}, {"name": "Heat coverage at least 100%", "passed": false, "detail": "0.0%", "requirement": true}, {"name": "Cold coverage at least 100%", "passed": false, "detail": "0.0%", "requirement": true}]}

data: {"type": "CUSTOM", "timestamp": 1793185761997, "name": "clarification", "value": {"kind": "decision", "intro": "How should I go on?", "questions": [{"id": "decision", "label": "How should I go on?", "hint": "I'll run the full checks on the option you pick.", "options": ["The same 1 km doublet with heat pumps and a peak boiler (100% of the heat at 70.8 €/MWh)", "A 2.2 km doublet under the same limits (65.4% of the heat at 41.3 €/MWh)", "Keep my limits and report the shortfall"], "default": "A 2.2 km doublet under the same limits (65.4% of the heat at 41.3 €/MWh)", "required": true}]}}

data: {"type": "RUN_FINISHED", "timestamp": 1793185761998, "threadId": "v-rdesign", "runId": "f8a6fa2948", "outcome": {"type": "interrupt", "interrupts": [{"id": "f8a6fa2948-ask", "reason": "decision"}]}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 818, "outputTokens": 75, "totalTokens": 893}, {"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 687, "outputTokens": 374, "totalTokens": 1061}], "result": {"behaviour": "report_infeasible", "asked": ["decision"], "answer": "No single 1 km doublet can cover 100% of heating and cooling without heat pumps, boilers, or chillers. The brine reaches only 39.8 °C at the wellhead, below the required 70 °C. This design covers 0% of the heat demand and is short by 61.8 GWh a year. A 2.2 km doublet under the same limits covers 65.4% of the heat at 41.3 €/MWh, while adding heat pumps and a peak boiler achieves 100% coverage at 70.8 €/MWh.", "ungrounded": [], "dropped": [], "verified": false, "reasoning": true, "decided_by": {"plan": "rules", "reflect": "model", "write": "model"}, "intent": "design", "language": "en", "screened": false, "plan": ["D1"], "draft": "No design meets 100% of the heat with no boilers, chillers or heat pumps. The 1 km doublet covers 0% of the heat, 61.8 GWh a year short. Its brine reaches only 39.8 °C at the wellhead, below the 70 °C the network needs. Options: The same 1 km doublet with heat pumps and a peak boiler: 100% of the heat at 70.8 €/MWh. A 2.2 km doublet under the same limits: 65.4% of the heat at 41.3 €/MWh.", "heat_coverage": 0.0, "cool_coverage": 0.0, "lcoh": 9999.0, "alternative": "D1", "recommended": "deeper", "seconds": 5.317, "llm_calls": 3, "calls": ["intake: qwen3:1.7b", "reflect: qwen3.5:9b", "write: qwen3.5:9b"], "prompt_tokens": 1505, "output_tokens": 449, "load_seconds": 0.009, "prompt_seconds": 0.33, "output_seconds": 4.73, "tool_calls": 7, "cache_hits": 7, "tool_errors": 0, "left_out": [], "user_turns": 2, "model": "qwen3:1.7b", "prompt_version": "intake_v2"}}

`;export{e as default};