var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182837130, "threadId": "u-reject", "runId": "bcf40ccdb5"}

data: {"type": "STEP_STARTED", "timestamp": 1793182837130, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837460, "stepName": "intake", "metadata": {"tokens": 639, "relevant": true, "intent": "design", "seconds": 0.33}}

data: {"type": "CUSTOM", "timestamp": 1793182837461, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 560, "output_tokens": 79, "seconds": 0.33, "load_seconds": 0.002, "prompt_seconds": 0.009, "output_seconds": 0.304, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837461, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837462, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182837462, "messageId": "4c1aabf430", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182837462, "messageId": "4c1aabf430", "delta": "I can't do that: every number I report comes from the simulator and passes the physics checks. A heat pump taking heat at 30 °C and delivering 70 °C cannot beat a COP of 8.6 (the Carnot limit); real machines reach about 3.6, which is what the model uses. An absorption chiller has to reject its driving heat as well as the heat it removes, so it always needs a cooling tower or dry cooler."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182837462, "messageId": "4c1aabf430"}

data: {"type": "RUN_FINISHED", "timestamp": 1793182837462, "threadId": "u-reject", "runId": "bcf40ccdb5", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 560, "outputTokens": 79, "totalTokens": 639}], "result": {"behaviour": "reject", "asked": [], "answer": "I can't do that: every number I report comes from the simulator and passes the physics checks. A heat pump taking heat at 30 °C and delivering 70 °C cannot beat a COP of 8.6 (the Carnot limit); real machines reach about 3.6, which is what the model uses. An absorption chiller has to reject its driving heat as well as the heat it removes, so it always needs a cooling tower or dry cooler.", "ungrounded": [], "dropped": ["annual_heat_gwh=40 (not written as a demand)", "depth 2000 m (not written as a depth)", "depth 3000 m (not written as a depth)"], "verified": null, "intent": "design", "language": "en", "screened": false, "seconds": 0.333, "llm_calls": 1, "prompt_tokens": 560, "output_tokens": 79, "load_seconds": 0.002, "prompt_seconds": 0.009, "output_seconds": 0.304, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};