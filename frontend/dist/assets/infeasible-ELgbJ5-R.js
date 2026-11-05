var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182837480, "threadId": "u-design", "runId": "496eb7679e"}

data: {"type": "STEP_STARTED", "timestamp": 1793182837480, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837760, "stepName": "intake", "metadata": {"tokens": 626, "relevant": true, "intent": "design", "seconds": 0.28}}

data: {"type": "CUSTOM", "timestamp": 1793182837761, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 556, "output_tokens": 70, "seconds": 0.279, "load_seconds": 0.001, "prompt_seconds": 0.009, "output_seconds": 0.262, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837761, "stepName": "plan", "metadata": {"label": "Plan the study", "kind": "plan", "code": "plan(D1)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837761, "stepName": "plan", "metadata": {"alternatives": ["1 km doublet"], "not_modelled": [], "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837762, "stepName": "doublet", "metadata": {"label": "Solve the doublet", "kind": "tool", "code": "solve_doublet(depth_m=1000)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837762, "toolCallId": "a5382a8ea7", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837762, "toolCallId": "a5382a8ea7", "delta": "{\\"depth_m\\": 1000.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837762, "toolCallId": "a5382a8ea7"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837762, "messageId": "a5382a8ea7-result", "toolCallId": "a5382a8ea7", "content": "{\\"cached\\": false, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 1000.0, \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 1.93}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837762, "stepName": "doublet", "metadata": {"calls": 1, "failed": 0, "seconds": 0.001}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837763, "stepName": "simulate", "metadata": {"label": "Simulate the year", "kind": "tool", "code": "simulate_year(D1)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837764, "toolCallId": "302e347398", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837764, "toolCallId": "302e347398", "delta": "{\\"alternative\\": {\\"code\\": \\"D1\\", \\"name\\": \\"1 km doublet\\", \\"depth_m\\": 1000.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 1.0, \\"min_cool_coverage\\": 1.0, \\"excluded\\": [\\"boiler\\", \\"chiller\\", \\"heat_pump\\"], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837764, "toolCallId": "302e347398"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837764, "messageId": "302e347398-result", "toolCallId": "302e347398", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"D1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 39.8, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 0.0, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.0, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 1.93}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837765, "stepName": "simulate", "metadata": {"calls": 1, "failed": 0, "seconds": 0.002}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837765, "stepName": "economics", "metadata": {"label": "Cost and CO₂", "kind": "tool", "code": "economics(D1)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837765, "toolCallId": "6a618d355e", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837765, "toolCallId": "6a618d355e", "delta": "{\\"alternative\\": \\"D1\\", \\"year\\": {\\"alternative\\": \\"D1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 39.8, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 0.0, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.0, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 1.93}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837765, "toolCallId": "6a618d355e"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837765, "messageId": "6a618d355e-result", "toolCallId": "6a618d355e", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"D1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 9999.0, \\"lcoc_eur_per_mwh\\": null, \\"capex_meur\\": 9.2, \\"co2_saving_vs_gas\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837766, "stepName": "economics", "metadata": {"calls": 1, "failed": 0, "seconds": 0.001}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837766, "stepName": "verify", "metadata": {"label": "Check the physics", "kind": "check", "code": "verify_design(D1)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837767, "stepName": "verify", "metadata": {"passed": 1, "total": 1, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837767, "stepName": "options", "metadata": {"label": "Look for designs that would work", "kind": "tool", "code": "simulate_year(O1, O2, A1)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837769, "toolCallId": "e302f7fec4", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837769, "toolCallId": "e302f7fec4", "delta": "{\\"alternative\\": {\\"code\\": \\"O1\\", \\"name\\": \\"1 km doublet\\", \\"depth_m\\": 1000.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.0, \\"min_cool_coverage\\": 0.0, \\"excluded\\": [], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837769, "toolCallId": "e302f7fec4"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837769, "messageId": "e302f7fec4-result", "toolCallId": "e302f7fec4", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"O1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 20.37, \\"boiler\\": 41.38}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 2.68, \\"boiler_mw\\": 11.5, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 7609.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 5.65, \\"brine_heat_gwh\\": 14.72, \\"brine_capacity_mw\\": 1.93}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837769, "toolCallId": "de11b23869", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837769, "toolCallId": "de11b23869", "delta": "{\\"alternative\\": \\"O1\\", \\"year\\": {\\"alternative\\": \\"O1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 40.8, \\"wellhead_c\\": 39.8, \\"hex_outlet_c\\": 39.8, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 20.37, \\"boiler\\": 41.38}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 2.68, \\"boiler_mw\\": 11.5, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 7609.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 5.65, \\"brine_heat_gwh\\": 14.72, \\"brine_capacity_mw\\": 1.93}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837769, "toolCallId": "de11b23869"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837769, "messageId": "de11b23869-result", "toolCallId": "de11b23869", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"O1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 70.8, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 14.7, \\"co2_saving_vs_gas\\": 0.134}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837772, "toolCallId": "2ade00a207", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837772, "toolCallId": "2ade00a207", "delta": "{\\"alternative\\": {\\"code\\": \\"O2\\", \\"name\\": \\"1 km doublet\\", \\"depth_m\\": 2200.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.0, \\"min_cool_coverage\\": 0.0, \\"excluded\\": [\\"boiler\\", \\"chiller\\", \\"heat_pump\\"], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837772, "toolCallId": "2ade00a207"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837772, "messageId": "2ade00a207-result", "toolCallId": "2ade00a207", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"O2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 77.8, \\"wellhead_c\\": 76.8, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 45.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 40.38, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.6538, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 40.38, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 6.28, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 4370.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 40.38, \\"brine_capacity_mw\\": 9.24}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837772, "toolCallId": "be1d66d493", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837772, "toolCallId": "be1d66d493", "delta": "{\\"alternative\\": \\"O2\\", \\"year\\": {\\"alternative\\": \\"O2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 77.8, \\"wellhead_c\\": 76.8, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 45.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 40.38, \\"cool_delivered_gwh\\": 0.0, \\"heat_coverage\\": 0.6538, \\"cool_coverage\\": 0.0, \\"heat_split_gwh\\": {\\"geo\\": 40.38, \\"hp\\": 0.0, \\"boiler\\": 0.0}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 0.0}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 6.28, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 0.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 0.0, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 4370.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 40.38, \\"brine_capacity_mw\\": 9.24}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837772, "toolCallId": "be1d66d493"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837772, "messageId": "be1d66d493-result", "toolCallId": "be1d66d493", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"O2\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 41.3, \\"lcoc_eur_per_mwh\\": null, \\"capex_meur\\": 16.4, \\"co2_saving_vs_gas\\": 0.941}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837775, "toolCallId": "60c3f13061", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837775, "toolCallId": "60c3f13061", "delta": "{\\"alternative\\": {\\"code\\": \\"A1\\", \\"name\\": \\"Deep doublet with absorption cascade\\", \\"depth_m\\": 2500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.0, \\"min_cool_coverage\\": 0.0, \\"excluded\\": [], \\"doublet_depths_m\\": [1000.0], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837775, "toolCallId": "60c3f13061"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837775, "messageId": "60c3f13061-result", "toolCallId": "60c3f13061", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182837775, "toolCallId": "3186463cbd", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182837775, "toolCallId": "3186463cbd", "delta": "{\\"alternative\\": \\"A1\\", \\"year\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182837775, "toolCallId": "3186463cbd"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182837775, "messageId": "3186463cbd-result", "toolCallId": "3186463cbd", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 41.0, \\"lcoc_eur_per_mwh\\": 58.0, \\"capex_meur\\": 25.1, \\"co2_saving_vs_gas\\": 0.822}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837776, "stepName": "options", "metadata": {"options": 3, "seconds": 0.009}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837777, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837777, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182837777, "messageId": "87d768ef4b", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182837777, "messageId": "87d768ef4b", "delta": "No design meets 100% of the heat with no boilers, chillers or heat pumps. The 1 km doublet covers 0% of the heat, 61.8 GWh a year short. Its brine reaches only 39.8 °C at the wellhead, below the 70 °C the network needs. Options: The same 1 km doublet with heat pumps and a peak boiler: 100% of the heat at 70.8 €/MWh. A 2.2 km doublet under the same limits: 65.4% of the heat at 41.3 €/MWh. A1, the 2.5 km cascade with heat pump, boiler and absorption chiller: 100% of the heat at 41 €/MWh."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182837777, "messageId": "87d768ef4b"}

data: {"type": "CUSTOM", "timestamp": 1793182837778, "name": "result", "value": {"alternative": "D1", "name": "1 km doublet", "source": "mock", "verified": false, "checks": {"passed": 10, "total": 12}, "kpis": [{"id": "heat_coverage", "label": "Heat covered", "value": 0.0, "unit": "%"}, {"id": "cool_coverage", "label": "Cold covered", "value": 0.0, "unit": "%"}, {"id": "lcoh", "label": "Cost of heat", "value": 9999.0, "unit": "€/MWh"}, {"id": "lcoc", "label": "Cost of cold", "value": null, "unit": "€/MWh"}, {"id": "co2", "label": "CO₂ against gas", "value": 0, "unit": "%"}, {"id": "flh", "label": "Doublet in use", "value": 0.0, "unit": "full-load hours"}], "heat_split_gwh": {"geo": 0.0, "hp": 0.0, "boiler": 0.0}, "cool_split_gwh": {"abs": 0.0, "chill": 0.0}, "sizes_mw": {"heat_exchanger": 0.0, "heat_pump": 0.0, "boiler": 0.0, "absorption": 0.0, "chillers": 0.0}, "temperatures_c": {"wellhead": 39.8, "heat_exchanger_out": 39.8, "reinjection": 39.8}, "demand_gwh": {"heat": 61.76, "cold": 13.67}}}

data: {"type": "CUSTOM", "timestamp": 1793182837778, "name": "checks", "value": [{"name": "Heat adds up", "passed": true, "detail": "0.0 GWh from the sources, 0.0 GWh delivered", "requirement": false}, {"name": "Cold adds up", "passed": true, "detail": "0.0 GWh from the sources, 0.0 GWh delivered", "requirement": false}, {"name": "No more heat than demand", "passed": true, "detail": "0.0 of 61.8 GWh", "requirement": false}, {"name": "No more cold than demand", "passed": true, "detail": "0.0 of 13.7 GWh", "requirement": false}, {"name": "Brine cools along its path", "passed": true, "detail": "39.8 → 39.8 → 39.8 °C", "requirement": false}, {"name": "Reinjection at or above 30 °C", "passed": true, "detail": "39.8 °C", "requirement": false}, {"name": "No unit gives more than its size allows", "passed": true, "detail": "heat exchanger: 0.0 of 0.0 GWh possible at 0 MW", "requirement": false}, {"name": "Brine gives no more heat than it carries", "passed": true, "detail": "0.0 of 16.9 GWh a year", "requirement": false}, {"name": "Heating supply above return", "passed": true, "detail": "70/40 °C", "requirement": false}, {"name": "Cooling return above supply", "passed": true, "detail": "6/12 °C", "requirement": false}, {"name": "Heat coverage at least 100%", "passed": false, "detail": "0.0%", "requirement": true}, {"name": "Cold coverage at least 100%", "passed": false, "detail": "0.0%", "requirement": true}]}

data: {"type": "RUN_FINISHED", "timestamp": 1793182837779, "threadId": "u-design", "runId": "496eb7679e", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 556, "outputTokens": 70, "totalTokens": 626}], "result": {"behaviour": "report_infeasible", "asked": [], "answer": "No design meets 100% of the heat with no boilers, chillers or heat pumps. The 1 km doublet covers 0% of the heat, 61.8 GWh a year short. Its brine reaches only 39.8 °C at the wellhead, below the 70 °C the network needs. Options: The same 1 km doublet with heat pumps and a peak boiler: 100% of the heat at 70.8 €/MWh. A 2.2 km doublet under the same limits: 65.4% of the heat at 41.3 €/MWh. A1, the 2.5 km cascade with heat pump, boiler and absorption chiller: 100% of the heat at 41 €/MWh.", "ungrounded": [], "dropped": [], "verified": false, "intent": "design", "language": "en", "screened": false, "heat_coverage": 0.0, "cool_coverage": 0.0, "lcoh": 9999.0, "alternative": "D1", "seconds": 0.298, "llm_calls": 1, "prompt_tokens": 556, "output_tokens": 70, "load_seconds": 0.001, "prompt_seconds": 0.009, "output_seconds": 0.262, "tool_calls": 9, "cache_hits": 1, "tool_errors": 0, "left_out": [], "user_turns": 2, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};