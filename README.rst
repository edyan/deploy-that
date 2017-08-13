Overview
========
A simple tool that I use for my personal projects to make sure I follow all the steps
to publish a package:

- Verify the ``setup.py``
- Find the latest version pushed and ask for the new version
- Replace the version value in a list of files defined in deploythat.yml
- Commit the changed files (of step 3)
- Push to GIT (before tests to let CI tools do the tests in parallel)
- Run unit tests in local
- If ``ci`` is True in config, wait before creating the tag that the CI tools gave a positive answer
- Create tag from version defined above and push tags
- Update the package to PyPi


Configuration File Reference
============================
The file must be named ``deploythat.yml``.

Parameters:

- ``language`` : *required*, python or php (not supported now, will be later)
- ``files`` : *required*, list of files to patch, only the lines with the old version number + a keyword "version" will be changed
- ``tests_dir`` : Directory where to find tests (``tests/`` by default)
- ``git`` :
    - ``push_branch`` : the branch where to push
- ``ci`` : true by default, can be false to avoid the tool to ask questions


Installation
============

.. code-block:: bash

    $ pip install git+https://github.com/edyan/deploy-that.git


Example
=======
With the following configuration:

.. code-block:: yaml

    language: python
    files:
        - stakkr/cli.py
    tests_dir: tests/

Run:

.. code-block:: bash

    $ deploy-that
