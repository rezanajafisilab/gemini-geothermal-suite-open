Installation
===========================

.. tip::
   New to GEMINI or just want to try it out quickly? See the :ref:`quickstart-installation` page
   for a shorter, beginner-friendly version of these instructions. Come back here for full detail
   on every service, environment variable, and the local development workflow.

.. _gemini-suite-setup:

GEMINI Suite Setup
--------------------

GEMINI Digital Twin relies on several supporting services (Grafana, MySQL, InfluxDB, Redis,
MongoDB, ChromaDB and, optionally, Ollama) that are packaged together in this repository's
``docker-compose.yml``. Basic Docker knowledge is recommended -- see the official
`Docker documentation <https://docs.docker.com/>`_ for fundamentals.

Prerequisites:

* Docker Desktop: https://docs.docker.com/engine/install/
* Docker Compose: https://docs.docker.com/compose/install/

The full service definitions live in ``docker-compose.yml`` at the repo root. Here's what each
one is for:

#. Grafana
    Visualization platform for time-series dashboards and alerts. Embedded in the app's
    Timeseries Viewer tab.

#. MySQLDB
    Relational database for user, configuration, and project metadata. **Required.**

#. InfluxDB
    Time-series database used for geothermal operational data, written by the framework module
    and read by Grafana. **Required.**

#. Redis
    In-memory broker/backend for Celery task queues. **Required** for most analysis tabs (ESP,
    production well performance, injection well monitoring, well integrity monitoring) and the
    AI Chat Assistant.

#. MongoDB
    Document database used for uploaded report and document storage. Optional -- only needed for
    the report upload/download feature.

#. ChromaDB
    Vector database used by RAG workflows for semantic document retrieval. Optional -- only
    needed for the AI Chat Assistant (see :ref:`chat-assistant-setup`).

#. Ollama
    Runtime for local LLM and embedding model execution. Optional -- only needed for the AI Chat
    Assistant.

Starting the stack
~~~~~~~~~~~~~~~~~~

Run:

.. code-block:: bash

   docker compose up -d

After startup, open the GEMINI GUI on the configured frontend port.

.. _local-development-setup:

Local Development Setup
------------------------

Besides running the supporting services with the ``docker-compose.yml`` described above, the
GEMINI application itself can be run directly from source for development purposes, using Poetry
for dependency management.

Prerequisites
~~~~~~~~~~~~~

Make sure the following tools are installed on your machine before you start:

* **Python 3.11** (the project pins ``python = "^3.11"`` in ``pyproject.toml``)
* **Poetry** (https://python-poetry.org/) for dependency management (installed automatically by
  the install scripts below, or install manually with ``pip install poetry``)
* **Docker** and **Docker Compose** (to run the supporting services: Grafana, MySQL, InfluxDB,
  Redis, MongoDB, ChromaDB and Ollama)
* **Git** for cloning the repository

