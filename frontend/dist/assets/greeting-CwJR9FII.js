var e=`data: {"type": "RUN_STARTED", "timestamp": 1793185368267, "threadId": "v-greet", "runId": "11c1d7f897"}

data: {"type": "STEP_STARTED", "timestamp": 1793185368268, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185368268, "stepName": "intake", "metadata": {"tokens": 0, "relevant": true, "intent": "greeting", "screened": true, "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793185368268, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185368269, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793185368269, "messageId": "f773f94668", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793185368269, "messageId": "f773f94668", "delta": "Hello! I design geothermal heating and cooling for this district. Ask me to design a system, compare options or look up a value."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793185368269, "messageId": "f773f94668"}

data: {"type": "CUSTOM", "timestamp": 1793185368269, "name": "suggestions", "value": ["Design heating and cooling for this district", "Compare well depths", "What does the reservoir temperature change?"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793185368270, "threadId": "v-greet", "runId": "11c1d7f897", "outcome": {"type": "success"}, "usage": [], "result": {"behaviour": "greeting", "asked": [], "answer": "Hello! I design geothermal heating and cooling for this district. Ask me to design a system, compare options or look up a value.", "ungrounded": [], "dropped": [], "verified": null, "reasoning": false, "decided_by": {}, "intent": "greeting", "language": "en", "screened": true, "seconds": 0.002, "llm_calls": 0, "calls": [], "prompt_tokens": 0, "output_tokens": 0, "load_seconds": 0, "prompt_seconds": 0, "output_seconds": 0, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v2"}}

`;export{e as default};