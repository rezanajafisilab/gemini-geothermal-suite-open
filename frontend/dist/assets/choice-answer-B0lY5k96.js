var e=`data: {"type": "RUN_STARTED", "timestamp": 1793260460000, "threadId": "w-choice", "runId": "f6c0de5e06"}

data: {"type": "STEP_STARTED", "timestamp": 1793260460001, "stepName": "docs", "metadata": {"label": "Search the documents", "kind": "tool", "code": "search_docs('Explain how to install GEMINI')"}}

data: {"type": "TOOL_CALL_START", "timestamp": 1793260460151, "toolCallId": "a7b8c9d0e1", "toolCallName": "search_docs"}

data: {"type": "TOOL_CALL_ARGS", "timestamp": 1793260460151, "toolCallId": "a7b8c9d0e1", "delta": "{\\"query\\": \\"Explain how to install GEMINI\\", \\"threadId\\": \\"w-choice\\", \\"only_attached\\": false}"}

data: {"type": "TOOL_CALL_END", "timestamp": 1793260460151, "toolCallId": "a7b8c9d0e1"}

data: {"type": "TOOL_CALL_RESULT", "timestamp": 1793260460151, "messageId": "a7b8c9d0e1-result", "toolCallId": "a7b8c9d0e1", "content": "{\\"backend\\": \\"gemini-chroma\\", \\"passages\\": [{\\"source\\": \\"src/gemini_documentation/source/start_installation_quickstart.rst\\", \\"section\\": \\"Quick Start (Beginners) > Steps\\", \\"text\\": \\"1. Clone the repository: git clone https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open.git, cd gemini-geothermal-suite-open. 2. Create your environment file from the template: cp .env.template .env. 3. docker compose up -d. 4. Install Python dependencies: pip install poetry, poetry install, or bash ci/linux/run_installation.sh (Linux/macOS).\\", \\"score\\": 0.8123, \\"suspicious\\": false}, {\\"source\\": \\"src/gemini_documentation/source/start_installation_quickstart.rst\\", \\"section\\": \\"Quick Start (Beginners) > Minimum requirements\\", \\"text\\": \\"Docker Desktop, running. Python 3.11. Poetry, installed automatically by the ci scripts below, or manually with pip install poetry. Git.\\", \\"score\\": 0.7934, \\"suspicious\\": false}]}", "role": "tool"}

data: {"type": "STEP_FINISHED", "timestamp": 1793260460153, "stepName": "docs", "metadata": {"passages": 2, "suspicious": 0, "backend": "gemini-chroma", "seconds": 0.002}}

data: {"type": "STEP_STARTED", "timestamp": 1793260460154, "stepName": "answer", "metadata": {"label": "Write the answer", "kind": "model", "code": null}}

data: {"type": "STEP_FINISHED", "timestamp": 1793260462594, "stepName": "answer", "metadata": {"decided_by": "model", "model": "qwen3.5:9b", "device": "gpu", "tokens": 2682, "understood": "You want the steps to install GEMINI locally.", "kind": "answer", "scope": "project", "seconds": 2.44}}

data: {"type": "CUSTOM", "timestamp": 1793260462594, "name": "usage", "value": {"purpose": "answer", "model": "qwen3.5:9b", "prompt_tokens": 2540, "output_tokens": 142, "seconds": 2.44, "load_seconds": 0.002, "prompt_seconds": 0.732, "output_seconds": 1.659, "ok": true, "error": ""}}

data: {"type": "TEXT_MESSAGE_START", "timestamp": 1793260462595, "messageId": "8e4a3b2c77", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260462635, "messageId": "8e4a3b2c77", "delta": "GEMINI's quick start needs Docker Desktop running, Python 3.11, Poetry and Git. Then: clone gemini-geothermal-suite-open, copy .env.template "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260462675, "messageId": "8e4a3b2c77", "delta": "to .env and fill in the passwords, start the services with docker compose up -d, and install "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260462715, "messageId": "8e4a3b2c77", "delta": "the Python packages with poetry install (or ci/linux/run_installation.sh). The full list of services is in the setup "}

data: {"type": "TEXT_MESSAGE_CONTENT", "timestamp": 1793260462755, "messageId": "8e4a3b2c77", "delta": "guide."}

data: {"type": "TEXT_MESSAGE_END", "timestamp": 1793260462756, "messageId": "8e4a3b2c77"}

data: {"type": "CUSTOM", "timestamp": 1793260462757, "name": "answer", "value": {"understood": "You want the steps to install GEMINI locally.", "kind": "answer", "scope": "project", "used": ["doc1", "doc2"], "model": "qwen3.5:9b", "device": "gpu", "fallback": false, "corrections": []}}

data: {"type": "CUSTOM", "timestamp": 1793260462758, "name": "sources", "value": [{"source": "src/gemini_documentation/source/start_installation_quickstart.rst", "section": "Quick Start (Beginners) > Minimum requirements", "text": "Docker Desktop, running. Python 3.11. Poetry, installed automatically by the ci scripts below, or manually with pip install poetry. Git.", "score": 0.7934, "suspicious": false}, {"source": "src/gemini_documentation/source/start_installation_quickstart.rst", "section": "Quick Start (Beginners) > Steps", "text": "1. Clone the repository: git clone https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open.git, cd gemini-geothermal-suite-open. 2. Create your environment file from the template: cp .env.template .env. 3. docker compose up -d. 4. Install Python dependencies: pip install poetry, poetry install, or bash ci/linux/run_installation.sh (Linux/macOS).", "score": 0.8123, "suspicious": false}]}

data: {"type": "CUSTOM", "timestamp": 1793260462759, "name": "suggestions", "value": ["Which parts of GEMINI do you use?", "Design heating and cooling for this district"]}

data: {"type": "RUN_FINISHED", "timestamp": 1793260462760, "threadId": "w-choice", "runId": "f6c0de5e06", "outcome": {"type": "success"}, "usage": [{"model": "qwen3.5:9b", "provider": "ollama", "inputTokens": 2540, "outputTokens": 142, "totalTokens": 2682}], "result": {"asked": [], "ungrounded": [], "dropped": [], "verified": null, "language": "en", "screened": false, "seconds": 2.759, "llm_calls": 1, "calls": ["answer: qwen3.5:9b"], "prompt_tokens": 2540, "output_tokens": 142, "load_seconds": 0.004, "prompt_seconds": 0.732, "output_seconds": 1.659, "tool_calls": 1, "cache_hits": 0, "tool_errors": 0, "left_out": [], "user_turns": 1, "model": "qwen3:1.7b", "prompt_version": "answer_v1", "behaviour": "answer", "answer": "GEMINI's quick start needs Docker Desktop running, Python 3.11, Poetry and Git. Then: clone gemini-geothermal-suite-open, copy .env.template to .env and fill in the passwords, start the services with docker compose up -d, and install the Python packages with poetry install (or ci/linux/run_installation.sh). The full list of services is in the setup guide.", "reasoning": false, "decided_by": {"answer": "model"}, "intent": "explain"}}

`;export{e as default};