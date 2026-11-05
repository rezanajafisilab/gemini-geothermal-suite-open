var e=`data: {"type": "RUN_STARTED", "timestamp": 1793270200000, "threadId": "f-image", "runId": "9a0c3e7b15"}

data: {"type": "STEP_STARTED", "timestamp": 1793270200001, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793270200361, "stepName": "intake", "metadata": {"tokens": 878, "relevant": true, "intent": "data", "screened": false, "seconds": 0.36}}

data: {"type": "CUSTOM", "timestamp": 1793270200361, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 812, "output_tokens": 66, "seconds": 0.36, "load_seconds": 0.002, "prompt_seconds": 0.108, "output_seconds": 0.245, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793270200362, "stepName": "read_file", "metadata": {"label": "Open network_map.png", "kind": "tool", "code": "read_file('network_map.png', view='image')"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793270200366, "toolCallId": "2c8d5f1e90", "toolCallName": "read_file"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793270200366, "toolCallId": "2c8d5f1e90", "delta": "{\\"name\\": \\"network_map.png\\", \\"view\\": \\"image\\", \\"threadId\\": \\"f-image\\"}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793270200366, "toolCallId": "2c8d5f1e90"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793270200384, "messageId": "2c8d5f1e90-result", "toolCallId": "2c8d5f1e90", "content": "{\\"cached\\": false, \\"result\\": {\\"name\\": \\"network_map.png\\", \\"origin\\": \\"attachment\\", \\"kind\\": \\"image\\", \\"width\\": 458, \\"height\\": 458}}", "role": "tool"}

data: {"type": "CUSTOM", "timestamp": 1793270200385, "name": "file", "value": {"name": "network_map.png", "kind": "image", "origin": "attachment", "url": "/favicon.svg", "size_bytes": 48213, "show": "image", "note": "Your upload. The models here read text only: they can show an image but not see what is drawn in it.", "image": {"url": "/favicon.svg", "width": 458, "height": 458}}}

data: {"type": "STEP_FINISHED", "timestamp": 1793270200386, "stepName": "read_file", "metadata": {"files": 1, "rows": null, "seconds": 0.024}}

data: {"type": "STEP_STARTED", "timestamp": 1793270200387, "stepName": "answer", "metadata": {"label": "Write the answer", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793270201597, "stepName": "answer", "metadata": {"decided_by": "model", "model": "qwen3.5:9b", "device": "gpu", "tokens": 2034, "understood": "You want to see the network map you attached.", "kind": "answer", "scope": "project", "seconds": 1.21}}

data: {"type": "CUSTOM", "timestamp": 1793270201597, "name": "usage", "value": {"purpose": "answer", "model": "qwen3.5:9b", "prompt_tokens": 1960, "output_tokens": 74, "seconds": 1.21, "load_seconds": 0.002, "prompt_seconds": 0.363, "output_seconds": 0.823, "ok": true, "error": ""}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793270201598, "messageId": "9a0c3ea1b2", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793270201638, "messageId": "9a0c3ea1b2", "delta": "Here is network_map.png, the image you attached.\\n\\nI can show it, but I can't see what is drawn in it. If it holds numbers the design needs, such as pipe lengths or the substations' supply temperatures, type them in and I'll use them.\\n"}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793270201639, "messageId": "9a0c3ea1b2"}

data: {"type": "CUSTOM", "timestamp": 1793270201640, "name": "answer", "value": {"understood": "You want to see the network map you attached.", "kind": "answer", "scope": "project", "used": [], "model": "qwen3.5:9b", "device": "gpu", "fallback": false, "corrections": []}}

data: {"type": "CUSTOM", "timestamp": 1793270201641, "name": "suggestions", "value": ["Design heating and cooling for this district", "What data does the design need?"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793270201642, "threadId": "f-image", "runId": "9a0c3e7b15", "outcome": {"type": "success"}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 812, "outputTokens": 66, "totalTokens": 878}, {"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 1960, "outputTokens": 74, "totalTokens": 2034}], "result": {"behaviour": "answer", "asked": [], "answer": "Here is network_map.png, the image you attached.\\n\\nI can show it, but I can't see what is drawn in it. If it holds numbers the design needs, such as pipe lengths or the substations' supply temperatures, type them in and I'll use them.", "ungrounded": [], "dropped": [], "verified": null, "intent": "data", "language": "en", "screened": false, "seconds": 1.66, "llm_calls": 2, "calls": ["intake: qwen3:1.7b", "answer: qwen3.5:9b"], "prompt_tokens": 2772, "output_tokens": 140, "tool_calls": 1, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "answer_v2", "reasoning": false, "decided_by": {"answer": "model"}}}

`;export{e as default};