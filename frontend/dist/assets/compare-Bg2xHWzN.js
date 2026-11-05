var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182838437, "threadId": "u-compare", "runId": "780851c15e"}

data: {"type": "STEP_STARTED", "timestamp": 1793182838437, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182838738, "stepName": "intake", "metadata": {"tokens": 635, "relevant": true, "intent": "compare", "seconds": 0.3}}

data: {"type": "CUSTOM", "timestamp": 1793182838738, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 559, "output_tokens": 76, "seconds": 0.3, "load_seconds": 0.002, "prompt_seconds": 0.009, "output_seconds": 0.276, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182838738, "stepName": "ask", "metadata": {"label": "Ask for the missing inputs", "kind": "ask", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182838739, "stepName": "ask", "metadata": {"seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182838739, "messageId": "091ddd2ea6", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182838739, "messageId": "091ddd2ea6", "delta": "Before I design, I need 2 inputs. Each has a proposed default: accept it or change it."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182838739, "messageId": "091ddd2ea6"}

data: {"type": "CUSTOM", "timestamp": 1793182838739, "name": "clarification", "value": {"intro": "Before I design, I need 2 inputs. Each has a proposed default: accept it or change it.", "questions": [{"id": "dh_supply_return_c", "label": "Heating network, supply and return", "hint": "Typical for a new network.", "options": ["80/50 °C", "70/40 °C", "60/30 °C"], "default": "70/40 °C", "required": true}, {"id": "dc_supply_return_c", "label": "Cooling network, supply and return", "hint": "Typical for building cooling.", "options": ["6/12 °C", "8/14 °C", "16/19 °C"], "default": "6/12 °C", "required": true}]}}

data: {"type": "RUN_FINISHED", "timestamp": 1793182838740, "threadId": "u-compare", "runId": "780851c15e", "outcome": {"type": "interrupt", "interrupts": [{"id": "780851c15e-ask", "reason": "clarification"}]}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 559, "outputTokens": 76, "totalTokens": 635}], "result": {"behaviour": "clarify", "asked": ["dh_supply_return_c", "dc_supply_return_c"], "answer": "Before I design, I need 2 inputs. Each has a proposed default: accept it or change it.", "ungrounded": [], "dropped": [], "verified": null, "intent": "compare", "language": "en", "screened": false, "seconds": 0.303, "llm_calls": 1, "prompt_tokens": 559, "output_tokens": 76, "load_seconds": 0.002, "prompt_seconds": 0.009, "output_seconds": 0.276, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};