# pylint: skip-file
# ruff: noqa

# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import logging
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path

# Suppress the specific database connection warning before any imports
# This filter will catch the warning at the source before it's logged
logging.basicConfig()
logging.getLogger("nexusLIMS.instruments").addFilter(
    lambda record: "Could not connect to database or retrieve instruments"
    not in record.getMessage()
)

# Add custom extensions directory to path (includes custom parsers)
sys.path.insert(0, os.path.abspath("_ext"))

import nexusLIMS.version


def autodoc_mock_settings(_):
    """Mock settings for autodoc to avoid validation errors."""
    # create dummy directories for data and instrument data
    tmp_dir = Path("/tmp")
    instrument_data_path = tmp_dir / "nx_instrument_data"
    instrument_data_path.mkdir(exist_ok=True)
    data_path = tmp_dir / "nx_data"
    data_path.mkdir(exist_ok=True)
    db_dir = tmp_dir / "nx_db"
    db_dir.mkdir(exist_ok=True)
    db_path = db_dir / "nexuslims_db.sqlite"
    # Create empty database file to satisfy path validation
    db_path.touch(exist_ok=True)

    os.environ["NX_INSTRUMENT_DATA_PATH"] = str(instrument_data_path)
    os.environ["NX_DATA_PATH"] = str(data_path)
    os.environ["NX_DB_PATH"] = str(db_path)

    # Set dummy CDCS environment variables (same as conftest.py)
    os.environ["NX_CDCS_URL"] = "https://cdcs.example.com"
    os.environ["NX_CDCS_TOKEN"] = "test-api-token-not-for-production"


# -- Project information -----------------------------------------------------

project = "NexusLIMS"
copyright = f"2025 - {datetime.now().year}, datasophos, LLC"
author = "datasophos, LLC"
numfig = False

# The full version, including alpha/beta/rc tags
actual_release = nexusLIMS.version.__version__

# Add PR number to context if available
pr_number = os.environ.get("PR_NUMBER")

# Determine version, release, and version_match for switcher.json
# version/release must be semver for PyData theme banner comparison
# version_match is used for dropdown highlighting only
deploy_target = os.environ.get("DEPLOY_TARGET")
if pr_number:
    # PR builds use "pr-<number>" as version
    version = f"pr-{pr_number}"
    release = f"pr-{pr_number}"
    version_match = f"pr-{pr_number}"
elif deploy_target == "stable":
    # Stable builds: use actual version number for banner comparison
    # Theme requires semver to suppress banner on preferred version
    version = actual_release
    release = actual_release
    version_match = actual_release
elif os.environ.get("GITHUB_REF") == "refs/heads/main":
    # Main branch builds use "dev" as version
    version = "dev"
    release = "dev"
    version_match = "dev"
else:
    # Release builds use full version (e.g., "2.1.0") to match switcher.json
    version = actual_release
    release = actual_release
    version_match = actual_release

# Debug output for version matching
print(f"[DEBUG] Sphinx conf.py version info:")
print(f"  release: {release}")
print(f"  version: {version}")
print(f"  version_match: {version_match}")
print(f"  deploy_target: {deploy_target}")
print(f"  PR_NUMBER: {pr_number}")
print(f"  GITHUB_REF: {os.environ.get('GITHUB_REF', 'not set')}")

# Pass version and PR info to templates
html_context = {
    "version": version,
    "release": release,
    "pr_number": pr_number,
    "version_match": version_match,
}

# Set html_baseurl for proper asset loading in subdirectories
# This is critical for GitHub Pages deployment to subdirectories like /pr-2/
base_url = "https://datasophos.github.io/NexusLIMS"
if pr_number:
    html_baseurl = f"{base_url}/pr-{pr_number}/"
elif os.environ.get("GITHUB_REF") == "refs/heads/main":
    html_baseurl = f"{base_url}/latest/"
else:
    # For local builds or stable releases, use relative paths
    html_baseurl = ""


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.doctest",  # Support for doctest-style examples
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",  # Creates .nojekyll file for GitHub Pages
    "sphinxcontrib.towncrier.ext",
    "sphinxcontrib.autodoc_pydantic",
    "sphinx_autodoc_typehints",
    "sphinx_design",
    "myst_parser",  # Support for Markdown files
    "sphinxcontrib.mermaid",  # Support for Mermaid diagrams
    "xsd_documenter",  # Custom XSD documentation extension with D3.js diagrams
    "autodoc2",  # Automatic API documentation generation
    "sphinx_copybutton",  # Add copy buttons to code blocks
    "config_field_detail",  # Render config field detail text from json_schema_extra
]

mermaid_d3_zoom = True

# -- Options for sphinx-copybutton -------------------------------------------
# Strip Python prompts (>>>, ...) and output when copying code blocks
copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True
# Don't copy output lines (lines that don't start with a prompt)
copybutton_only_copy_prompt_lines = True
# Remove prompts before copying
copybutton_remove_prompts = True

