var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182854068, "threadId": "u-tool", "runId": "ef406414e1"}

data: {"type": "STEP_STARTED", "timestamp": 1793182854068, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854356, "stepName": "intake", "metadata": {"tokens": 625, "relevant": true, "intent": "design", "seconds": 0.288}}

data: {"type": "CUSTOM", "timestamp": 1793182854356, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 560, "output_tokens": 65, "seconds": 0.287, "load_seconds": 0.002, "prompt_seconds": 0.012, "output_seconds": 0.261, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854356, "stepName": "plan", "metadata": {"label": "Plan the study", "kind": "plan", "code": "plan(A1, A2, A4)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854356, "stepName": "plan", "metadata": {"alternatives": ["Deep doublet with absorption cascade", "Shallow doublet with heat pumps", "Gas boiler and electric chillers (reference)"], "not_modelled": ["A3: Doublet with aquifer storage (ATES model not built yet)"], "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854356, "stepName": "doublet", "metadata": {"label": "Solve the doublet", "kind": "tool", "code": "solve_doublet(depth_m=2500, 1500)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854356, "toolCallId": "06a7bf2923", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854356, "toolCallId": "06a7bf2923", "delta": "{\\"depth_m\\": 2500.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854356, "toolCallId": "06a7bf2923"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854356, "messageId": "06a7bf2923-result", "toolCallId": "06a7bf2923", "content": "{\\"cached\\": false, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 2500.0, \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854356, "toolCallId": "c09c6d48b4", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854356, "toolCallId": "c09c6d48b4", "delta": "{\\"depth_m\\": 1500.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854356, "toolCallId": "c09c6d48b4"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854356, "messageId": "c09c6d48b4-result", "toolCallId": "c09c6d48b4", "content": "{\\"cached\\": false, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 1500.0, \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 4.97}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854356, "stepName": "doublet", "metadata": {"calls": 2, "failed": 0, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854356, "stepName": "simulate", "metadata": {"label": "Simulate the year", "kind": "tool", "code": "simulate_year(A1, A2, A4)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854358, "toolCallId": "4a6b62f6f9", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854358, "toolCallId": "4a6b62f6f9", "delta": "{\\"alternative\\": {\\"code\\": \\"A1\\", \\"name\\": \\"Deep doublet with absorption cascade\\", \\"depth_m\\": 2500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854358, "toolCallId": "4a6b62f6f9"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854358, "messageId": "4a6b62f6f9-result", "toolCallId": "4a6b62f6f9", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854358, "toolCallId": "433aa6b4cc", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854358, "toolCallId": "433aa6b4cc", "delta": "{\\"alternative\\": {\\"code\\": \\"A2\\", \\"name\\": \\"Shallow doublet with heat pumps\\", \\"depth_m\\": 1500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": false, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854358, "toolCallId": "433aa6b4cc"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854358, "messageId": "433aa6b4cc-result", "toolCallId": "433aa6b4cc", "content": "{\\"cached\\": false, \\"error\\": \\"depth 1500 m is outside the doublet model\\"}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854359, "toolCallId": "843281a570", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854359, "toolCallId": "843281a570", "delta": "{\\"alternative\\": {\\"code\\": \\"A4\\", \\"name\\": \\"Gas boiler and electric chillers (reference)\\", \\"depth_m\\": 0.0, \\"heat_pump\\": false, \\"boiler\\": true, \\"absorption\\": false, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854359, "toolCallId": "843281a570"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854359, "messageId": "843281a570-result", "toolCallId": "843281a570", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 10.0, \\"wellhead_c\\": 10.0, \\"hex_outlet_c\\": 10.0, \\"reinjection_c\\": 10.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 61.76}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 14.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854359, "stepName": "simulate", "metadata": {"calls": 3, "failed": 1, "seconds": 0.003}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854359, "stepName": "economics", "metadata": {"label": "Cost and CO₂", "kind": "tool", "code": "economics(A1, A4)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854359, "toolCallId": "95f93ff816", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854359, "toolCallId": "95f93ff816", "delta": "{\\"alternative\\": \\"A1\\", \\"year\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854359, "toolCallId": "95f93ff816"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854359, "messageId": "95f93ff816-result", "toolCallId": "95f93ff816", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 41.0, \\"lcoc_eur_per_mwh\\": 58.0, \\"capex_meur\\": 25.1, \\"co2_saving_vs_gas\\": 0.822}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854359, "toolCallId": "bc27bfeda8", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854359, "toolCallId": "bc27bfeda8", "delta": "{\\"alternative\\": \\"A4\\", \\"year\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 10.0, \\"wellhead_c\\": 10.0, \\"hex_outlet_c\\": 10.0, \\"reinjection_c\\": 10.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 61.76}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 14.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 0.0}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854359, "toolCallId": "bc27bfeda8"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854359, "messageId": "bc27bfeda8-result", "toolCallId": "bc27bfeda8", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 63.9, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 3.8, \\"co2_saving_vs_gas\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854359, "stepName": "economics", "metadata": {"calls": 2, "failed": 0, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854359, "stepName": "verify", "metadata": {"label": "Check the physics", "kind": "check", "code": "verify_design(A1, A4)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854359, "stepName": "verify", "metadata": {"passed": 2, "total": 2, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854360, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854360, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182854360, "messageId": "2f63351f60", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182854360, "messageId": "2f63351f60", "delta": "A1 covers 100% of the heat and 100% of the cold at 41 €/MWh for heat and 58 €/MWh for cold, with 82.2% less CO₂ than gas. Summer cooling from the same brine keeps the doublet busy 18.1% longer. For comparison: A4 (gas reference) at 63.9 €/MWh. Left out: A2 (simulate_year failed: depth 1500 m is outside the doublet model)."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182854360, "messageId": "2f63351f60"}

data: {"type": "CUSTOM", "timestamp": 1793182854360, "name": "result", "value": {"alternative": "A1", "name": "Deep doublet with absorption cascade", "source": "mock", "verified": true, "checks": {"passed": 17, "total": 17}, "kpis": [{"id": "heat_coverage", "label": "Heat covered", "value": 100.0, "unit": "%"}, {"id": "cool_coverage", "label": "Cold covered", "value": 100.0, "unit": "%"}, {"id": "lcoh", "label": "Cost of heat", "value": 41.0, "unit": "€/MWh"}, {"id": "lcoc", "label": "Cost of cold", "value": 58.0, "unit": "€/MWh"}, {"id": "co2", "label": "CO₂ against gas", "value": -82, "unit": "%"}, {"id": "flh", "label": "Doublet in use", "value": 6080.0, "unit": "full-load hours"}], "heat_split_gwh": {"geo": 48.22, "hp": 12.02, "boiler": 1.52}, "cool_split_gwh": {"abs": 7.32, "chill": 6.36}, "sizes_mw": {"heat_exchanger": 8.09, "heat_pump": 4.1, "boiler": 2.0, "absorption": 2.0, "chillers": 2.5}, "temperatures_c": {"wellhead": 86.0, "heat_exchanger_out": 45.0, "reinjection": 30.0}, "demand_gwh": {"heat": 61.76, "cold": 13.67}}}

data: {"type": "CUSTOM", "timestamp": 1793182854360, "name": "checks", "value": [{"name": "Heat adds up", "passed": true, "detail": "61.8 GWh from the sources, 61.8 GWh delivered", "requirement": false}, {"name": "Cold adds up", "passed": true, "detail": "13.7 GWh from the sources, 13.7 GWh delivered", "requirement": false}, {"name": "No more heat than demand", "passed": true, "detail": "61.8 of 61.8 GWh", "requirement": false}, {"name": "No more cold than demand", "passed": true, "detail": "13.7 of 13.7 GWh", "requirement": false}, {"name": "Heat pump COP below the Carnot limit", "passed": true, "detail": "COP 3.6 < 8.6 at 30 °C in and 70 °C out", "requirement": false}, {"name": "Brine cools along its path", "passed": true, "detail": "86 → 45 → 30 °C", "requirement": false}, {"name": "Reinjection at or above 30 °C", "passed": true, "detail": "30 °C", "requirement": false}, {"name": "No temperature cross in the heat exchanger", "passed": true, "detail": "brine 86 → 45 °C, network 40 → 70 °C", "requirement": false}, {"name": "No unit gives more than its size allows", "passed": true, "detail": "heat exchanger: 48.2 of 70.9 GWh possible at 8.09 MW", "requirement": false}, {"name": "Heat pump heat = electricity × COP", "passed": true, "detail": "12.0 GWh vs 3.3 GWh × 3.6", "requirement": false}, {"name": "Brine gives no more heat than it carries", "passed": true, "detail": "67.2 of 96.8 GWh a year", "requirement": false}, {"name": "Heating supply above return", "passed": true, "detail": "70/40 °C", "requirement": false}, {"name": "Cooling return above supply", "passed": true, "detail": "6/12 °C", "requirement": false}, {"name": "Absorption chiller driven hot enough", "passed": true, "detail": "86 °C ≥ 80 °C", "requirement": false}, {"name": "Cost is finite", "passed": true, "detail": "41 EUR/MWh", "requirement": false}, {"name": "Heat coverage at least 95%", "passed": true, "detail": "100.0%", "requirement": true}, {"name": "Cold coverage at least 95%", "passed": true, "detail": "100.0%", "requirement": true}]}

data: {"type": "CUSTOM", "timestamp": 1793182854360, "name": "suggestions", "value": ["What if the reservoir is 10 °C colder?", "Compare a 3 km doublet with a 1.5 km doublet with heat pumps", "Explain the summer cascade"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793182854360, "threadId": "u-tool", "runId": "ef406414e1", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 560, "outputTokens": 65, "totalTokens": 625}], "result": {"behaviour": "design", "asked": [], "answer": "A1 covers 100% of the heat and 100% of the cold at 41 €/MWh for heat and 58 €/MWh for cold, with 82.2% less CO₂ than gas. Summer cooling from the same brine keeps the doublet busy 18.1% longer. For comparison: A4 (gas reference) at 63.9 €/MWh. Left out: A2 (simulate_year failed: depth 1500 m is outside the doublet model).", "ungrounded": [], "dropped": [], "verified": true, "intent": "design", "language": "en", "screened": false, "heat_coverage": 1.0, "cool_coverage": 1.0, "lcoh": 41.0, "alternative": "A1", "seconds": 0.292, "llm_calls": 1, "prompt_tokens": 560, "output_tokens": 65, "load_seconds": 0.002, "prompt_seconds": 0.012, "output_seconds": 0.261, "tool_calls": 7, "cache_hits": 0, "tool_errors": 1, "left_out": ["A2: simulate_year failed: depth 1500 m is outside the doublet model"], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};