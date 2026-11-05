var e=`data: {"type": "RUN_STARTED", "timestamp": 1793260400000, "threadId": "w-choice", "runId": "e5c0de5e05"}

data: {"type": "STEP_STARTED", "timestamp": 1793260400001, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260400343, "stepName": "intake", "metadata": {"tokens": 864, "relevant": true, "intent": "explain", "screened": false, "seconds": 0.342}}

data: {"type": "CUSTOM", "timestamp": 1793260400343, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 806, "output_tokens": 58, "seconds": 0.342, "load_seconds": 0.002, "prompt_seconds": 0.103, "output_seconds": 0.233, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793260400344, "stepName": "answer", "metadata": {"label": "Write the answer", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260401554, "stepName": "answer", "metadata": {"decided_by": "model", "model": "qwen3.5:9b", "device": "gpu", "tokens": 2092, "understood": "You want install steps, but 'it' could mean me or GEMINI.", "kind": "clarify", "scope": "project", "seconds": 1.21}}

data: {"type": "CUSTOM", "timestamp": 1793260401554, "name": "usage", "value": {"purpose": "answer", "model": "qwen3.5:9b", "prompt_tokens": 2018, "output_tokens": 74, "seconds": 1.21, "load_seconds": 0.002, "prompt_seconds": 0.363, "output_seconds": 0.823, "ok": true, "error": ""}}

data: {"type": "CUSTOM", "timestamp": 1793260401555, "name": "answer", "value": {"understood": "You want install steps, but 'it' could mean me or GEMINI.", "kind": "clarify", "scope": "project", "used": ["self"], "model": "qwen3.5:9b", "device": "gpu", "fallback": false, "corrections": []}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793260401556, "messageId": "7d3f2a1b66", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260401596, "messageId": "7d3f2a1b66", "delta": "Do you mean how "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260401636, "messageId": "7d3f2a1b66", "delta": "to use me, or "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260401676, "messageId": "7d3f2a1b66", "delta": "how to install GEMINI?"}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793260401677, "messageId": "7d3f2a1b66"}

data: {"type": "CUSTOM", "timestamp": 1793260401678, "name": "clarification", "value": {"kind": "choice", "intro": "Do you mean how to use me, or how to install GEMINI?", "questions": [{"id": "choice", "label": "Do you mean how to use me, or how to install GEMINI?", "hint": "Pick one, or type your own question.", "options": ["Show me how to use Dioscuri", "Explain how to install GEMINI"], "default": null}]}}

data: {"type": "RUN_FINISHED", "timestamp": 1793260401679, "threadId": "w-choice", "runId": "e5c0de5e05", "outcome": {"type": "interrupt", "interrupts": [{"id": "e5c0de5e05-ask", "reason": "choice"}]}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 806, "outputTokens": 58, "totalTokens": 864}, {"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 2018, "outputTokens": 74, "totalTokens": 2092}], "result": {"asked": ["choice"], "ungrounded": [], "dropped": [], "verified": null, "language": "en", "screened": false, "seconds": 1.678, "llm_calls": 2, "calls": ["intake: qwen3:1.7b", "answer: qwen3.5:9b"], "prompt_tokens": 2824, "output_tokens": 132, "load_seconds": 0.004, "prompt_seconds": 0.466, "output_seconds": 1.055, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "answer_v1", "behaviour": "clarify", "answer": "Do you mean how to use me, or how to install GEMINI?", "reasoning": false, "decided_by": {"answer": "model"}, "intent": "explain"}}

`;export{e as default};