.. currentmodule:: uataq

Utah Atmospheric Trace-gas and Air Quality (UATAQ)
==================================================

.. image:: https://github.com/jmineau/uataq/actions/workflows/tests.yml/badge.svg
   :target: https://github.com/jmineau/uataq/actions/workflows/tests.yml
   :alt: Tests

.. image:: https://github.com/jmineau/uataq/actions/workflows/docs.yml/badge.svg
   :target: https://github.com/jmineau/uataq/actions/workflows/docs.yml
   :alt: Documentation

.. image:: https://github.com/jmineau/uataq/actions/workflows/quality.yml/badge.svg
   :target: https://github.com/jmineau/uataq/actions/workflows/quality.yml
   :alt: Code Quality

.. image:: https://codecov.io/gh/jmineau/uataq/branch/main/graph/badge.svg
   :target: https://codecov.io/gh/jmineau/uataq
   :alt: Code Coverage

.. image:: https://badge.fury.io/py/uataq.svg
   :target: https://badge.fury.io/py/uataq
   :alt: PyPI version

.. image:: https://img.shields.io/pypi/pyversions/uataq.svg
   :target: https://pypi.org/project/uataq/
   :alt: Python Version

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff

.. image:: https://img.shields.io/badge/pyright-checked-brightgreen.svg
   :target: https://github.com/microsoft/pyright
   :alt: Pyright

.. toctree::
   :maxdepth: 1

   installation
   quickstart
   general
   laboratory
   filesystem
   sites
   instruments
   contributing

Naming Convention
-----------------

I chose `UATAQ` as the name for the package because it is the most encompassing
name for the groups currently involved in the project.

Designing a user-friendly package is a challenge because the data is collected
by multiple research groups, each with their own naming conventions and data formats.
The package must be able to handle all of these different formats and provide a 
onsistent interface for the user.

I have defined a set of [standardized column names](columns.md) that each
groupspace module must define a :obj:`column_mapping` dictionary that maps the group's column
names to the standardized names when using the `GroupSpace.standardize_data` method.

Contents
--------

.. autosummary::

   laboratory
   get_site
   read_data
   get_obs

Contributing
============

See the `CONTRIBUTING.md <https://github.com/jmineau/uataq/blob/main/CONTRIBUTING.md>`_ file for guidelines on how to contribute to this project.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
