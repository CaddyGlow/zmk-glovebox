# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path


# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.insert(0, str(Path("..").resolve()))

# -- Project information -----------------------------------------------------

project = "Glovebox"
copyright = "2024, Glovebox Contributors"
author = "Glovebox Contributors"

# The full version, including alpha/beta/rc tags
try:
    from glovebox._version import __version__

    release = __version__
    version = ".".join(__version__.split(".")[:2])  # X.Y from X.Y.Z
except ImportError:
    # Fallback if version file doesn't exist
    release = "0.0.1"
    version = "0.0"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension modules here. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    # Core Sphinx extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    # Third-party extensions
    "autoapi.extension",  # sphinx-autoapi
    "myst_parser",  # MyST parser for Markdown
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "implementation/deprecated/**",
    "**/workspace_repo_*/**",  # Exclude workspace directories
]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Theme options
html_theme_options = {
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
    "titles_only": False,
}

# -- Extension configuration -------------------------------------------------

# Napoleon settings for docstring parsing
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# AutoAPI configuration
autoapi_dirs = ["../glovebox"]
autoapi_type = "python"
autoapi_template_dir = "_templates/autoapi"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
    "special-members",
]
autoapi_ignore = [
    "*migrations*",
    "*tests*",
    "*test_*",
    "*conftest*",
    "*/workspace_repo_*/*",
    "*/__pycache__/*",
]
autoapi_python_class_content = "both"
autoapi_member_order = "groupwise"
autoapi_root = "api"
autoapi_add_toctree_entry = False
autoapi_keep_files = True

# Autodoc configuration
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}

# Autosummary configuration
autosummary_generate = True

# Intersphinx configuration
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "rich": ("https://rich.readthedocs.io/en/stable/", None),
}

# MyST configuration
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

# TODO extension
todo_include_todos = True
todo_emit_warnings = True

# Suppress specific warnings
suppress_warnings = [
    "autoapi.python_import_resolution",
    "misc.highlighting_failure",
]

# Master document
master_doc = "index"
