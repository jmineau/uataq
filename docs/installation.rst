Installation
============

uataq reads the UATAQ data archive, and the archive lives on CHPC. So you
install and use uataq on CHPC. This page takes you from a fresh login to a
first read of real data in about five minutes.

Run the commands on a *login node*, the computer you land on when you ``ssh``
in. Login nodes are for light work: installing, editing, small reads. Bigger
jobs go to a compute node through *Slurm*, CHPC's job scheduler (see
:ref:`install-slurm`). If CHPC is new to you, start with
`CHPC's documentation <https://www.chpc.utah.edu/documentation/>`_.

What you need
-------------

* **A CHPC account in the** ``lin`` **group.** The archive is stored in the Lin
  group's space, and only members of the group can read it. The command
  ``groups`` lists your groups. If ``lin`` is not in the list, ask your advisor
  to have you added.
* **Python 3.11 or newer.** The Python you get when you log in (``python3``) is
  version 3.6.8, which is too old, and ``pip install`` fails on it with an
  unhelpful error (see :ref:`install-errors`). Step 2 loads a newer Python from
  CHPC.

That is all. You do not set any environment variable: uataq already knows where
the archive is.

Install
-------

1. **Check that you can read the archive.**

   .. code-block:: bash

      ls /uufs/chpc.utah.edu/common/home/lin-group20/measurements/data

   You should see one folder per site (``abrb``, ``asb``, ``csp``, and so on
   through ``wbb``). If you get an error instead, you do not have access yet.
   See `What you need`_.

2. **Load a newer Python.** CHPC installs its software as *modules*, and
   ``module load`` turns one on for your current session.

   .. code-block:: bash

      module load python
      python3 --version

   The second command should print ``Python 3.11`` or newer (``Python 3.11.3``
   in October 2026).

3. **Make a virtual environment.** A virtual environment is a folder with its
   own copy of Python and its own packages. What you install for uataq stays
   there and does not disturb anything else.

   .. code-block:: bash

      python3 -m venv ~/venvs/uataq
      source ~/venvs/uataq/bin/activate

   ``(uataq)`` now appears at the start of your prompt. The folder takes about
   0.4 GB. Keep it in your home directory, not in scratch: CHPC deletes scratch
   files that go unused for 60 days.

4. **Install uataq.** ``pip`` is Python's installer. uataq is not on PyPI (the
   usual package index), so you point pip at its GitHub repository.

   .. code-block:: bash

      pip install git+https://github.com/jmineau/uataq.git

   pip prints a long list while it works (about two minutes). The last line
   that matters starts with ``Successfully installed``. A notice about a new
   pip release after it is harmless.

5. **Check that it reads real data.** This reads one day of CO2 from the WBB
   site (William Browning, on the University of Utah campus):

   .. code-block:: bash

      python -c "import uataq; print(uataq.get_obs('WBB', 'CO2', time_range='2025-06-02'))"

   It takes a couple of seconds and prints a table:

   .. code-block:: text

                           CO2d_ppm_cal  CO2d_ppm_raw
      Time_UTC
      2025-06-02 00:00:01    431.852558      434.8026
      2025-06-02 00:00:11    431.612346      434.5594
      2025-06-02 00:00:21    431.812938      434.7615
      2025-06-02 00:00:30    431.939531      434.8889
      2025-06-02 00:00:40    432.130721      435.0815
      ...                           ...           ...
      2025-06-02 23:59:20    429.260744      431.1932
      2025-06-02 23:59:29    429.139982      431.0713
      2025-06-02 23:59:39    429.083069      431.0138
      2025-06-02 23:59:49    429.033293      430.9635
      2025-06-02 23:59:59    429.157492      431.0887

      [8390 rows x 2 columns]

   If you see a table like this, the install works and you can read the
   archive. (The row count can change if the data are reprocessed.)
   ``import uataq`` alone is not a good test: it can succeed even when the
   archive is out of reach, so this step reads some data.

Next, read the :doc:`quickstart`.

Other Pythons
^^^^^^^^^^^^^

``module load python`` gives CHPC's default Python. Any version from 3.11 up
works. ``module spider python`` lists the others. The steps above were tried
with the modules ``python/3.11.3`` (the default), ``python/3.12.12``,
``python/3.13.5`` and ``python/3.14.5``. For 3.14.5, CHPC wants
``module load gcc/13.4.0 python/3.14.5``.

If you already use conda, make an environment with Python 3.11 or newer and
run the same ``pip install`` inside it. This works too, and the environment
takes 0.6 GB in ``~/.conda/envs``:

.. code-block:: bash

   module load miniforge3
   conda create -y -n uataq python=3.12
   conda activate uataq
   pip install git+https://github.com/jmineau/uataq.git

