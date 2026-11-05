var e=`data: {"type": "RUN_STARTED", "timestamp": 1793187652089, "threadId": "h1", "runId": "9a9b4c4a23"}

data: {"type": "STEP_STARTED", "timestamp": 1793187652091, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652513, "stepName": "intake", "metadata": {"tokens": 929, "relevant": true, "intent": "design", "screened": false, "seconds": 0.422}}

data: {"type": "CUSTOM", "timestamp": 1793187652514, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 851, "output_tokens": 78, "seconds": 0.421, "load_seconds": 0.003, "prompt_seconds": 0.13, "output_seconds": 0.269, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793187652514, "stepName": "plan", "metadata": {"label": "Plan the study", "kind": "plan", "code": "plan(brief, options)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652514, "stepName": "plan", "metadata": {"decided_by": "rules", "reason": "The standard study: A1 uses the deep brine directly, A2 tests a cheaper shallow well with heat pumps, and A4 is the gas reference.", "alternatives": ["Deep doublet with absorption cascade", "Shallow doublet with heat pumps", "Gas boiler and electric chillers (reference)"], "codes": ["A1", "A2", "A4"], "not_modelled": ["A3: Doublet with aquifer storage (ATES model not built yet)"], "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793187652515, "stepName": "doublet", "metadata": {"label": "Solve the doublet", "kind": "tool", "code": "solve_doublet(depth_m=2500, 1500)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652515, "toolCallId": "5cdb73dc6e", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652515, "toolCallId": "5cdb73dc6e", "delta": "{\\"depth_m\\": 2500.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652515, "toolCallId": "5cdb73dc6e"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652515, "messageId": "5cdb73dc6e-result", "toolCallId": "5cdb73dc6e", "content": "{\\"cached\\": true, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 2500.0, \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652516, "toolCallId": "2b2b256cb7", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652516, "toolCallId": "2b2b256cb7", "delta": "{\\"depth_m\\": 1500.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652516, "toolCallId": "2b2b256cb7"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652516, "messageId": "2b2b256cb7-result", "toolCallId": "2b2b256cb7", "content": "{\\"cached\\": true, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 1500.0, \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 4.97}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652516, "stepName": "doublet", "metadata": {"calls": 2, "failed": 0, "seconds": 0.001}}

data: {"type": "STEP_STARTED", "timestamp": 1793187652516, "stepName": "simulate", "metadata": {"label": "Simulate the year", "kind": "tool", "code": "simulate_year(A1, A2, A4)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652517, "toolCallId": "39b7c9721b", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652517, "toolCallId": "39b7c9721b", "delta": "{\\"alternative\\": {\\"code\\": \\"A1\\", \\"name\\": \\"Deep doublet with absorption cascade\\", \\"depth_m\\": 2500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652517, "toolCallId": "39b7c9721b"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652517, "messageId": "39b7c9721b-result", "toolCallId": "39b7c9721b", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652517, "toolCallId": "613bbafe8a", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652517, "toolCallId": "613bbafe8a", "delta": "{\\"alternative\\": {\\"code\\": \\"A2\\", \\"name\\": \\"Shallow doublet with heat pumps\\", \\"depth_m\\": 1500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": false, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652517, "toolCallId": "613bbafe8a"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652517, "messageId": "613bbafe8a-result", "toolCallId": "613bbafe8a", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"hex_outlet_c\\": 55.2, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 43.16, \\"boiler\\": 18.59}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 6.89, \\"boiler_mw\\": 7.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6269.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 11.98, \\"brine_heat_gwh\\": 31.18, \\"brine_capacity_mw\\": 4.97}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652518, "toolCallId": "bee89dfb27", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652518, "toolCallId": "bee89dfb27", "delta": "{\\"alternative\\": {\\"code\\": \\"A4\\", \\"name\\": \\"Gas boiler and electric chillers (reference)\\", \\"depth_m\\": 0.0, \\"heat_pump\\": false, \\"boiler\\": true, \\"absorption\\": false, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652518, "toolCallId": "bee89dfb27"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652518, "messageId": "bee89dfb27-result", "toolCallId": "bee89dfb27", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 10.0, \\"wellhead_c\\": 10.0, \\"hex_outlet_c\\": 10.0, \\"reinjection_c\\": 10.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 61.76}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 14.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652518, "stepName": "simulate", "metadata": {"calls": 3, "failed": 0, "seconds": 0.002}}

data: {"type": "STEP_STARTED", "timestamp": 1793187652519, "stepName": "economics", "metadata": {"label": "Cost and CO₂", "kind": "tool", "code": "economics(A1, A2, A4)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652519, "toolCallId": "9fe3818cbb", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652519, "toolCallId": "9fe3818cbb", "delta": "{\\"alternative\\": \\"A1\\", \\"year\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652519, "toolCallId": "9fe3818cbb"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652519, "messageId": "9fe3818cbb-result", "toolCallId": "9fe3818cbb", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 41.0, \\"lcoc_eur_per_mwh\\": 58.0, \\"capex_meur\\": 25.1, \\"co2_saving_vs_gas\\": 0.822}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652519, "toolCallId": "a4dbfe9217", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652519, "toolCallId": "a4dbfe9217", "delta": "{\\"alternative\\": \\"A2\\", \\"year\\": {\\"alternative\\": \\"A2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"hex_outlet_c\\": 55.2, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 43.16, \\"boiler\\": 18.59}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 6.89, \\"boiler_mw\\": 7.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6269.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 11.98, \\"brine_heat_gwh\\": 31.18, \\"brine_capacity_mw\\": 4.97}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652519, "toolCallId": "a4dbfe9217"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652519, "messageId": "a4dbfe9217-result", "toolCallId": "a4dbfe9217", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A2\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 65.5, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 19.9, \\"co2_saving_vs_gas\\": 0.324}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793187652520, "toolCallId": "67c4d62caf", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793187652520, "toolCallId": "67c4d62caf", "delta": "{\\"alternative\\": \\"A4\\", \\"year\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 10.0, \\"wellhead_c\\": 10.0, \\"hex_outlet_c\\": 10.0, \\"reinjection_c\\": 10.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 61.76}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 14.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 0.0}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793187652520, "toolCallId": "67c4d62caf"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793187652520, "messageId": "67c4d62caf-result", "toolCallId": "67c4d62caf", "content": "{\\"cached\\": true, \\"result\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 63.9, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 3.8, \\"co2_saving_vs_gas\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652520, "stepName": "economics", "metadata": {"calls": 3, "failed": 0, "seconds": 0.002}}

data: {"type": "STEP_STARTED", "timestamp": 1793187652521, "stepName": "verify", "metadata": {"label": "Check the physics", "kind": "check", "code": "verify_design(A1, A2, A4)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652521, "stepName": "verify", "metadata": {"passed": 3, "total": 3, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793187652521, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793187652521, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793187652521, "messageId": "33e1e13bab", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793187652521, "messageId": "33e1e13bab", "delta": "A1 covers 100% of the heat and 100% of the cold at 41 €/MWh for heat and 58 €/MWh for cold, with 82.2% less CO₂ than gas. Summer cooling from the same brine keeps the doublet busy 18.1% longer. For comparison: A4 (gas reference) at 63.9 €/MWh, A2 at 65.5 €/MWh."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793187652521, "messageId": "33e1e13bab"}

data: {"type": "CUSTOM", "timestamp": 1793187652522, "name": "result", "value": {"alternative": "A1", "name": "Deep doublet with absorption cascade", "source": "mock", "verified": true, "checks": {"passed": 17, "total": 17}, "kpis": [{"id": "heat_coverage", "label": "Heat covered", "value": 100.0, "unit": "%"}, {"id": "cool_coverage", "label": "Cold covered", "value": 100.0, "unit": "%"}, {"id": "lcoh", "label": "Cost of heat", "value": 41.0, "unit": "€/MWh"}, {"id": "lcoc", "label": "Cost of cold", "value": 58.0, "unit": "€/MWh"}, {"id": "co2", "label": "CO₂ against gas", "value": -82, "unit": "%"}, {"id": "flh", "label": "Doublet in use", "value": 6080.0, "unit": "full-load hours"}], "heat_split_gwh": {"geo": 48.22, "hp": 12.02, "boiler": 1.52}, "cool_split_gwh": {"abs": 7.32, "chill": 6.36}, "sizes_mw": {"heat_exchanger": 8.09, "heat_pump": 4.1, "boiler": 2.0, "absorption": 2.0, "chillers": 2.5}, "temperatures_c": {"wellhead": 86.0, "heat_exchanger_out": 45.0, "reinjection": 30.0}, "demand_gwh": {"heat": 61.76, "cold": 13.67}}}

data: {"type": "CUSTOM", "timestamp": 1793187652522, "name": "checks", "value": [{"name": "Heat adds up", "passed": true, "detail": "61.8 GWh from the sources, 61.8 GWh delivered", "requirement": false}, {"name": "Cold adds up", "passed": true, "detail": "13.7 GWh from the sources, 13.7 GWh delivered", "requirement": false}, {"name": "No more heat than demand", "passed": true, "detail": "61.8 of 61.8 GWh", "requirement": false}, {"name": "No more cold than demand", "passed": true, "detail": "13.7 of 13.7 GWh", "requirement": false}, {"name": "Heat pump COP below the Carnot limit", "passed": true, "detail": "COP 3.6 < 8.6 at 30 °C in and 70 °C out", "requirement": false}, {"name": "Brine cools along its path", "passed": true, "detail": "86 → 45 → 30 °C", "requirement": false}, {"name": "Reinjection at or above 30 °C", "passed": true, "detail": "30 °C", "requirement": false}, {"name": "No temperature cross in the heat exchanger", "passed": true, "detail": "brine 86 → 45 °C, network 40 → 70 °C", "requirement": false}, {"name": "No unit gives more than its size allows", "passed": true, "detail": "heat exchanger: 48.2 of 70.9 GWh possible at 8.09 MW", "requirement": false}, {"name": "Heat pump heat = electricity × COP", "passed": true, "detail": "12.0 GWh vs 3.3 GWh × 3.6", "requirement": false}, {"name": "Brine gives no more heat than it carries", "passed": true, "detail": "67.2 of 96.8 GWh a year", "requirement": false}, {"name": "Heating supply above return", "passed": true, "detail": "70/40 °C", "requirement": false}, {"name": "Cooling return above supply", "passed": true, "detail": "6/12 °C", "requirement": false}, {"name": "Absorption chiller driven hot enough", "passed": true, "detail": "86 °C ≥ 80 °C", "requirement": false}, {"name": "Cost is finite", "passed": true, "detail": "41 EUR/MWh", "requirement": false}, {"name": "Heat coverage at least 95%", "passed": true, "detail": "100.0%", "requirement": true}, {"name": "Cold coverage at least 95%", "passed": true, "detail": "100.0%", "requirement": true}]}

data: {"type": "CUSTOM", "timestamp": 1793187652522, "name": "suggestions", "value": ["What if the reservoir is 10 °C colder?", "Compare a 3 km doublet with a 1.5 km doublet with heat pumps", "Explain the summer cascade"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793187652523, "threadId": "h1", "runId": "9a9b4c4a23", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 851, "outputTokens": 78, "totalTokens": 929}], "result": {"behaviour": "design", "asked": [], "answer": "A1 covers 100% of the heat and 100% of the cold at 41 €/MWh for heat and 58 €/MWh for cold, with 82.2% less CO₂ than gas. Summer cooling from the same brine keeps the doublet busy 18.1% longer. For comparison: A4 (gas reference) at 63.9 €/MWh, A2 at 65.5 €/MWh.", "ungrounded": [], "dropped": [], "verified": true, "reasoning": false, "decided_by": {"plan": "rules"}, "intent": "design", "language": "en", "screened": false, "plan": ["A1", "A2", "A4"], "heat_coverage": 1.0, "cool_coverage": 1.0, "lcoh": 41.0, "alternative": "A1", "seconds": 0.433, "llm_calls": 1, "calls": ["intake: qwen3:1.7b"], "prompt_tokens": 851, "output_tokens": 78, "load_seconds": 0.003, "prompt_seconds": 0.13, "output_seconds": 0.269, "tool_calls": 8, "cache_hits": 8, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v2"}}

`;export{e as default};