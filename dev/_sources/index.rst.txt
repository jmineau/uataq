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

.. image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: License

.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.22900090.svg
   :target: https://doi.org/10.5281/zenodo.22900090
   :alt: DOI

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Ruff

.. image:: https://img.shields.io/badge/types-pyrefly-blue.svg
   :target: https://pyrefly.org
   :alt: Pyrefly

uataq reads UATAQ data: the greenhouse-gas and air-quality measurements from
fixed sites and from TRAX trains and buses, out of the archives that the Lin and
Horel research groups keep on CHPC. It is written for members of the groups who
work on CHPC, where the archive is. Start with :doc:`installation`, then
:doc:`first_month`.

.. toctree::
   :maxdepth: 1
   :caption: Getting started

   installation
   first_month

.. toctree::
   :maxdepth: 1
   :caption: Guides

   what_data_exists
   reading_data
   errors

.. toctree::
   :maxdepth: 1
   :caption: Reference

   sites_and_instruments
   columns
   input_parameters
   config

.. toctree::
   :maxdepth: 1
   :caption: API reference

   functions_and_modules
   laboratory
   sites

.. toctree::
   :maxdepth: 1

   contributing

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