Each time you log in
--------------------

Activate the environment before you use uataq:

.. code-block:: bash

   source ~/venvs/uataq/bin/activate

You do not need ``module load python`` again: the environment remembers which
Python it uses. If it ever stops working after CHPC changes its modules, delete
the folder (``rm -rf ~/venvs/uataq``) and redo steps 2 to 4.

Update uataq, or pin a version
------------------------------

The install above gets the newest code. To update later, run the same command
with ``--upgrade``:

.. code-block:: bash

   pip install --upgrade git+https://github.com/jmineau/uataq.git

For results you will publish, install a fixed release by adding its tag, and
write the version down. ``pip show uataq`` prints the version you have.
`The releases page <https://github.com/jmineau/uataq/releases>`_ lists the tags.

.. code-block:: bash

   pip install git+https://github.com/jmineau/uataq.git@v2026.10.0
   pip show uataq

.. _install-slurm:

Use uataq in a Slurm job
------------------------

A day or two of one site is small enough for a login node. For a year of data,
several sites or many processes (``num_processes``), write a job script. The
job only has to activate the environment:

.. code-block:: bash

   #!/bin/bash
   #SBATCH --account=lin-np
   #SBATCH --partition=lin-np
   #SBATCH --nodes=1
   #SBATCH --ntasks=1
   #SBATCH --mem=8G
   #SBATCH --time=00:30:00

   source ~/venvs/uataq/bin/activate
   python my_script.py

Save it as ``my_job.sh`` and submit it with ``sbatch my_job.sh``. ``lin-np`` is
the Lin group's own set of compute nodes. If ``sbatch`` refuses the account,
``mychpc batch`` lists the accounts and partitions you can use. See
`CHPC's Slurm guide <https://www.chpc.utah.edu/documentation/software/slurm.php>`_
for the rest.

Install for development
-----------------------

Use this to change uataq itself and send the change back. It sets up the
project the way its maintainer works. Three tools do the work:

* `uv <https://docs.astral.sh/uv/>`_ installs the packages the project needs
  into a ``.venv`` folder inside your copy of the code, at the versions
  recorded in ``uv.lock``.
* `just <https://just.systems/>`_ runs the project's named tasks, listed in
  its ``justfile`` (``just --list`` shows them). ``uv sync`` installs it, and
  you run it as ``uv run just``.
* `pre-commit <https://pre-commit.com/>`_ checks your changes for style
  problems each time you ``git commit``, before the commit is made.

uataq needs uv 0.12 or newer, and CHPC's ``uv`` module is older (0.11.14 in
October 2026). Install your own copy with pip. Do this in a shell where the
uataq environment is not active: run ``deactivate`` first, or pip stops with
``Can not perform a '--user' install``.

.. code-block:: bash

   module load python
   pip install --user uv
   uv --version

The last command should print ``uv 0.12`` or newer. Then get the code and set
it up:

.. code-block:: bash

   git clone https://github.com/jmineau/uataq.git
   cd uataq
   uv sync                       # the packages, into .venv (about two minutes)
   uv run pre-commit install     # turn on the checks at commit time

To run the checks that CI runs (lint, types, docstrings and the tests), use a
compute node, not the login node:

.. code-block:: bash

   srun --account=lin-np --partition=lin-np --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=8G --time=00:30:00 uv run just quality-check

It takes about a minute and ends with a line like ``453 passed``. The tests do
not need the archive, so you can also develop on your own computer.
`CONTRIBUTING.md <https://github.com/jmineau/uataq/blob/main/CONTRIBUTING.md>`_
has the rest of the workflow: branches and pull requests.

To work on the code while you use it for your own analysis, install your clone
into the environment from the steps above (an *editable* install, which runs
the code in your folder as you change it):

.. code-block:: bash

   source ~/venvs/uataq/bin/activate
   cd uataq
   pip install -e .

.. _install-errors:

If something goes wrong
-----------------------

``pip install`` ends with ``FileNotFoundError: ... setup.py``
   You are on CHPC's system Python 3.6, which cannot install uataq. Run
   ``module load python``, delete the environment if you made it before that
   (``rm -rf ~/venvs/uataq``), and redo steps 2 to 4.

The ``ls`` in step 1, or the read in step 5, fails
   You are probably not in the ``lin`` group yet. Run ``groups`` and see
   `What you need`_.

``uv sync`` fails with ``Required uv version ... does not match the running version``
   You are running CHPC's ``uv`` module. Run ``module unload uv``, install uv
   with pip as shown above, and open a new shell so the new copy comes first.

The steps on this page were last checked in October 2026 on a Notchpeak login
node.
