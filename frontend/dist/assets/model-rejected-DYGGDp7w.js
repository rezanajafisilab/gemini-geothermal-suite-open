var e=`data: {"type": "RUN_STARTED", "timestamp": 1793188250213, "threadId": "k2", "runId": "67815ddac5"}

data: {"type": "STEP_STARTED", "timestamp": 1793188250214, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793188250214, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793188250214, "messageId": "a75271a1e9", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793188250214, "messageId": "a75271a1e9", "delta": "Rejected: the model was not saved."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793188250214, "messageId": "a75271a1e9"}

data: {"type": "RUN_FINISHED", "timestamp": 1793188250216, "threadId": "k2", "runId": "67815ddac5", "outcome": {"type": "success"}, "usage": [], "result": {"behaviour": "answer", "asked": [], "answer": "Rejected: the model was not saved.", "ungrounded": [], "dropped": [], "verified": null, "reasoning": false, "decided_by": {}, "intent": "explain", "language": "en", "answered": ["approval"], "seconds": 0.002, "llm_calls": 0, "calls": [], "prompt_tokens": 0, "output_tokens": 0, "load_seconds": 0, "prompt_seconds": 0, "output_seconds": 0, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 4, "model": "qwen3:1.7b", "prompt_version": "intake_v2"}}

`;export{e as default};