var e=`data: {"type": "RUN_STARTED", "timestamp": 1793270300000, "threadId": "w-md", "runId": "71e2b9c0d4"}

data: {"type": "STEP_STARTED", "timestamp": 1793270300001, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793270300361, "stepName": "intake", "metadata": {"tokens": 878, "relevant": true, "intent": "explain", "screened": false, "seconds": 0.36}}

data: {"type": "CUSTOM", "timestamp": 1793270300361, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 812, "output_tokens": 66, "seconds": 0.36, "load_seconds": 0.002, "prompt_seconds": 0.108, "output_seconds": 0.245, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793270300362, "stepName": "docs", "metadata": {"label": "Search the documents", "kind": "tool", "code": "search_docs('heat pump absorption chiller')"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793270300482, "toolCallId": "b0e19c7a44", "toolCallName": "search_docs"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793270300482, "toolCallId": "b0e19c7a44", "delta": "{\\"query\\": \\"heat pump absorption chiller\\", \\"threadId\\": \\"w-md\\", \\"only_attached\\": false}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793270300482, "toolCallId": "b0e19c7a44"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793270300484, "messageId": "b0e19c7a44-result", "toolCallId": "b0e19c7a44", "content": "{\\"backend\\": \\"gemini-chroma\\", \\"passages\\": [{\\"source\\": \\"src/gemini_documentation/source/model_surface_equipment.rst\\", \\"section\\": \\"Surface Equipment > Heat Pump\\", \\"text\\": \\"gemini_model.heatpump.heatpump_basic.HeatpumpBasic computes the coefficient of performance (COP), outlet temperatures, thermal production, and electrical consumption of a heat pump, using either a Carnot-efficiency or a Lorenz-efficiency model. It solves the thermodynamic efficiency equation together with the sink/source energy balance.\\", \\"score\\": 0.8065, \\"suspicious\\": false, \\"kind\\": \\"doc\\", \\"images\\": [{\\"url\\": \\"/favicon.svg\\", \\"caption\\": \\"Heat pump: the source loop (brine) and the sink loop (district network)\\"}]}, {\\"source\\": \\"hackathon/docs/cooling_design.md\\", \\"section\\": \\"4. Proposed models (GEMINI-compatible) > Absorption chiller\\", \\"text\\": \\"Single-effect LiBr–water chiller driven by the brine after the heat exchanger. COP_th ≈ 0.7 at 85 °C drive, falling steeply below 75 °C; chilled water 6/12 °C; heat rejected to a dry cooler: Q_rej = Q_E + Q_drive.\\", \\"score\\": 0.7627, \\"suspicious\\": false, \\"kind\\": \\"note\\", \\"file\\": \\"cooling_design.md\\"}]}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793270300485, "stepName": "docs", "metadata": {"passages": 2, "suspicious": 0, "backend": "gemini-chroma", "seconds": 0.122}}

data: {"type": "STEP_STARTED", "timestamp": 1793270300486, "stepName": "answer", "metadata": {"label": "Write the answer", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793270303126, "stepName": "answer", "metadata": {"decided_by": "model", "model": "qwen3.5:9b", "device": "gpu", "tokens": 3192, "understood": "You want the heat pump and the absorption chiller compared.", "kind": "answer", "scope": "general", "seconds": 2.64}}

data: {"type": "CUSTOM", "timestamp": 1793270303126, "name": "usage", "value": {"purpose": "answer", "model": "qwen3.5:9b", "prompt_tokens": 2980, "output_tokens": 212, "seconds": 2.64, "load_seconds": 0.002, "prompt_seconds": 0.792, "output_seconds": 1.795, "ok": true, "error": ""}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793270303127, "messageId": "71e2b9a1b2", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793270303167, "messageId": "71e2b9a1b2", "delta": "A **heat pump** and an **absorption chiller** do opposite jobs in the cascade:\\n\\n- The heat pump lifts low-temperature brine to the network's 70/40 °C, and pays for the lift with electricity.[^1]\\n"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793270303207, "messageId": "71e2b9a1b2", "delta": "- The absorption chiller is *driven by heat*: hot brine makes chilled water at 6/12 °C with little electricity.[^2]\\n"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793270303247, "messageId": "71e2b9a1b2", "delta": "- Both sit after the heat exchanger, so they share what the doublet delivers.\\n\\n| | Heat pump | Absorption chiller |\\n"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793270303287, "messageId": "71e2b9a1b2", "delta": "|---|---|---|\\n| Driven by | electricity | brine at 75–95 °C |\\n| Typical COP | 3.6 | 0.7 |\\n| Delivers | heat at 70/40 °C | cold at 6/12 °C |\\n"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793270303327, "messageId": "71e2b9a1b2", "delta": "| In GEMINI | \`HeatpumpBasic\` | not modelled yet |\\n\\n### What this means here\\nThe chiller only works while the brine stays above about 75 °C, so it belongs on the **deep** doublet. Our proposed model is in cooling_design.md.[^2]\\n"}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793270303328, "messageId": "71e2b9a1b2"}

data: {"type": "CUSTOM", "timestamp": 1793270303329, "name": "answer", "value": {"understood": "You want the heat pump and the absorption chiller compared.", "kind": "answer", "scope": "general", "used": ["doc1", "doc2"], "model": "qwen3.5:9b", "device": "gpu", "fallback": false, "corrections": []}}

data: {"type": "CUSTOM", "timestamp": 1793270303330, "name": "sources", "value": [{"source": "src/gemini_documentation/source/model_surface_equipment.rst", "section": "Surface Equipment > Heat Pump", "text": "gemini_model.heatpump.heatpump_basic.HeatpumpBasic computes the coefficient of performance (COP), outlet temperatures, thermal production, and electrical consumption of a heat pump, using either a Carnot-efficiency or a Lorenz-efficiency model. It solves the thermodynamic efficiency equation together with the sink/source energy balance.", "score": 0.8065, "suspicious": false, "kind": "doc", "images": [{"url": "/favicon.svg", "caption": "Heat pump: the source loop (brine) and the sink loop (district network)"}]}, {"source": "hackathon/docs/cooling_design.md", "section": "4. Proposed models (GEMINI-compatible) > Absorption chiller", "text": "Single-effect LiBr–water chiller driven by the brine after the heat exchanger. COP_th ≈ 0.7 at 85 °C drive, falling steeply below 75 °C; chilled water 6/12 °C; heat rejected to a dry cooler: Q_rej = Q_E + Q_drive.", "score": 0.7627, "suspicious": false, "kind": "note", "file": "cooling_design.md"}]}

data: {"type": "CUSTOM", "timestamp": 1793270303331, "name": "suggestions", "value": ["How is the heat pump COP computed?", "Design heating and cooling for this district"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793270303332, "threadId": "w-md", "runId": "71e2b9c0d4", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 812, "outputTokens": 66, "totalTokens": 878}, {"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 2980, "outputTokens": 212, "totalTokens": 3192}], "result": {"behaviour": "answer", "asked": [], "answer": "A **heat pump** and an **absorption chiller** do opposite jobs in the cascade:\\n\\n- The heat pump lifts low-temperature brine to the network's 70/40 °C, and pays for the lift with electricity.[^1]\\n- The absorption chiller is *driven by heat*: hot brine makes chilled water at 6/12 °C with little electricity.[^2]\\n- Both sit after the heat exchanger, so they share what the doublet delivers.\\n\\n| | Heat pump | Absorption chiller |\\n|---|---|---|\\n| Driven by | electricity | brine at 75–95 °C |\\n| Typical COP | 3.6 | 0.7 |\\n| Delivers | heat at 70/40 °C | cold at 6/12 °C |\\n| In GEMINI | \`HeatpumpBasic\` | not modelled yet |\\n\\n### What this means here\\nThe chiller only works while the brine stays above about 75 °C, so it belongs on the **deep** doublet. Our proposed model is in cooling_design.md.[^2]", "ungrounded": [], "dropped": [], "verified": null, "intent": "explain", "language": "en", "screened": false, "seconds": 3.09, "llm_calls": 2, "calls": ["intake: qwen3:1.7b", "answer: qwen3.5:9b"], "prompt_tokens": 3792, "output_tokens": 278, "tool_calls": 1, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "answer_v2", "reasoning": false, "decided_by": {"answer": "model"}}}

`;export{e as default};