Installation
============

From Source
-----------

To install from source:

.. code-block:: bash

   git clone https://github.com/jmineau/uataq.git
   cd uataq
   pip install -e .

Development Installation
------------------------

For development, install with the development dependencies:

.. code-block:: bash

   git clone https://github.com/jmineau/uataq.git
   cd uataq
   uv sync                    # uataq and the dev tools
   uv run pre-commit install
   uv run just quality-check

See ``CONTRIBUTING.md`` for the full workflow.

Requirements
------------

- Python 3.11 or higher
