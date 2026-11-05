var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182854368, "threadId": "u-err", "runId": "70fc92b937"}

data: {"type": "STEP_STARTED", "timestamp": 1793182854368, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854632, "stepName": "intake", "metadata": {"tokens": 625, "relevant": true, "intent": "design", "seconds": 0.264}}

data: {"type": "CUSTOM", "timestamp": 1793182854632, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 560, "output_tokens": 65, "seconds": 0.264, "load_seconds": 0.001, "prompt_seconds": 0.004, "output_seconds": 0.251, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854633, "stepName": "plan", "metadata": {"label": "Plan the study", "kind": "plan", "code": "plan(A1, A2, A4)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854633, "stepName": "plan", "metadata": {"alternatives": ["Deep doublet with absorption cascade", "Shallow doublet with heat pumps", "Gas boiler and electric chillers (reference)"], "not_modelled": ["A3: Doublet with aquifer storage (ATES model not built yet)"], "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854633, "stepName": "doublet", "metadata": {"label": "Solve the doublet", "kind": "tool", "code": "solve_doublet(depth_m=2500, 1500)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854633, "toolCallId": "8d7d65a662", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854633, "toolCallId": "8d7d65a662", "delta": "{\\"depth_m\\": 2500.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854633, "toolCallId": "8d7d65a662"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854633, "messageId": "8d7d65a662-result", "toolCallId": "8d7d65a662", "content": "{\\"cached\\": false, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 2500.0, \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854633, "toolCallId": "e753ba6c96", "toolCallName": "solve_doublet"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854633, "toolCallId": "e753ba6c96", "delta": "{\\"depth_m\\": 1500.0, \\"reservoir_delta_c\\": 0.0}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854633, "toolCallId": "e753ba6c96"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854633, "messageId": "e753ba6c96-result", "toolCallId": "e753ba6c96", "content": "{\\"cached\\": false, \\"result\\": {\\"source\\": \\"mock\\", \\"depth_m\\": 1500.0, \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"flow_mw_per_k\\": 0.1974, \\"available_heat_mw\\": 4.97}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854633, "stepName": "doublet", "metadata": {"calls": 2, "failed": 0, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854633, "stepName": "simulate", "metadata": {"label": "Simulate the year", "kind": "tool", "code": "simulate_year(A1, A2, A4)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854634, "toolCallId": "10fe54ce00", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854634, "toolCallId": "10fe54ce00", "delta": "{\\"alternative\\": {\\"code\\": \\"A1\\", \\"name\\": \\"Deep doublet with absorption cascade\\", \\"depth_m\\": 2500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": true, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854634, "toolCallId": "10fe54ce00"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854634, "messageId": "10fe54ce00-result", "toolCallId": "10fe54ce00", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854635, "toolCallId": "85aaef9b59", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854635, "toolCallId": "85aaef9b59", "delta": "{\\"alternative\\": {\\"code\\": \\"A2\\", \\"name\\": \\"Shallow doublet with heat pumps\\", \\"depth_m\\": 1500.0, \\"heat_pump\\": true, \\"boiler\\": true, \\"absorption\\": false, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854635, "toolCallId": "85aaef9b59"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854635, "messageId": "85aaef9b59-result", "toolCallId": "85aaef9b59", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"hex_outlet_c\\": 55.2, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 43.16, \\"boiler\\": 18.59}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 6.89, \\"boiler_mw\\": 7.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6269.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 11.98, \\"brine_heat_gwh\\": 31.18, \\"brine_capacity_mw\\": 4.97}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854636, "toolCallId": "01adf245e5", "toolCallName": "simulate_year"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854636, "toolCallId": "01adf245e5", "delta": "{\\"alternative\\": {\\"code\\": \\"A4\\", \\"name\\": \\"Gas boiler and electric chillers (reference)\\", \\"depth_m\\": 0.0, \\"heat_pump\\": false, \\"boiler\\": true, \\"absorption\\": false, \\"chillers\\": true}, \\"brief\\": {\\"site\\": null, \\"heating\\": {\\"supply_c\\": 70.0, \\"return_c\\": 40.0}, \\"cooling\\": {\\"supply_c\\": 6.0, \\"return_c\\": 12.0}, \\"annual_heat_gwh\\": null, \\"annual_cool_gwh\\": null, \\"reservoir_depth_m\\": 2500.0, \\"reservoir_temp_c\\": 87.0, \\"transmissivity_dm\\": null, \\"min_heat_coverage\\": 0.95, \\"min_cool_coverage\\": 0.95, \\"excluded\\": [], \\"doublet_depths_m\\": [], \\"reservoir_delta_c\\": 0.0, \\"wants_cooling\\": true}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854636, "toolCallId": "01adf245e5"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854636, "messageId": "01adf245e5-result", "toolCallId": "01adf245e5", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 10.0, \\"wellhead_c\\": 10.0, \\"hex_outlet_c\\": 10.0, \\"reinjection_c\\": 10.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 61.76}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 14.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854636, "stepName": "simulate", "metadata": {"calls": 3, "failed": 0, "seconds": 0.004}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854636, "stepName": "economics", "metadata": {"label": "Cost and CO₂", "kind": "tool", "code": "economics(A1, A2, A4)"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854637, "toolCallId": "20907277ea", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854637, "toolCallId": "20907277ea", "delta": "{\\"alternative\\": \\"A1\\", \\"year\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 87.0, \\"wellhead_c\\": 86.0, \\"hex_outlet_c\\": 45.0, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 48.22, \\"hp\\": 12.02, \\"boiler\\": 1.52}, \\"cool_split_gwh\\": {\\"abs\\": 7.32, \\"chill\\": 6.36}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 8.09, \\"heat_pump_mw\\": 4.1, \\"boiler_mw\\": 2.0, \\"absorption_mw\\": 2.0, \\"chiller_mw\\": 2.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6080.0, \\"cooling_gain\\": 0.181, \\"heat_pump_electricity_gwh\\": 3.34, \\"brine_heat_gwh\\": 67.21, \\"brine_capacity_mw\\": 11.05}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854637, "toolCallId": "20907277ea"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854637, "messageId": "20907277ea-result", "toolCallId": "20907277ea", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A1\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 41.0, \\"lcoc_eur_per_mwh\\": 58.0, \\"capex_meur\\": 25.1, \\"co2_saving_vs_gas\\": 0.822}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854637, "toolCallId": "cc996d2237", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854637, "toolCallId": "cc996d2237", "delta": "{\\"alternative\\": \\"A2\\", \\"year\\": {\\"alternative\\": \\"A2\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 56.2, \\"wellhead_c\\": 55.2, \\"hex_outlet_c\\": 55.2, \\"reinjection_c\\": 30.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 43.16, \\"boiler\\": 18.59}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 6.89, \\"boiler_mw\\": 7.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 6269.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 11.98, \\"brine_heat_gwh\\": 31.18, \\"brine_capacity_mw\\": 4.97}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854637, "toolCallId": "cc996d2237"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854637, "messageId": "cc996d2237-result", "toolCallId": "cc996d2237", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A2\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 65.5, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 19.9, \\"co2_saving_vs_gas\\": 0.324}}", "role": "tool"}

