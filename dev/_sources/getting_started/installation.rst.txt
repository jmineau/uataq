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
the archive is. (To read a copy of it, set ``LINGROUP_MEASUREMENTS_DIR`` to the
copy's ``measurements`` folder; see :ref:`install-archive-copy`.)

Install
-------

1. **Check that you can read the archive.**

   .. code-block:: bash

      ls /uufs/chpc.utah.edu/common/home/lin-group25/measurements/data

   You should see a folder for each site the lin group records (``asb``,
   ``csp``, ``dbk``, and so on through ``wbb``), and a few other folders that
   are not uataq sites. If you get an error instead, you do not have access
   yet. See `What you need`_.

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

Next, read :doc:`/getting_started/first_data`.

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

.. _install-jupyter:

Use uataq in Jupyter
--------------------

CHPC runs Jupyter in your browser through
`Open OnDemand <https://ondemand.chpc.utah.edu>`_. To use your uataq environment
there, install Jupyter into it once:

.. code-block:: bash

   source ~/venvs/uataq/bin/activate
   pip install jupyterlab

It takes a minute or two and about 0.25 GB more. Then open the Jupyter app in
Open OnDemand, choose **Custom (Environment setup below)** as the Python version,
and enter these two lines in the environment setup box:

.. code-block:: bash

   module load python
   source ~/venvs/uataq/bin/activate

Your notebooks then run the environment's Python, with uataq. (The two lines
are CHPC's instructions for a custom environment; the environment itself was
tested up to a Jupyter kernel that imports uataq.)

Update uataq, or pin a version
------------------------------

The install above gets the newest code. To update later, run the same command
with ``--upgrade``:

.. code-block:: bash

   pip install --upgrade git+https://github.com/jmineau/uataq.git

For results you will publish, install a fixed release by adding its tag, and
write the version down. ``pip show uataq`` prints the version you have.
`The releases page <https://github.com/jmineau/uataq/releases>`_ lists the tags
(``v2026.10.1`` was the newest in October 2026).

.. code-block:: bash

   pip install git+https://github.com/jmineau/uataq.git@v2026.10.1
   pip show uataq

.. _install-slurm:

Use uataq in a Slurm job
------------------------

A login node is for light work, such as a year of one site's CO2 and CH4 at the
``final`` level (how long that takes: :ref:`large-reads`). For
several years or many sites, the ``raw`` level, or reads in several processes,
write a job script. The job only has to activate the environment:

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

.. _install-archive-copy:

Reading a copy of the archive
-----------------------------

uataq reads the Lin group's measurements from the group's dedicated measurements
space. To read a copy instead (a snapshot kept for a paper, or a test tree), set
``LINGROUP_MEASUREMENTS_DIR`` to the copy's ``measurements`` folder, the one that
holds ``data`` and ``pipeline``. Unset or empty, it means the archive itself.

.. code-block:: bash

   export LINGROUP_MEASUREMENTS_DIR=/path/to/measurements

uataq looks the variable up each time it needs a path, so setting it in Python
after ``import uataq`` works too (``os.environ["LINGROUP_MEASUREMENTS_DIR"] = ...``),
with one exception: the pipeline's configuration files (``data_config.json`` and
``site_config.csv``) are read once, when uataq is imported, so set the variable
before the import if the copy's configuration differs. A value that is not a
directory raises ``FileNotFoundError`` naming the variable. The Horel group's
folders have no such variable.

.. _install-errors:

If something goes wrong
-----------------------

``pip install`` ends with ``FileNotFoundError: ... setup.py``
   You are on CHPC's system Python 3.6, which cannot install uataq. Run
   ``module load python``, delete the environment if you made it before that
   (``rm -rf ~/venvs/uataq``), and redo steps 2 to 4.

``FileNotFoundError`` saying ``LINGROUP_MEASUREMENTS_DIR`` is not a directory
   The variable is set to a path that does not exist. Fix the path, or run
   ``unset LINGROUP_MEASUREMENTS_DIR`` to read the archive itself.

The ``ls`` in step 1, or the read in step 5, fails
   You are probably not in the ``lin`` group yet. Run ``groups`` and see
   `What you need`_.

The steps on this page were last checked in October 2026 on a Notchpeak login
node.
