var e=`data: {"type": "RUN_STARTED", "timestamp": 1793260000000, "threadId": "w-adv", "runId": "a1c0de5e01"}

data: {"type": "STEP_STARTED", "timestamp": 1793260000001, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260000389, "stepName": "intake", "metadata": {"tokens": 884, "relevant": true, "intent": "about", "screened": false, "seconds": 0.388}}

data: {"type": "CUSTOM", "timestamp": 1793260000389, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 820, "output_tokens": 64, "seconds": 0.388, "load_seconds": 0.002, "prompt_seconds": 0.116, "output_seconds": 0.264, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793260000390, "stepName": "answer", "metadata": {"label": "Write the answer", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260002460, "stepName": "answer", "metadata": {"decided_by": "model", "model": "qwen3.5:9b", "device": "gpu", "tokens": 2354, "understood": "You want to know what Dioscuri does better than a spreadsheet.", "kind": "answer", "scope": "project", "seconds": 2.07}}

data: {"type": "CUSTOM", "timestamp": 1793260002460, "name": "usage", "value": {"purpose": "answer", "model": "qwen3.5:9b", "prompt_tokens": 2236, "output_tokens": 118, "seconds": 2.07, "load_seconds": 0.002, "prompt_seconds": 0.621, "output_seconds": 1.408, "ok": true, "error": ""}}

data: {"type": "CUSTOM", "timestamp": 1793260002461, "name": "answer", "value": {"understood": "You want to know what Dioscuri does better than a spreadsheet.", "kind": "answer", "scope": "project", "used": ["self"], "model": "qwen3.5:9b", "device": "gpu", "fallback": false, "corrections": []}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793260002462, "messageId": "ad7e0f1c22", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260002502, "messageId": "ad7e0f1c22", "delta": "A spreadsheet holds the numbers you type in; I work them out. I read your brief, ask once for anything missing, then simulate each option with GEMINI's physics models: the "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260002542, "messageId": "ad7e0f1c22", "delta": "doublet, the heat pumps, the cooling cascade. Every design is checked for energy balance, the Carnot limit and its temperatures before I report it, and every number in my answer "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260002582, "messageId": "ad7e0f1c22", "delta": "traces back to a tool or to you. When a component has no model yet, I can write one and test it in a sandbox, but only with your yes."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793260002583, "messageId": "ad7e0f1c22"}

data: {"type": "CUSTOM", "timestamp": 1793260002584, "name": "suggestions", "value": ["Design heating and cooling for this district", "Show me how a design is checked", "What can't you model yet?"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793260002585, "threadId": "w-adv", "runId": "a1c0de5e01", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 820, "outputTokens": 64, "totalTokens": 884}, {"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 2236, "outputTokens": 118, "totalTokens": 2354}], "result": {"asked": [], "ungrounded": [], "dropped": [], "verified": null, "language": "en", "screened": false, "seconds": 2.584, "llm_calls": 2, "calls": ["intake: qwen3:1.7b", "answer: qwen3.5:9b"], "prompt_tokens": 3056, "output_tokens": 182, "load_seconds": 0.004, "prompt_seconds": 0.737, "output_seconds": 1.671, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "answer_v1", "behaviour": "answer", "answer": "A spreadsheet holds the numbers you type in; I work them out. I read your brief, ask once for anything missing, then simulate each option with GEMINI's physics models: the doublet, the heat pumps, the cooling cascade. Every design is checked for energy balance, the Carnot limit and its temperatures before I report it, and every number in my answer traces back to a tool or to you. When a component has no model yet, I can write one and test it in a sandbox, but only with your yes.", "reasoning": false, "decided_by": {"answer": "model"}, "intent": "about"}}

`;export{e as default};