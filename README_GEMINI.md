[![Test workflow status](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/actions/workflows/python_test.yaml/badge.svg)](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/actions/workflows/python_test.yaml)
[![Lint workflow status](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/actions/workflows/python_lint.yaml/badge.svg)](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/actions/workflows/python_lint.yaml)
[![Docs workflow status](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/actions/workflows/docs.yaml/badge.svg)](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/actions/workflows/docs.yaml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

# GEMINI Geothermal Suite (Open Source)

Open-source repository for the GEMINI Geothermal Digital Twin platform, developed in the
context of the *Nieuwe Warmte Nu* innovation program.

## Documentation

Public documentation is built from `src/gemini_documentation` and published via GitHub Pages.

- Main branch docs:
  <https://gemini-digital-twin.github.io/gemini-geothermal-suite-open/main/>
- Branch docs (pattern):
  `https://gemini-digital-twin.github.io/gemini-geothermal-suite-open/<branch-name>/`

> Branch names are sanitized for deployment (`/` is replaced with `-`).

**New to GEMINI?** Start with the [Quick Start (Beginners)](https://gemini-digital-twin.github.io/gemini-geothermal-suite-open/main/start_installation_quickstart.html)
guide. For full detail on every service, environment variable, and the local development workflow,
see the [Installation guide](https://gemini-digital-twin.github.io/gemini-geothermal-suite-open/main/start_installation.html).

## Quick start

Requirements: **Docker Desktop**, **Python 3.11**, **Poetry**, **Git**.

```bash
git clone https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open.git
cd gemini-geothermal-suite-open
cp .env.template .env      # fill it in, see the Quick Start doc above for a working example
docker compose up -d       # starts MySQL, InfluxDB, Redis, MongoDB, ChromaDB, Grafana, Ollama
pip install poetry
poetry install
poetry run python src/gemini_interface/app.py
```

Open `http://localhost:<GEMINI_FRONTEND_PORT>` (default `5101`) and log in with the
`GEMINI_ADMIN_EMAIL`/`GEMINI_ADMIN_PASSWORD` set in `.env`. See the Quick Start doc above for
populating time-series data, starting Celery (required for most analysis tabs), and pulling the
Ollama models (required for the AI Chat Assistant).

## Development

Convenience scripts for installing dependencies, running the app/framework module, Celery/Flower,
tests, linting, formatting, and docs builds are provided under `ci/windows` and `ci/linux`. See
[CONTRIBUTING.md](./CONTRIBUTING.md) for the full workflow.

## Repository structure

- `src/gemini_framework` - framework/runtime logic (physics model modules, database connectors)
- `src/gemini_model` - domain and physics models
- `src/gemini_application` - application-level features
- `src/gemini_interface` - Flask web app (GUI, blueprints, Celery tasks)
- `src/gemini_documentation` - Sphinx docs source and build output
- `ci/windows`, `ci/linux` - convenience scripts to install dependencies, run the app/framework
  module, Celery/Flower, tests, linting, formatting, and docs builds

## CI and branch documentation workflow

- **Test** workflow: `.github/workflows/python_test.yaml`
- **Lint** workflow: `.github/workflows/python_lint.yaml`
- **Docs** workflow: `.github/workflows/docs.yaml`

On every push, the Docs workflow builds Sphinx docs and deploys to `gh-pages` under a
branch-specific folder, enabling side-by-side docs per branch.

## Versioning and release notes

- Versioning policy: [VERSIONING.md](./VERSIONING.md)
- Release notes / change history: [CHANGELOG.md](./CHANGELOG.md)

## Contribution

Please read [CONTRIBUTING.md](./CONTRIBUTING.md) before opening a pull request.

For bugs, feature requests, and technical discussions, open an
[issue](https://github.com/GEMINI-Digital-Twin/gemini-geothermal-suite-open/issues).

## License

This content is released under the [Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0) License.

## Acknowledgments
This project is sponsored by NWM innovatie: Datagedreven optimalisatie aardwarmtesystemen
(https://nwn.nu/projecten/innovaties/datagedreven-optimalisatie-aardwarmte-systemen)

Organization: TNO, Gaia Energy, HVC, Well Engineering Partners (WEP), Helin