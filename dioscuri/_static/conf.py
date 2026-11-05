"""Configuration file for the Sphinx documentation builder."""

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
import sys

project = "GEMINI Geothermal Digital Twin"
copyright = "2024, TNO"
author = "Ryvo Octaviano, Demetris Palochis, Leila Hashemi, Jonah Poort, Pejman Shoeibi Omrani"
version = os.getenv("DOCS_VERSION", os.getenv("GITHUB_REF_NAME", "local"))
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinxcontrib.jquery",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_autodoc_typehints",
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.extlinks",
]

templates_path = ["_templates"]
exclude_patterns = []
autoclass_content = "both"

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

# Enable numref
numfig = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = [""]
html_title = f"{project} ({version})"


sys.path.insert(0, os.path.abspath("../../"))
