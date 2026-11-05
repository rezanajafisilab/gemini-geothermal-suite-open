var e=`data: {"type": "RUN_STARTED", "timestamp": 1793187158282, "threadId": "g3", "runId": "5abb2d0e3d"}

data: {"type": "STEP_STARTED", "timestamp": 1793187158282, "stepName": "report", "metadata": {"label": "Write the answer", "kind": "report", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793187158283, "stepName": "report", "metadata": {"ungrounded": [], "seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793187158283, "messageId": "03cef16ed0", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793187158283, "messageId": "03cef16ed0", "delta": "Understood: no new model. The design keeps the components it has."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793187158283, "messageId": "03cef16ed0"}

data: {"type": "RUN_FINISHED", "timestamp": 1793187158284, "threadId": "g3", "runId": "5abb2d0e3d", "outcome": {"type": "success"}, "usage": [], "result": {"behaviour": "answer", "asked": [], "answer": "Understood: no new model. The design keeps the components it has.", "ungrounded": [], "dropped": [], "verified": null, "reasoning": false, "decided_by": {}, "intent": "question", "language": "en", "answered": ["generate"], "seconds": 0.002, "llm_calls": 0, "calls": [], "prompt_tokens": 0, "output_tokens": 0, "load_seconds": 0, "prompt_seconds": 0, "output_seconds": 0, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 2, "model": "qwen3:1.7b", "prompt_version": "intake_v2"}}

`;export{e as default};