**Ollama** (https://ollama.com/) can be used to run the LLM/embedding models locally. The ``ollama`` service is included in ``docker-compose.yml`` and started
by default along with the other supporting services.

1. Clone the repository
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open.git
   cd gemini-geothermal-suite-open

2. Configure environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This repo uses a single ``.env`` file in the repo root, read both by Docker Compose (via
``env_file:`` in ``docker-compose.yml``) and automatically, via ``python-dotenv``, by every local
Python entry point (``src/gemini_interface/app.py``, ``src/gemini_framework/app.py``, and the
Celery worker). You do not need to manually export variables into your shell before running
``poetry run python src/gemini_interface/app.py`` -- ``.env`` is loaded automatically as soon as
the process starts.

Create it from the template:

.. code-block:: bash

   cp .env.template .env

On Windows (PowerShell):

.. code-block:: powershell

   Copy-Item .env.template .env

``.env.template`` is organized into a **Required** section (needed to run the GUI, framework
module, and Celery-backed analysis tabs) and an **Optional** section (report upload/download via
MongoDB; the AI Chat Assistant via ChromaDB/Ollama -- see :ref:`chat-assistant-setup`). Fill in
the Required section; leave the Optional section blank unless you use those features. See the
complete, working example (including the Optional section) in the :ref:`quickstart-installation`
guide.

``MONGODB_USERNAME``/``PASSWORD`` and ``MONGO_INITDB_ROOT_*`` can stay blank for a no-auth Mongo
setup (fine for local development) -- only fill them in (with matching values on both sides) if
you want Mongo authentication enabled. See :ref:`chat-assistant-setup` for the Ollama model
values and how to pull the models into the container.

.. warning::
   Hostnames (``GEMINI_MYSQLDB_URL``, ``MONGODB_HOST``, ``INFLUXDB_URL``, ``CELERY_BROKER_URL``,
   ``CHROMADB_HOST``, ``OLLAMA_HOST``) depend on where the app runs: use ``localhost`` (with the
   host-published port) when running with ``poetry run``, or the Docker Compose service name
   (e.g. ``mysqldb``, ``influxdb``, ``redis``) when running the app itself inside Docker. Mixing
   these up is the most common setup error -- see :ref:`troubleshooting`.

   ``GRAFANA_URL`` must also be reachable at that exact URL from your browser, or the Timeseries
   Viewer tab won't work. Never commit your ``.env`` file -- it's already excluded via
   ``.gitignore``.

See :ref:`troubleshooting` for common errors after changing ``.env``.

3. Install Python dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The project uses Poetry for dependency management. Convenience scripts are provided under
``ci/windows`` and ``ci/linux``.

**Windows:**

.. code-block:: powershell

   ci\windows\run_installation.bat        # runtime dependencies only
   ci\windows\run_installation_dev.bat    # runtime + development dependencies (tests, linters, docs)

**Linux/macOS:**

.. code-block:: bash

   bash ci/linux/run_installation.sh

These scripts run the equivalent of:

.. code-block:: bash

   python -m pip install --upgrade pip
   pip install poetry
   poetry lock
   poetry install            # add "--only main" to skip dev dependencies

4. Start the supporting services (Docker)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The suite depends on several backing services (Grafana, MySQL, InfluxDB, Redis, MongoDB,
ChromaDB, and optionally Ollama), defined in ``docker-compose.yml``. Start them with:

.. code-block:: bash

   docker compose up -d

or, using the provided script on Windows:

.. code-block:: powershell

   ci\windows\run_docker.bat

This will start Grafana (port 3000, dashboards), MySQL (port 3306, relational data), InfluxDB
(ports 8086/8088, time-series process data), Redis (port 6379, Celery broker/result backend),
MongoDB (port 27017, document storage) and ChromaDB (port 8000, vector store for the AI chat
assistant).

5. Run the application
~~~~~~~~~~~~~~~~~~~~~~

Start the Flask web interface (entry point is ``src/gemini_interface/app.py``):

.. code-block:: bash

   poetry run python src/gemini_interface/app.py

``.env`` is loaded automatically (via ``python-dotenv``) as soon as the process starts, so no
manual env export is required -- just make sure ``.env`` exists in the repo root and the Docker
Compose services from step 4 are already running.

The app reads ``GEMINI_FRONTEND_PORT`` from ``.env`` (defaults are only applied if the variable
is set) and listens on ``0.0.0.0``. Once running, open your browser at:

.. code-block::

   http://localhost:<GEMINI_FRONTEND_PORT>

.. warning::
   Always use ``http://localhost:<port>``, not ``http://127.0.0.1:<port>``. See "Accessing
   Grafana from the Timeseries Viewer" below for why this matters.

Log in using the ``GEMINI_ADMIN_EMAIL`` / ``GEMINI_ADMIN_PASSWORD`` configured in your ``.env``
file.

Accessing Grafana from the Timeseries Viewer
++++++++++++++++++++++++++++++++++++++++++++

The Timeseries Viewer tab embeds Grafana in an iframe pointing at ``GRAFANA_URL``. Two things
are required for this to work correctly:

1. **Use consistent hostnames.** Access the whole app via
   ``http://localhost:<GEMINI_FRONTEND_PORT>`` (not ``http://127.0.0.1:...``), matching the
   hostname used in ``GRAFANA_URL=http://localhost:3000``. Mismatched hostnames are treated as
   different origins by the browser, so Grafana's login session won't be visible inside the
   iframe and it will keep bouncing back to the login form.
2. **Configure Grafana's own InfluxDB data source using the Docker service name**, not
   ``localhost``. Grafana runs inside the ``gemini`` Docker network, so from inside the Grafana
   container, ``localhost`` refers to the Grafana container itself, not your host machine. When
   adding the InfluxDB data source in Grafana's UI (``Connections`` -> ``Data sources``), use
   ``http://influxdb:8086/`` as the URL.

Configuring a plant
~~~~~~~~~~~~~~~~~~~~

Plant-specific configuration lives under ``gemini-project/``. Each plant is a folder containing a
``plant.conf`` file and ``.param`` files describing individual assets (reservoir, wells, pumps,
heat exchangers, filters, degassers, etc.), plus a ``diagram.json`` describing the plant topology.
A ``_template`` folder is provided with blank templates for each asset type to help you set up a
new plant. Set ``GEMINI_PLANT`` in your ``.env`` to the name of the folder you want to load (e.g.
``geothermal_example``).

Running the framework module (populating time-series data)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The Flask app (``gemini_interface``) alone lets you log in and browse the UI, but the Timeseries
Viewer/dashboards stay empty until the **framework** module (``gemini_framework``) has processed
plant data into InfluxDB. It reads raw data for the configured ``GEMINI_PLANT``, runs the physics
model modules, and writes the results, then exits (it performs one processing step per run, not a
continuous loop). Run it any time you want to process the latest data, with the Docker services
already running:

.. code-block:: bash

   poetry run python src/gemini_framework/app.py

.. code-block:: powershell

   ci\windows\run_gemini_module.bat        # Windows

.. code-block:: bash

   bash ci/linux/run_gemini_module.sh      # Linux/macOS

Running tests, linting and formatting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Tests** (pytest with coverage):

.. code-block:: bash

   poetry run pytest -v --cov -p no:faulthandler
   # or
   ci\windows\run_test.bat        # Windows
   bash ci/linux/run_test.sh      # Linux

**Linting** (flake8, black, isort in check mode):

.. code-block:: powershell

   ci\windows\run_linter.bat

.. code-block:: bash

   bash ci/linux/run_linter.sh

**Auto-formatting** (black + isort, Windows only script provided):

.. code-block:: powershell

   ci\windows\run_formatting.bat

Background workers (Celery/Flower)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Celery is **required** for most interactive analysis tabs -- ESP analysis, production well
performance (VLP/IPR), injection well monitoring (Hall integral, skin lines), well integrity
monitoring (caliper log processing, corrosion prediction/optimization/forecasting), and the AI
Chat Assistant (RAG response generation). These all queue their work as Celery tasks against the
Redis broker started via Docker Compose; without a running worker, those actions queue but never
complete. You can skip this section only if you just want to browse the dashboard, plant
settings, and Timeseries Viewer without using those analysis features.

Start a Celery worker:

.. code-block:: powershell

   ci\windows\run_celery.bat

.. code-block:: bash

   celery --app src.gemini_interface.blueprint.celerytasks.celery worker --loglevel=info

Optionally, start the Flower monitoring dashboard to inspect Celery tasks:

.. code-block:: powershell

   ci\windows\run_flower.bat

.. code-block:: bash

   poetry run celery -A src.gemini_interface.blueprint.celerytasks.celery flower

.. _troubleshooting:

Troubleshooting
~~~~~~~~~~~~~~~~

**"Unknown database 'None'" (MySQL / SQLAlchemy) when running the app**
   ``MYSQL_DATABASE`` is blank in ``.env``. It's read by both the ``mysqldb`` container (to
   create the database) and the app (to build its connection string). Fill it in, then reset the
   volume (see below) since the container already initialized without it.

