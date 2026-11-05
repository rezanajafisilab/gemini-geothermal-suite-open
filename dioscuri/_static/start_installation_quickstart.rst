.. _quickstart-installation:

Quick Start (Beginners)
===========================

This page gives you the shortest path to get GEMINI Digital Twin fully running locally: the GUI,
the framework/models, the Celery-backed analysis tabs, report upload/download, and the AI Chat
Assistant -- see :ref:`gemini-suite-setup` for full detail on every service and environment
variable.

Minimum requirements
----------------------

* **Docker Desktop**, running (https://docs.docker.com/desktop/)
* **Python 3.11**
* **Poetry** (https://python-poetry.org/) -- installed automatically by the ``ci`` scripts below,
  or manually with ``pip install poetry``
* **Git** (https://git-scm.com/downloads)

Steps
------

1. Clone the repository:

.. code-block:: bash

   git clone https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open.git
   cd gemini-geothermal-suite-open

2. Create your environment file from the template:

.. code-block:: bash

   cp .env.template .env

Open ``.env`` and fill it in. This is a complete, working example -- copy it in and only change
the passwords:

.. code-block::

   GEMINI_PLANT=geothermal_example
   GEMINI_FRONTEND_PORT=5101
   GEMINI_ADMIN_EMAIL=admin@example.com
   GEMINI_ADMIN_NAME=admin
   GEMINI_ADMIN_PASSWORD=change-me

   GEMINI_MYSQLDB_URL=localhost
   MYSQL_ROOT_PASSWORD=root
   MYSQL_DATABASE=gemini_database

   INFLUXDB_URL=http://localhost:8086
   INFLUXDB_ORG=gemini
   INFLUXDB_BUCKET=gemini
   INFLUXDB_USERNAME=admin
   INFLUXDB_PASSWORD=change-me-too
   DOCKER_INFLUXDB_INIT_MODE=setup
   DOCKER_INFLUXDB_INIT_ORG=gemini
   DOCKER_INFLUXDB_INIT_BUCKET=gemini
   DOCKER_INFLUXDB_INIT_USERNAME=admin
   DOCKER_INFLUXDB_INIT_PASSWORD=change-me-too

   CELERY_BROKER_URL=redis://localhost:6379/0
   CELERY_RESULT_BACKEND=redis://localhost:6379/0

   MONGODB_HOST=localhost
   MONGODB_PORT=27017
   MONGODB_USERNAME=admin
   MONGODB_PASSWORD=change-me
   MONGO_INITDB_ROOT_USERNAME=admin
   MONGO_INITDB_ROOT_PASSWORD=change-me

   LLM_MODEL_VERSION=llama3.2
   EMBED_MODEL_VERSION=snowflake-arctic-embed
   TRANSLATION_LLM_MODEL=zongwei/gemma3-translator:4b
   CHROMADB_GUI_HOST=localhost
   CHROMADB_GUI_PORT=8000
   OLLAMA_GUI_HOST=localhost
   OLLAMA_GUI_PORT=11434
   OLLAMA_HOST=0.0.0.0:11434

   GRAFANA_URL=http://localhost:3000
   GF_SERVER_ROOT_URL=http://localhost:5101/grafana/
   GF_SERVER_SERVE_FROM_SUB_PATH=true
   GF_SECURITY_ALLOW_EMBEDDING=true
   GF_SECURITY_ADMIN_USER=admin
   GF_SECURITY_ADMIN_EMAIL=admin@example.com
   GF_SECURITY_ADMIN_PASSWORD=change-me

.. important::
   If you ever start the stack, then change a ``MYSQL_*`` or ``DOCKER_INFLUXDB_INIT_*`` value,
   reset the volumes before restarting (``docker compose down -v`` then ``docker compose up -d``)
   -- these only take effect the first time each container initializes its data. See
   :ref:`troubleshooting` for the full explanation and other common errors.

3. Start the supporting services:

.. code-block:: bash

   docker compose up -d

4. Install Python dependencies:

.. code-block:: bash

   pip install poetry
   poetry install

or ``ci\windows\run_installation.bat`` (Windows) / ``bash ci/linux/run_installation.sh``
(Linux/macOS).

5. Run the web app:

.. code-block:: bash

   poetry run python src/gemini_interface/app.py

or ``ci\windows\run_gemini_gui.bat`` on Windows. Open ``http://localhost:5101`` (or your
``GEMINI_FRONTEND_PORT``) and log in with ``GEMINI_ADMIN_EMAIL``/``GEMINI_ADMIN_PASSWORD``.

6. Populate time-series data -- the Timeseries Viewer stays empty until the **framework** module
   has processed at least one batch of plant data:

.. code-block:: bash

   poetry run python src/gemini_framework/app.py

or ``ci\windows\run_gemini_module.bat`` / ``bash ci/linux/run_gemini_module.sh``. Re-run any time
you want to process newer data.

7. Start a Celery worker -- **required** for most analysis tabs (ESP, production well
   performance, injection well monitoring, well integrity monitoring); those run as Celery tasks
   and will queue but never complete without a worker:

.. code-block:: bash

   celery --app src.gemini_interface.blueprint.celerytasks.celery worker --loglevel=info

or ``ci\windows\run_celery.bat``. Optionally monitor tasks with Flower
(``ci\windows\run_flower.bat``).

8. Pull the Ollama models -- **required** for the AI Chat Assistant to work; the models
   configured above (``LLM_MODEL_VERSION``, ``EMBED_MODEL_VERSION``, ``TRANSLATION_LLM_MODEL``)
   must be downloaded into the ``ollama`` container before first use:

.. code-block:: bash

   ci\windows\run_ollama_models.bat        # Windows
   bash ci/linux/run_ollama_models.sh       # Linux/macOS

See :ref:`chat-assistant-setup` for pulling models manually and other model options.

Need more?
-----------

* Every service, environment variable, hostname rules, optional features (reports, AI Chat
  Assistant), and troubleshooting: :ref:`gemini-suite-setup` (see also :ref:`troubleshooting`)
* Local development workflow (tests, linting, docs): :ref:`local-development-setup`

