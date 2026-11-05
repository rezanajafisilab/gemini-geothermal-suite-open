var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182854058, "threadId": "u-missing", "runId": "540653c51a"}

data: {"type": "STEP_STARTED", "timestamp": 1793182854058, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854061, "stepName": "intake", "metadata": {"tokens": 0, "relevant": true, "intent": "other", "seconds": 0.004}}

data: {"type": "CUSTOM", "timestamp": 1793182854061, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:8b", "prompt_tokens": 0, "output_tokens": 0, "seconds": 0.004, "load_seconds": 0.0, "prompt_seconds": 0.0, "output_seconds": 0.0, "ok": false, "error": "ResponseError: model 'qwen3:8b' not found (status code: 404)"}}

data: {"type": "CUSTOM", "timestamp": 1793182854061, "name": "model_unavailable", "value": {"model": "qwen3:8b", "error": "ResponseError: model 'qwen3:8b' not found (status code: 404)", "fix": "ollama pull qwen3:8b"}}

data: {"type": "STEP_STARTED", "timestamp": 1793182854061, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182854061, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182854061, "messageId": "00de6003c6", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182854061, "messageId": "00de6003c6", "delta": "I can't read your request right now: the local model qwen3:8b isn't available. Run \`ollama pull qwen3:8b\` and ask again."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182854061, "messageId": "00de6003c6"}

data: {"type": "RUN_FINISHED", "timestamp": 1793182854061, "threadId": "u-missing", "runId": "540653c51a", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:8b", "provider": "ollama", "inputTokens": 0, "outputTokens": 0, "totalTokens": 0}], "result": {"behaviour": "model_unavailable", "asked": [], "answer": "I can't read your request right now: the local model qwen3:8b isn't available. Run \`ollama pull qwen3:8b\` and ask again.", "ungrounded": [], "dropped": [], "verified": null, "intent": "other", "language": "en", "screened": false, "seconds": 0.004, "llm_calls": 1, "prompt_tokens": 0, "output_tokens": 0, "load_seconds": 0.0, "prompt_seconds": 0.0, "output_seconds": 0.0, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:8b", "prompt_version": "intake_v1"}}

`;export{e as default};