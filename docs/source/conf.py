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
    # built-in extensions
    "sphinx.ext.apidoc",  # generate API docs
    "sphinx.ext.autodoc",  # include documentation from docstrings
    "sphinx.ext.duration",  # show durations in documentation builds
    "sphinx.ext.intersphinx",  # link to other projects' documentation
    "sphinx.ext.mathjax",  # render math with MathJax
    "sphinx.ext.napoleon",  # support numpy and google style docstrings
    "sphinx.ext.viewcode",  # add links to highlighted source code
    # other 3rd party extensions
    "notfound.extension",  # adds a notfound 404 page
    "sphinx_click",  # document click command line tools
    "sphinx_copybutton",  # adds a button that enables code to be copied
]

# Generate API documentation pages with sphinx.ext.apidoc
apidoc_modules = [
    {
        "path": "../../src/pyfaradaycup",
        "destination": "api/",
        "separate_modules": True,
        "module_first": True,
    },
]

# Convert numpydoc type specifications like "int, optional" or
# "dict of str to list" into cross-references
napoleon_preprocess_types = True

intersphinx_mapping = {
    "numpy": ("https://numpy.org/doc/stable/", None),
    "python": ("https://docs.python.org/3/", None),
    "spacepy": ("https://spacepy.github.io/", None),
}

# Do not convert "--" into an en dash, so that command line options
# like --l0file are shown correctly
smartquotes_action = "qe"

templates_path = ["_templates"]
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]

# https://pydata-sphinx-theme.readthedocs.io/en/stable/user_guide/index.html
html_theme_options = {
    "github_url": "https://github.com/PlasmaPy/pyfaradaycup",
    "use_edit_page_button": True,
}

# Used by the "Edit on GitHub" button
html_context = {
    "github_user": "PlasmaPy",
    "github_repo": "pyfaradaycup",
    "github_version": "main",
    "doc_path": "docs/source",
}
