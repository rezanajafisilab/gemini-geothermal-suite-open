var e=`data: {"type": "RUN_STARTED", "timestamp": 1793182836794, "threadId": "u-clarify", "runId": "da8ea9e8b9"}

data: {"type": "STEP_STARTED", "timestamp": 1793182836794, "stepName": "intake", "metadata": {"label": "Read the request", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837070, "stepName": "intake", "metadata": {"tokens": 612, "relevant": true, "intent": "design", "seconds": 0.276}}

data: {"type": "CUSTOM", "timestamp": 1793182837070, "name": "usage", "value": {"purpose": "intake", "model": "qwen3:1.7b", "prompt_tokens": 543, "output_tokens": 69, "seconds": 0.276, "load_seconds": 0.001, "prompt_seconds": 0.008, "output_seconds": 0.258, "ok": true, "error": ""}}

data: {"type": "STEP_STARTED", "timestamp": 1793182837071, "stepName": "ask", "metadata": {"label": "Ask for the missing inputs", "kind": "ask", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793182837071, "stepName": "ask", "metadata": {"seconds": 0.0}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793182837071, "messageId": "3125588087", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793182837071, "messageId": "3125588087", "delta": "Before I design, I need 2 inputs. Each has a proposed default: accept it or change it."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793182837071, "messageId": "3125588087"}

data: {"type": "CUSTOM", "timestamp": 1793182837071, "name": "clarification", "value": {"intro": "Before I design, I need 2 inputs. Each has a proposed default: accept it or change it.", "questions": [{"id": "dh_supply_return_c", "label": "Heating network, supply and return", "hint": "Typical for a new network.", "options": ["80/50 °C", "70/40 °C", "60/30 °C"], "default": "70/40 °C", "required": true}, {"id": "dc_supply_return_c", "label": "Cooling network, supply and return", "hint": "Typical for building cooling.", "options": ["6/12 °C", "8/14 °C", "16/19 °C"], "default": "6/12 °C", "required": true}]}}

data: {"type": "RUN_FINISHED", "timestamp": 1793182837072, "threadId": "u-clarify", "runId": "da8ea9e8b9", "outcome": {"type": "interrupt", "interrupts": [{"id": "da8ea9e8b9-ask", "reason": "clarification"}]}, "usage": [{"model": "qwen3:1.7b", "provider": "ollama", "inputTokens": 543, "outputTokens": 69, "totalTokens": 612}], "result": {"behaviour": "clarify", "asked": ["dh_supply_return_c", "dc_supply_return_c"], "answer": "Before I design, I need 2 inputs. Each has a proposed default: accept it or change it.", "ungrounded": [], "dropped": ["annual_heat_gwh=40 (not written as a demand)", "annual_cool_gwh=40 (not written as a demand)"], "verified": null, "intent": "design", "language": "en", "screened": false, "seconds": 0.278, "llm_calls": 1, "prompt_tokens": 543, "output_tokens": 69, "load_seconds": 0.001, "prompt_seconds": 0.008, "output_seconds": 0.258, "tool_calls": 0, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "intake_v1"}}

`;export{e as default};