# MyST parser extensions - enable fieldlist for proper parameter/return rendering
myst_enable_extensions = [
    "fieldlist",  # Required for Napoleon-parsed docstrings
    "colon_fence",  # Allow ::: for RST directives (including doctest blocks)
    "attrs_block",  # Allow setting custom attributes via block quote
    "tasklist",  # Enable GitHub-style task lists (- [ ] / - [x])
    "html_image",  # Allow raw <video> and other HTML elements in markdown
]

# Napoleon settings - these affect docstring parsing
napoleon_use_ivar = True  # Fixes duplicate descriptions for class attributes
napoleon_use_admonition_for_examples = False  # Use code blocks for examples
napoleon_use_admonition_for_notes = False  # Use plain formatting for notes
napoleon_use_admonition_for_references = False  # Use plain formatting for refs

# Suppress MyST warnings about H1 headers in docstrings
# These come from code examples and literal blocks in docstrings
suppress_warnings = [
    "myst.header",  # Suppress "Document headings start at H2, not H1" warnings
]

autodoc_pydantic_model_show_json = False
autodoc_pydantic_model_show_config_summary = False
autodoc_pydantic_model_show_validator_members = False
autodoc_pydantic_model_show_validator_summary = False

# Options for sphinx_autodoc_typehints
set_type_checking_flag = True
typehints_fully_qualified = False

# use short form for type hint links
autodoc_typehints_format = "short"
python_use_unqualified_type_names = True

# -- Options for autodoc2 ----------------------------------------------------
autodoc2_packages = [
    {
        "path": "../nexusLIMS",
        "exclude_files": [
            "version.py",
        ],
        "exclude_dirs": [
            "dev_scripts",
            "dev",  # Excludes any 'dev' directory
        ],
    }
]
autodoc2_render_plugin = "myst"
autodoc2_output_dir = "api"
autodoc2_index_template = None  # We'll use a custom api.rst instead

# Control how __init__ is documented: "merge" appends __init__ docstring to class
# docstring and omits the method separately, "both" includes it as a distinct item
autodoc2_class_docstring = "both"

# Exclude private members (those starting with underscore like _logger)
autodoc2_hidden_objects = ["private", "inherited", "dunder"]

# Enable NumPy-style docstring support via custom Napoleon parser
# This uses the autodoc2_docstrings_parser.py file in the docs directory
autodoc2_docstring_parser_regexes = [
    # Process all docstrings with custom Napoleon parser to support NumPy-style
    (r".*", "autodoc2_docstrings_parser"),
]

# -- Options for towncrier_draft extension -----------------------------------
towncrier_draft_autoversion_mode = "draft"
towncrier_draft_include_empty = False
towncrier_draft_working_directory = "."

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix of source filenames.
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
highlight_language = "python"
# Set today to current timestamp in local timezone
today = datetime.now().strftime("%B %d, %Y at %I:%M %p %Z")
# Format: e.g., "December 28, 2025 at 02:30 PM PST"
pygments_style = "sphinx"
add_function_parentheses = True
# master_doc = 'index'

# # LXML does not use sphinx, so if you want to link to specific page,
# # you have to create a custom objects.inv file for that module
#   To do this, use the
# # example below to add the specific objects and links as needed (this
# # method from https://sphobjinv.readthedocs.io/en/latest/customfile.html)

#     import sphobjinv as soi
#     inv = soi.Inventory()
#     inv.project = 'lxml'
#     inv.version = lxml.__version__
#     o = soi.DataObjStr(name='lxml.etree._XSLTResultTree', domain='py',
#     role='class', priority='1', uri='xpathxslt.html#xslt', dispname='-')
#     inv.objects.append(o)
#     text = inv.data_file(contract=True)
#     ztext = soi.compress(text)
#     soi.writebytes('NexusMicroscopyLIMS/mdcs/nexusLIMS/'
#                    'doc/source/objects_lxml.inv', ztext)

intersphinx_mapping = {
    "python": ("https://docs.python.org/3.11/", None),
    "hyperspy": ("http://hyperspy.org/hyperspy-doc/current/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
    "matplotlib": ("https://matplotlib.org/stable/", None),
    "requests": ("https://requests.readthedocs.io/en/latest/", None),
    "PIL": ("https://pillow.readthedocs.io/en/stable/", None),
    "pytz": ("https://pythonhosted.org/pytz/", "pytz_objects.inv"),
    # use the custom objects.inv file above for LXML:
    "lxml": ("https://lxml.de/", "objects_lxml.inv"),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
}

html_theme = "pydata_sphinx_theme"


# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    ".git",
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "build",
    "changes/*.rst",
    "changes/*.md",
    "README.rst",
    "dev_scripts",
    "_ext/README.md",
]

# Keep warnings as “system message” paragraphs in the built documents.
# useful for easily seeing where errors are in the build files
keep_warnings = True


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_css_files = [
    "custom.css",
]

html_js_files = [
    "custom.js",
]

# html_title is not set - will use page title from first heading
html_short_title = ""
html_logo = "_static/nexusLIMS_bare_logo.png"
html_favicon = "_static/nexusLIMS_bare_logo.ico"
html_last_updated_fmt = "%b, %d, %Y"
html_use_smartypants = True
html_show_sourcelink = True
html_show_sphinx = False
html_show_copyright = True