**InfluxDB "401 Unauthorized" when running the framework module**
   ``INFLUXDB_USERNAME``/``PASSWORD`` don't match what the ``influxdb`` container was actually
   initialized with (``DOCKER_INFLUXDB_INIT_USERNAME``/``PASSWORD``). This commonly happens after
   changing a password in ``.env`` without resetting the volume -- see below.

**InfluxDB "could not find bucket" (404) when running the framework module**
   ``INFLUXDB_BUCKET`` doesn't match ``DOCKER_INFLUXDB_INIT_BUCKET`` -- the app is asking for a
   bucket name that was never actually created in the container. Set ``INFLUXDB_BUCKET`` to the
   same value as ``DOCKER_INFLUXDB_INIT_BUCKET`` in ``.env`` (same rule applies to
   ``INFLUXDB_ORG``/``DOCKER_INFLUXDB_INIT_ORG``).

**MongoDB / report blueprint fails at app startup with** ``ValueError: invalid literal for int()``
   ``MONGODB_PORT`` was left blank. The report blueprint connects to MongoDB eagerly at import
   time (even if you never use the report feature), so ``MONGODB_HOST``/``MONGODB_PORT`` must
   always be filled in -- see the Required section of ``.env.template``.

**Reset Docker volumes after changing container-init variables**
   ``MYSQL_DATABASE``, ``MYSQL_ROOT_PASSWORD``, ``DOCKER_INFLUXDB_INIT_*`` and
   ``MONGO_INITDB_ROOT_*`` only take effect the **first** time their container initializes its
   data volume. If you change one of these after already starting the stack once, the container
   keeps its old state. Fix by resetting the volumes and restarting:

   .. code-block:: bash

      docker compose down -v
      docker compose up -d

