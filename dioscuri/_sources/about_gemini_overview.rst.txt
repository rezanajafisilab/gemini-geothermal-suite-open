GEMINI architecture
===========================

GEMINI is a software framework for modeling and real-time monitoring of
geothermal assets. This page gives a high-level overview of the platform
architecture. The architecture is described from two perspectives:

* **Functional architecture**: platform layers and their responsibilities
* **Technical architecture**: software components and infrastructure

Functional architecture
---------------------------

:numref:`fig-func-architecture` shows the functional layers of GEMINI and their
interactions. The platform consists of:

*   The framework layer
*   The model layer
*   The module layer
*   The application layer
*   The project layer
*   The database layer
*   A Graphical User Interface (GUI)

The following subsections describe each layer.


.. _fig-func-architecture:

.. figure:: images/gemini_functional_architecture_V2_headers_only.png
    :width: 100%
    :align: center

    Overview of the functional architecture of the GEMINI digital twin framework.



Framework layer
~~~~~~~~~~~~~~~~~~

The framework is the foundation of GEMINI. It provides shared services that
connect all internal and external components. Examples include scheduling,
database I/O, and project lifecycle actions (create, open, save).


Model layer
~~~~~~~~~~~~~~~~~~
The model layer contains computational models used by GEMINI. A model maps
inputs to outputs and can be:

* **static** (pure input-output)
* **dynamic** (state is updated at each execution)

Examples include well VLP, fluid PVT, and erosion calculations.


Module layer
~~~~~~~~~~~~~~~~~~
A module is a scheduled collection of one or more models that provides a
specific utility. Modules run automatically at fixed intervals (for example,
every 5 minutes or hourly). A typical module computes KPIs such as injectivity
index using recent data.


Application layer
~~~~~~~~~~~~~~~~~~
Like modules, applications combine models and logic, but they run **on demand**.
Applications are designed for interactive analysis, parameter tuning, and
scenario exploration.

In practice, modules are mostly "set and run", while applications require direct
user interaction.


Project layer
~~~~~~~~~~~~~~~~~~
A project is a saved digital twin configuration for a specific system scope:
full doublet, single well, or even a single asset (for example an ESP). Project
settings and parameters are persisted and restored when reopened.


Database layer
~~~~~~~~~~~~~~~~~~
The database layer contains:

* plant data (real-time measurements)
* calculated data
* plant/project parameters
* user/account information

Database implementations can differ per plant and are therefore external to the
generic GEMINI core.


Graphical User Interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The GUI (Graphical User Interface) is the visual interaction layer on top of
GEMINI.


Internal vs. external layers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
GEMINI distinguishes between *internal* (general-purpose) and *external*
(plant-specific) layers. In :numref:`fig-func-architecture`, internal layers use
solid outlines and external layers use dashed outlines. Internal layers are part
of the open-source scope.







Technical architecture
---------------------------



:numref:`fig-tech-architecture` shows the software packages and tools that
implement GEMINI functionality. The technical architecture includes:

*   The back-end
*   The front-end
*   The workflow manager
*   The databases

The subsections below describe each part.


.. _fig-tech-architecture:

.. figure:: images/gemini_technical_architecture.png
    :width: 100%
    :align: center

    Overview of the technical architecture of the GEMINI digital twin framework.




Back-end
~~~~~~~~~~~~~~~~~~~~~~~~~
The back-end performs data processing, scheduling, and model calculations. It
connects the functional layers and exposes services to the front-end. The core
back-end is implemented in Python.

Front-end/back-end communication is handled using
`Flask <https://flask.palletsprojects.com/en/3.0.x/>`_.

Front-end
~~~~~~~~~~~~~~~~~~~~~~~~~
The front-end includes the web interface used by end users. It is built with
HTML/CSS (Bootstrap) and JavaScript (React), and is hosted in an Azure-based
deployment. Authentication secures access to back-end services.


Workflow manager
~~~~~~~~~~~~~~~~~~~~~~~~~
The workflow manager ensures periodic data retrieval and scheduled module
execution. GEMINI uses `Celery <https://docs.celeryq.dev/en/stable/index.html>`_
for this purpose.


Databases
~~~~~~~~~~~~~~~~~~~~~~~~~
The database layer provides access to plant data and parameter storage. Time
series streaming is typically handled with
`InfluxDB <https://www.influxdata.com/>`_, and relational configuration data with
`MySQL <https://www.mysql.com/>`_. Future integration with
`OSDU <https://osduforum.org/>`_ is planned.









