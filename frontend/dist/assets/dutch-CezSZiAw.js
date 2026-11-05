var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182838098, "threadId": "u-dutch", "runId": "45df0fb104"}

data: {"type": "STEP_STARTED", "timestamp": 1793182838099, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182838416, "stepName": "intake", "metadata": {"tokens": 641, "relevant": true, "intent": "design", "seconds": 0.318}}

data: {"type": "CUSTOM", "timestamp": 1793182838417, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 560, "output_tokens": 81, "seconds": 0.318, "load_seconds": 0.001, "prompt_seconds": 0.009, "output_seconds": 0.298, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182838417, "stepName": "ask", "metadata": {"label": "Ask for the missing inputs", "kind": "ask", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182838417, "stepName": "ask", "metadata": {"seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182838417, "messageId": "b5fe3122eb", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182838418, "messageId": "b5fe3122eb", "delta": "Voordat ik ontwerp, heb ik 2 gegevens nodig. Elk heeft een voorstel: neem het over of pas het aan."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182838418, "messageId": "b5fe3122eb"}

data: {"type": "CUSTOM", "timestamp": 1793182838418, "name": "clarification", "value": {"intro": "Voordat ik ontwerp, heb ik 2 gegevens nodig. Elk heeft een voorstel: neem het over of pas het aan.", "questions": [{"id": "dh_supply_return_c", "label": "Heating network, supply and return", "hint": "Typical for a new network.", "options": ["80/50 °C", "70/40 °C", "60/30 °C"], "default": "70/40 °C", "required": true}, {"id": "dc_supply_return_c", "label": "Cooling network, supply and return", "hint": "Typical for building cooling.", "options": ["6/12 °C", "8/14 °C", "16/19 °C"], "default": "6/12 °C", "required": true}]}}

data: {"type": "RUN_FINISHED", "timestamp": 1793182838418, "threadId": "u-dutch", "runId": "45df0fb104", "outcome": {"type": "interrupt", "interrupts": [{"id": "45df0fb104-ask", "reason": "clarification"}]}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 560, "outputTokens": 81, "totalTokens": 641}], "result": {"behaviour": "clarify", "asked": ["dh_supply_return_c", "dc_supply_return_c"], "answer": "Voordat ik ontwerp, heb ik 2 gegevens nodig. Elk heeft een voorstel: neem het over of pas het aan.", "ungrounded": [], "dropped": ["annual_heat_gwh=40 (not written as a demand)", "annual_cool_gwh=40 (not written as a demand)", "depth 2000 m (not written as a depth)", "reservoir_depth_m=2000 (not written as one)", "reservoir_temp_c=15 (outside 30-250)"], "verified": null, "intent": "design", "language": "nl", "screened": false, "seconds": 0.32, "llm_calls": 1, "prompt_tokens": 560, "output_tokens": 81, "load_seconds": 0.001, "prompt_seconds": 0.009, "output_seconds": 0.298, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};