Developer documentation
=======================

    `Last updated: December 2025`

If you are interested in learning about how the NexusLIMS back-end works or
adding new features, these instructions should get you up and running with a
development environment that will allow you to modify how the code operates.

Currently, running the NexusLIMS record building back-end code is only
supported and tested on Linux. It may run on MacOS or other UNIX environments,
but is known for sure not to work on Windows due to some specific
implementation choices.

Installation
------------

NexusLIMS uses the `uv <https://docs.astral.sh/uv/>`_ framework
to manage dependencies and create reproducible deployments. This means that
installing the ``nexusLIMS`` package will require
`installing <https://docs.astral.sh/uv/getting-started/installation/>`_
``uv``. ``uv`` will automatically manage Python versions for you, so you don't need
to install Python separately. NexusLIMS requires Python 3.11 or 3.12.
Installing ``uv`` is usually as simple as:

.. code:: bash

   curl -LsSf https://astral.sh/uv/install.sh | sh

.. danger::
   Never run code downloaded straight from the internet just because someone
   tells you to! Make sure to download and inspect the script to ensure it
   doesn't do anything nasty before you run it.

Once ``uv`` is installed, clone the NexusLIMS |RepoLink|_ using ``git``,
and then change to the root folder of the repository. Running the following
``sync``  command will make ``uv`` install the dependencies specified
in the ``uv.lock`` file into a local python virtual environment (so they
don't interfere with other Python installations on your system). It will also
install the ``nexusLIMS`` Python package in "editable" mode so you can make
changes locally for development purposes and still run things.

.. code:: bash

   $ uv sync --extra dev

.. note::
   ``uv`` automatically creates virtual environments in a local ``.venv`` folder
   by default, keeping all project files in one directory. This eliminates the need
   for additional configuration that was required with other package managers.
   To see information about your current environment, you can run
   ``$ uv python list`` to see available Python versions or ``$ uv pip list``
   to see installed packages. This approach keeps the project
   files all in one directory, rather than having the Python virtualenv in your
   user folder somewhere else on the system. ``uv`` manages this automatically
   without requiring additional configuration.

Setting up the environment
--------------------------

To interact with the remote systems from which NexusLIMS harvests information,
it is necessary to provide credentials for authentication and the paths in which
to search for new data files and where to write dataset previews, as well as
the path to the :doc:`NexusLIMS database <database>`.
These values should be set by copying the ``.env.example`` file from the git
repository into a file named ``.env`` in the base directory (in the same folder
as the ``README.md`` and ``pyproject.toml`` files).
``nexusLIMS`` makes use of the
`dotenv <https://pypi.org/project/python-dotenv/>`_ library to dynamically
load variables from this file when running any ``nexusLIMS`` code.
As an example, the  ``.env`` file content should look something like the
following (substituting real credentials, of course). See the
environment variables :ref:`documentation <nexusLIMS-user>` for more
details.

.. code:: bash

    NX_CDCS_USER='username'
    NX_CDCS_PASS='password'
    NX_INSTRUMENT_DATA_PATH='/path/to/mmfnexus/mount'
    NX_DATA_PATH='/path/to/nexusLIMS/mount/mmfnexus'
    NX_DB_PATH='/path/to/nexusLIMS/nexuslims_db.sqlite'
    NX_NEMO_ADDRESS_1='https://path.to.nemo.com/api/'
    NX_NEMO_TOKEN_1='authentication_token'
    NX_NEMO_STRFTIME_FMT_1="%Y-%m-%dT%H:%M:%S%z"
    NX_NEMO_STRPTIME_FMT_1="%Y-%m-%dT%H:%M:%S%z"
    NX_NEMO_TZ_1="America/New_York"

Rather than using the ``.env`` file, each of these variables could also be set
in the environment some other way if you desire. For example, to use Gitlab
CI/CD tools, you would set these variables in your project's CI/CD settings
(see `their documentation <https://docs.gitlab.com/ee/ci/variables/>`_),
since you would not want to commit a ``.env`` file into a remote repository
that contains authorization secrets (the equivalent is available in Github,
as well).

Getting into the environment
----------------------------

Once the package is installed using ``uv``, the code can be used
like any other Python library within the resulting virtual environment.

``uv`` allows you to run a single command inside that environment by
using the ``uv run`` command from the repository:

.. code:: bash

   $ uv run python

To use other commands in the NexusLIMS environment, you can also "activate"
the environment using the ``$ source .venv/bin/activate`` command from within the cloned
repository. This will activate the virtual environment that ensures all commands will have
access to the installed packages and environment variables set appropriately.

Testing and Documentation
-------------------------

To run the complete test suite, use the provided shell script:

..  code-block:: bash

   $ ./scripts/run_tests.sh

This will run all tests with coverage reporting. To run specific tests:

..  code-block:: bash

   $ pytest tests/test_extractors.py

To build the documentation for the project, run:

..  code-block:: bash

   $ ./scripts/build_docs.sh

The documentation should then be present in the ``./_build/`` directory.

To generate matplotlib baseline figures for the tests, run:

..  code-block:: bash

   $ ./scripts/generate_mpl_baseline.sh

Building new records
--------------------

The most basic feature of the NexusLIMS back-end is to check the
:doc:`database <database>` for any logs (typically inserted by the
NEMO harvester) with a status of
``'TO_BE_BUILT'``. This can be accomplished simply by running the
:py:mod:`~nexusLIMS.builder.record_builder` module directly via:

..  code-block:: bash

    $ uv run nexuslims-process-records

This command will find any records that need to be built, build their .xml
files, and then upload them to the front-end CDCS instance. Consult the
record building :doc:`documentation <record_building>` for more details.

Using other features of the library
-----------------------------------

Once you are in a python interpreter (such as ``python``, ``ipython``,
``jupyter``, etc.) from the ``uv`` environment, you can access the
code of this library through the ``nexusLIMS`` package if you want to do other
tasks, such as extracting metadata or building previews images, etc.

For example, to extract the metadata from a ``.tif`` file saved on the
FEI Quanta, run the following code using the
:py:func:`~nexusLIMS.extractors.quanta_tif.get_quanta_metadata` function:

.. code:: python

   from nexusLIMS.extractors.quanta_tif import get_quanta_metadata
   meta = get_quanta_metadata("path_to_file.tif")

The ``meta`` variable will then contain a dictionary with the extracted
metadata from the file.


Contributing
------------

To contribute, please fork the repository, develop your addition on a
`feature branch <https://www.atlassian.com/git/tutorials/comparing-workflows/feature-branch-workflow>`_
within your forked repo, and submit a pull request to the ``main``
branch to have it included in the project. Contributing to the package
requires that every line of code is covered by a test case. This project uses
testing through the `pytest <https://docs.pytest.org/en/latest/>`_ library,
and features that do not pass the test cases or decrease coverage will not be
accepted until suitable tests are included (see the ``tests`` directory
for examples) and that the coverage of any new features is 100%.

.. note::

    In the public version of this repository, the included tests will not run
    due to the exclusion of test files and the expectation of certain files being
    present. If you are contributing, please make sure `your changes` are covered
    by tests, and the NexusLIMS developers will take care of integrating your
    PR fully in the code after it is accepted.

To get information about test coverage, you can use an IDE that includes coverage tracking
(such as `PyCharm <https://www.jetbrains.com/pycharm/>`_) or include the
``--cov`` flag when running the tests. To test the preview image generation,
the ``--mpl`` option should also be provided, together with the path to
the `"reference"` images that are tested against. For example:

.. code:: bash

   $ cd <path_to_repo>
   $ uv run ./scripts/run_tests.sh

   # =============================================== test session starts =========================
   # platform darwin -- Python 3.11.14, pytest-9.0.1, pluggy-1.6.0
   # Matplotlib: 3.10.7
   # Freetype: 2.6.1
   # rootdir: /Users/josh/git_repos/datasophos/NexusLIMS
   # configfile: pyproject.toml
   # plugins: mpl-0.17.0, cov-7.0.0
   # collected 303 items
   #                                                                                                        
   # tests/cli/test_process_records.py ............................                         [  9%]
   # tests/test___init__.py ........                                                        [ 11%]
   # tests/test___main__.py .                                                               [ 12%]
   # tests/test_cdcs.py .......                                                             [ 14%]
   # tests/test_config.py ...................                                               [ 20%]
   # tests/test_extractors/test_basic_metadata.py ..                                        [ 21%]
   # tests/test_extractors/test_digital_micrograph.py .........                             [ 24%]
   # tests/test_extractors/test_edax.py ..                                                  [ 25%]
   # tests/test_extractors/test_extractor_module.py .................                       [ 30%]
   # tests/test_extractors/test_fei_emi.py ........................                         [ 38%]
   # tests/test_extractors/test_quanta_tif.py ......                                        [ 40%]
   # tests/test_extractors/test_thumbnail_generator.py ...............................      [ 50%]
   # tests/test_harvesters/test_nemo_api.py .........................................       [ 64%]
   # tests/test_harvesters/test_nemo_connector.py ..............                            [ 68%]
   # tests/test_harvesters/test_nemo_utils.py .........                                     [ 71%]
   # tests/test_harvesters/test_reservation_event.py ......                                 [ 73%]
   # tests/test_instruments.py .................                                            [ 79%]
   # tests/test_record_builder/test_activity.py ........                                    [ 82%]
   # tests/test_record_builder/test_record_builder.py ......................                [ 89%]
   # tests/test_sessions.py ......                                                          [ 91%]
   # tests/test_utils.py .........................                                          [ 99%]
   # tests/test_version.py .                                                                [100%]
   #                                                                                        [100%]    
   # =============================================== tests coverage ==============================
   # _____________________________ coverage: platform darwin, python 3.11.14-final-0 _____________
   # 
   # Name                                          Stmts   Miss  Cover   Missing
   # ---------------------------------------------------------------------------
   # nexusLIMS/__init__.py                            18      0   100%
   # nexusLIMS/__main__.py                             3      0   100%
   # nexusLIMS/builder/__init__.py                     0      0   100%
   # nexusLIMS/builder/record_builder.py             197      0   100%
   # nexusLIMS/cdcs.py                                73      0   100%
   # nexusLIMS/cli/__init__.py                         0      0   100%
   # nexusLIMS/cli/process_records.py                129      0   100%
   # nexusLIMS/config.py                             153      0   100%
   # nexusLIMS/db/__init__.py                          7      0   100%
   # nexusLIMS/db/session_handler.py                  89      0   100%
   # nexusLIMS/extractors/__init__.py                103      0   100%
   # nexusLIMS/extractors/basic_metadata.py           14      0   100%
   # nexusLIMS/extractors/digital_micrograph.py      278      0   100%
   # nexusLIMS/extractors/edax.py                     33      0   100%
   # nexusLIMS/extractors/fei_emi.py                 200      0   100%
   # nexusLIMS/extractors/quanta_tif.py              237      0   100%
   # nexusLIMS/extractors/thumbnail_generator.py     402      0   100%
   # nexusLIMS/extractors/utils.py                   163      0   100%
   # nexusLIMS/harvesters/__init__.py                  5      0   100%
   # nexusLIMS/harvesters/nemo/__init__.py            33      0   100%
   # nexusLIMS/harvesters/nemo/connector.py          244      0   100%
   # nexusLIMS/harvesters/nemo/exceptions.py           2      0   100%
   # nexusLIMS/harvesters/nemo/utils.py               68      0   100%
   # nexusLIMS/harvesters/reservation_event.py       130      0   100%
   # nexusLIMS/instruments.py                         91      0   100%
   # nexusLIMS/schemas/__init__.py                     0      0   100%
   # nexusLIMS/schemas/activity.py                   173      0   100%
   # nexusLIMS/utils.py                              240      0   100%
   # nexusLIMS/version.py                              2      0   100%
   # ---------------------------------------------------------------------------
   # TOTAL                                          3087      0   100%
   # Coverage HTML written to dir tests/coverage
   # Coverage XML written to file coverage.xml
   # ============================= 303 passed in 33.51s =================
   # >>> elapsed time 39s
