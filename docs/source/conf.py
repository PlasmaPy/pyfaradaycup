"""Configuration file for the Sphinx documentation builder."""

# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "pyFaradayCup"
copyright = "2026, pyFaradayCup developers"  # ruff:ignore[A001]
author = "pyFaradayCup developers"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    # build-in extensions
    "sphinx.ext.apidoc",  # generate API docs
    "sphinx.ext.autodoc",  # include documentation from docstrings
    "sphinx.ext.duration",  # show durations in documentation builds
    "sphinx.ext.intersphinx",  # link to other projects' documentation
    "sphinx.ext.mathjax",  # render math with MathJax
    "sphinx.ext.napoleon",  # support numpy and google style docstrings
    "sphinx.ext.viewcode",  # add links to highlighted source code
    # other 3rd party extensions
    "notfound.extension",  # adds a notfound page
    "sphinxcontrib.bibtex",  # allows a bibliography via bibtex
    "sphinx_copybutton",  # adds a button that enables code to be copied
]

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