html_extra_path = []

html_sidebars = {"**": ["sidebar-nav-bs"]}


html_theme_options = {
    "navbar_start": ["navbar-logo", "version-switcher"],
    "navbar_center": ["navbar-nav"],
    "switcher": {
        "json_url": "_static/switcher.json",
        "version_match": version_match,
    },
    "show_version_warning_banner": True,
    "logo": {
        "image_light": "_static/logo_horizontal_light.png",
        "image_dark": "_static/logo_horizontal_dark.png",
    },
    "github_url": "https://github.com/datasophos/NexusLIMS",
    "collapse_navigation": True,
    "header_links_before_dropdown": 5,
    "navbar_end": ["search-button", "theme-switcher", "navbar-icon-links"],
    "navbar_persistent": [],
    "icon_links": [
        {
            "name": "Datasophos",
            "url": "https://datasophos.co",
            "icon": "fa-solid fa-globe",
        },
    ],
}

rst_epilog = """
.. |RepoLink| replace:: repository
.. _RepoLink: https://github.com/datasophos/NexusLIMS
"""


# Note: autodoc2 replaces the old sphinx-apidoc approach
# API documentation is now generated automatically by autodoc2


# def build_plantuml(_):
#     from glob import glob
#     from plantuml import PlantUML
#     pl = PlantUML('http://www.plantuml.com/plantuml/img/')
#     cur_dir = os.path.normpath(os.path.dirname(__file__))
#     diagrams = os.path.join(cur_dir, 'diagrams')
#     output_path = os.path.join(cur_dir, '_static')
#     for f in glob(os.path.join(diagrams, '*uml')):
#         print(f)
#         out_name = os.path.splitext(os.path.basename(f))[0] + '.png'
#         out_f_path = os.path.join(output_path, out_name)
#         pl.processes_file(f, outfile=out_f_path)


# lines from intersphinx to ignore during api-doc autogeneration (so we don't
# get useless warning messages while the docs are being built
nitpick_ignore = [
    ("py:class", "function"),
    ("py:class", "optional"),
    ("py:class", "json.encoder.JSONEncoder"),
    ("py:class", "pathlib.Annotated"),
    # Pydantic type aliases not in their documentation
    ("py:class", "pydantic.EmailStr"),
    ("py:class", "pydantic.DirectoryPath"),
    ("py:class", "pydantic.FilePath"),
    # Pydantic settings internal types
    ("py:class", "pydantic_settings.sources.DotenvType"),
    ("py:class", "pydantic_settings.sources.PathType"),
    # lxml types not in custom objects.inv
    ("py:class", "lxml.etree.ElementBase"),
    # NexusLIMS type aliases (Annotated types can't be cross-referenced as classes)
    ("py:class", "nexusLIMS.schemas.pint_types.PintQuantity"),
    ("py:class", "nexusLIMS.exporters.registry.ExportStrategy"),
    # Pint library types (no intersphinx inventory available)
    ("py:class", "pint.Quantity"),
    # Pydantic exceptions (intersphinx doesn't resolve pydantic_core exceptions)
    ("py:exc", "pydantic.ValidationError"),
    # SQLModel does not have intersphinx inventory
    ("py:obj", "sqlmodel.SQLModel"),
]

# Regex-based nitpick ignore: suppress all unresolvable references to third-party
# libraries that don't publish intersphinx inventories (textual, rich, sqlmodel).
nitpick_ignore_regex = [
    (r"py:(obj|class)", r"textual\..*"),
    (r"py:(obj|class)", r"rich\..*"),
    (r"py:(obj|class)", r"sqlmodel\..*"),
    (r"py:(obj|class)", r"click\..*"),
]


def skip(app, what, name, obj, would_skip, options):
    if name == "__init__":
        return False
    # Skip logger attributes
    if name == "logger":
        return True
    return would_skip


def setup(app):
    app.connect("autodoc-skip-member", skip)
    app.connect("builder-inited", autodoc_mock_settings)

    # Patch autodoc2 to suppress Pydantic Field(...) values
    from autodoc2_docstrings_parser import patch_autodoc2_renderer

    patch_autodoc2_renderer()

    # Textual's App/Screen classes declare `DEFAULT_CSS: ClassVar[str]` on one line
    # then assign it on the next, causing astroid to emit two items with the same
    # full_name and triggering autodoc2.dup_item warnings.  Patch warn_sphinx to
    # swallow only those specific duplicate messages.
    import autodoc2.sphinx.extension as _a2ext

    _original_warn = _a2ext.warn_sphinx

    def _filtered_warn(msg, subtype=None, *args, **kwargs):
        if subtype and subtype.value == "dup_item" and "DEFAULT_CSS" in msg:
            return
        _original_warn(msg, subtype, *args, **kwargs)

    _a2ext.warn_sphinx = _filtered_warn

    # autodoc2 handles API doc generation automatically, no need for run_apidoc
    # app.connect('builder-inited', build_plantuml)
    # app.add_stylesheet("custom-styles.css")
