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
    # plasmapy extensions & setups
    #"plasmapy_sphinx.theme",
    #"plasmapy_sphinx.ext.autodoc",
    #"plasmapy_sphinx.ext.directives",
    # other 3rd party extensions
    #"IPython.sphinxext.ipython_console_highlighting",
    #"nbsphinx",
    #"notfound.extension",
    #"sphinx.ext.duration",
    #"sphinx.ext.extlinks",
    #"sphinx.ext.graphviz",
    #"sphinx.ext.intersphinx",
    #"sphinx.ext.mathjax",
    #"sphinx.ext.napoleon",
    #"sphinx.ext.todo",
    #"sphinx.ext.viewcode",
    #"sphinx_changelog",
    #"sphinx_copybutton",
    #"sphinx_gallery.load_style",
    #"sphinx_issues",
    #"sphinx_reredirects",
    #"sphinx_tabs.tabs",
    #"sphinx_toolbox.collapse",
    #"sphinx_toolbox.rest_example",
    #"sphinxcontrib.bibtex",
    #"sphinxemoji.sphinxemoji",
    #"sphinxcontrib.globalsubs",
]

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
html_static_path = ["_static"]
