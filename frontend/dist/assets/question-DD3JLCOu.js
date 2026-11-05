var e=`data: {"type": "RUN_STARTED", "timestamp": 1793185368323, "threadId": "v-question", "runId": "8bbf475185"}

data: {"type": "STEP_STARTED", "timestamp": 1793185368323, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185371885, "stepName": "intake", "metadata": {"tokens": 871, "relevant": true, "intent": "question", "screened": false, "seconds": 3.562}}

data: {"type": "CUSTOM", "timestamp": 1793185371886, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 797, "output_tokens": 74, "seconds": 3.561, "load_seconds": 3.081, "prompt_seconds": 0.179, "output_seconds": 0.29, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793185371886, "stepName": "lookup", "metadata": {"label": "Look up the values", "kind": "tool", "code": "lookup(reservoir_temp)"}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185371887, "stepName": "lookup", "metadata": {"found": ["reservoir_temp"], "missing": [], "seconds": 0.0}}

data: {"type": "STEP_STARTED", "timestamp": 1793185371887, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793185371887, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793185371888, "messageId": "24f1dd395b", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793185371888, "messageId": "24f1dd395b", "delta": "The initial reservoir temperature is 87 °C (undisturbed, before production cools it, at 2,500 m). Source: the project's subsurface data (subsurface.json)."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793185371888, "messageId": "24f1dd395b"}

data: {"type": "CUSTOM", "timestamp": 1793185371888, "name": "suggestions", "value": ["Design heating and cooling for this district", "Compare well depths", "What does the reservoir temperature change?"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793185371889, "threadId": "v-question", "runId": "8bbf475185", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 797, "outputTokens": 74, "totalTokens": 871}], "result": {"behaviour": "answer", "asked": [], "answer": "The initial reservoir temperature is 87 °C (undisturbed, before production cools it, at 2,500 m). Source: the project's subsurface data (subsurface.json).", "ungrounded": [], "dropped": [], "verified": null, "reasoning": false, "decided_by": {}, "intent": "question", "language": "en", "screened": false, "seconds": 3.566, "llm_calls": 1, "calls": ["intake: qwen3:1.7b"], "prompt_tokens": 797, "output_tokens": 74, "load_seconds": 3.081, "prompt_seconds": 0.179, "output_seconds": 0.29, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v2"}}

`;export{e as default};