data: {"type": "TOOL_CALL_START", "timestamp": 1793182854637, "toolCallId": "48b4cbc8f1", "toolCallName": "economics"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793182854637, "toolCallId": "48b4cbc8f1", "delta": "{\\"alternative\\": \\"A4\\", \\"year\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"reservoir_c\\": 10.0, \\"wellhead_c\\": 10.0, \\"hex_outlet_c\\": 10.0, \\"reinjection_c\\": 10.0, \\"heat_demand_gwh\\": 61.76, \\"cool_demand_gwh\\": 13.67, \\"heat_delivered_gwh\\": 61.76, \\"cool_delivered_gwh\\": 13.67, \\"heat_coverage\\": 1.0, \\"cool_coverage\\": 1.0, \\"heat_split_gwh\\": {\\"geo\\": 0.0, \\"hp\\": 0.0, \\"boiler\\": 61.76}, \\"cool_split_gwh\\": {\\"abs\\": 0.0, \\"chill\\": 13.67}, \\"peak_heat_mw\\": 13.88, \\"peak_cool_mw\\": 4.16, \\"hex_mw\\": 0.0, \\"heat_pump_mw\\": 0.0, \\"boiler_mw\\": 14.0, \\"absorption_mw\\": 0.0, \\"chiller_mw\\": 4.5, \\"heat_pump_cop\\": 3.6, \\"heat_pump_carnot_cop\\": 8.58, \\"full_load_hours\\": 0.0, \\"cooling_gain\\": 0.0, \\"heat_pump_electricity_gwh\\": 0.0, \\"brine_heat_gwh\\": 0.0, \\"brine_capacity_mw\\": 0.0}}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793182854637, "toolCallId": "48b4cbc8f1"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793182854637, "messageId": "48b4cbc8f1-result", "toolCallId": "48b4cbc8f1", "content": "{\\"cached\\": false, \\"result\\": {\\"alternative\\": \\"A4\\", \\"source\\": \\"mock\\", \\"lcoh_eur_per_mwh\\": 63.9, \\"lcoc_eur_per_mwh\\": 59.0, \\"capex_meur\\": 3.8, \\"co2_saving_vs_gas\\": 0.0}}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854637, "stepName": "economics", "metadata": {"calls": 3, "failed": 0, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854637, "stepName": "verify", "metadata": {"label": "Check the physics", "kind": "check", "code": "verify_design(A1, A2, A4)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854637, "stepName": "verify", "metadata": {"passed": 3, "total": 3, "seconds": 0.0}}

data: {"type": "RUN_ERROR", "timestamp": 1793182854637, "message": "KeyError: 'lcoc_eur_per_mwh'", "code": "agent_error"}

data: {"type": "RUN_FINISHED", "timestamp": 1793182854637, "threadId": "u-err", "runId": "70fc92b937", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 560, "outputTokens": 65, "totalTokens": 625}], "result": {"behaviour": "error", "asked": [], "answer": "", "ungrounded": [], "dropped": [], "verified": null, "intent": "design", "language": "en", "screened": false, "error": "KeyError: 'lcoc_eur_per_mwh'", "seconds": 0.269, "llm_calls": 1, "prompt_tokens": 560, "output_tokens": 65, "load_seconds": 0.001, "prompt_seconds": 0.004, "output_seconds": 0.251, "tool_calls": 8, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};