**``getaddrinfo failed`` / "Can't connect to MySQL server on 'mysqldb'"**
   You used a Docker Compose service name (e.g. ``mysqldb``) as a hostname from a process running
   outside Docker. Use ``localhost`` instead when running the app with ``poetry run`` -- see the
   hostname rules under "Configure environment variables" above.

**Grafana keeps looping back to its login screen inside the Timeseries Viewer**
   Access the app via ``http://localhost:<port>``, not ``http://127.0.0.1:<port>``. See
   "Accessing Grafana from the Timeseries Viewer" above for the full explanation.

.. _chat-assistant-setup:

Chat Assistant Setup
--------------------

The Chat Assistant setup is mostly automatic. The Ollama service is hosted in
the optional Docker container named ``ollama``. Start this container before
using the RAG pipeline, for example by running:

.. code-block:: bash

   docker compose up -d

The provided compose file starts Ollama together with the other GEMINI
services. The ``ollama`` service must remain running for the RAG pipeline to be
functional.

Models must be pulled (downloaded) into the Ollama service before they can be
used. For a quick start on Windows, run
``ci\windows\run_ollama_models.bat``. A shell script for Linux/macOS is
also provided at ``ci/linux/run_ollama_models.sh``. The script checks that Docker is
reachable and that the ``ollama`` container is running, then pulls all three
recommended models: ``llama3.2``, ``snowflake-arctic-embed``, and
``zongwei/gemma3-translator:4b``. Run this script only after
``docker compose up`` completes.

If you prefer to pull models manually (or are on Linux/macOS), make sure the
``ollama`` container is running and then run the pull command inside the
container, for example:

.. code-block:: bash

   docker exec -it ollama ollama pull llama3.2

Replace ``llama3.2`` with the model you want to install. Only Ollama-supported
models can be used by the Chat Assistant.

Model configuration
~~~~~~~~~~~~~~~~~~~

The full RAG pipeline needs three models: an LLM for response generation, an
embedding model, and an LLM for translation. These models are configured in the
``.env`` file with the following parameters:

.. code-block:: bash

   LLM_MODEL_VERSION=llama3.2
   EMBED_MODEL_VERSION=snowflake-arctic-embed
   TRANSLATION_LLM_MODEL=zongwei/gemma3-translator:4b

You may choose other models, but only models supported by Ollama can be used.
If you change any configured model, pull that model into the ``ollama``
container as well. The translation model (``TRANSLATION_LLM_MODEL``) translates
non-English documents before embedding and generation.

Example (pull ``mistral-nemo``):

.. code-block:: bash

   docker exec -it ollama ollama pull mistral-nemo

Recommended Models
~~~~~~~~~~~~~~~~~~

The following models were validated during development and are recommended:

**Response Generation Models (LLM_MODEL_VERSION)**

- llama3.2
  A lightweight and fast model that provides good performance with low latency.

- mistral-nemo
  A larger and more accurate model that returns responses more slowly.

**Embedding Model (EMBED_MODEL_VERSION)**

- snowflake-arctic-embed
  The recommended model for generating embeddings used by the RAG pipeline.

**Translation Model (TRANSLATION_LLM_MODEL)**

- zongwei/gemma3-translator:4b
  The recommended model for translating non-English documents before they are
  embedded and used for response generation.

These defaults provide a practical balance between latency and response quality.





