# setuptools_conda
<!-- 
[![Build Status](https://travis-ci.com/chrisjbillington/zprocess.svg?branch=master)](https://travis-ci.com/chrisjbillington/zprocess)

[![codecov](https://codecov.io/gh/chrisjbillington/zprocess/branch/master/graph/badge.svg)](https://codecov.io/gh/chrisjbillington/zprocess)-->

Add a `conda_dist` command to `setuptools`, allowing you to generate conda packages with
`python setup.py conda_dist`, with as much information as possible determined
automatically.

To install:

    pip install setuptools_conda

or

    conda install -c cbillington setuptools_conda

Docs coming soon - for now see the `setup.py` of this project for an example, or clone
this repo and run `python setup.py conda_dist -h` to read the help text for the
available options.

A more complete example is the `setup.py` of the [zprocess
project](https://github.com/chrisjbillington/zprocess/), which actually has non-trivial
dependencies.