var e=`data: {"type": "RUN_STARTED", "timestamp": 1793260200000, "threadId": "w-non", "runId": "c3c0de5e03"}

data: {"type": "STEP_STARTED", "timestamp": 1793260200001, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260200302, "stepName": "intake", "metadata": {"tokens": 831, "relevant": false, "intent": "other", "screened": false, "seconds": 0.301}}

data: {"type": "CUSTOM", "timestamp": 1793260200302, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 790, "output_tokens": 41, "seconds": 0.301, "load_seconds": 0.002, "prompt_seconds": 0.09, "output_seconds": 0.205, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793260200303, "stepName": "answer", "metadata": {"label": "Write the answer", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260201263, "stepName": "answer", "metadata": {"decided_by": "model", "model": "qwen3.5:9b", "device": "gpu", "tokens": 1956, "understood": "The message is random letters, not a question.", "kind": "nonsense", "scope": "out", "seconds": 0.96}}

data: {"type": "CUSTOM", "timestamp": 1793260201263, "name": "usage", "value": {"purpose": "answer", "model": "qwen3.5:9b", "prompt_tokens": 1904, "output_tokens": 52, "seconds": 0.96, "load_seconds": 0.002, "prompt_seconds": 0.288, "output_seconds": 0.653, "ok": true, "error": ""}}

data: {"type": "CUSTOM", "timestamp": 1793260201264, "name": "answer", "value": {"understood": "The message is random letters, not a question.", "kind": "nonsense", "scope": "out", "used": [], "model": "qwen3.5:9b", "device": "gpu", "fallback": false, "corrections": []}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793260201265, "messageId": "3b1d0e9f44", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260201305, "messageId": "3b1d0e9f44", "delta": "I couldn't read that as a question. Did "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260201345, "messageId": "3b1d0e9f44", "delta": "a few keys slip? Ask me about the "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260201385, "messageId": "3b1d0e9f44", "delta": "district's heating and cooling, or pick one of "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260201425, "messageId": "3b1d0e9f44", "delta": "these."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793260201426, "messageId": "3b1d0e9f44"}

data: {"type": "CUSTOM", "timestamp": 1793260201427, "name": "suggestions", "value": ["Design heating and cooling for this district", "What can you do?", "What is the reservoir temperature?"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793260201428, "threadId": "w-non", "runId": "c3c0de5e03", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 790, "outputTokens": 41, "totalTokens": 831}, {"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 1904, "outputTokens": 52, "totalTokens": 1956}], "result": {"asked": [], "ungrounded": [], "dropped": [], "verified": null, "language": "en", "screened": false, "seconds": 1.427, "llm_calls": 2, "calls": ["intake: qwen3:1.7b", "answer: qwen3.5:9b"], "prompt_tokens": 2694, "output_tokens": 93, "load_seconds": 0.004, "prompt_seconds": 0.378, "output_seconds": 0.857, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "answer_v1", "behaviour": "nonsense", "answer": "I couldn't read that as a question. Did a few keys slip? Ask me about the district's heating and cooling, or pick one of these.", "reasoning": false, "decided_by": {"answer": "model"}, "intent": "other"}}

`;export{e as default};