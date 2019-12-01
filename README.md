# setuptools_conda
<!-- 
[![Build Status](https://travis-ci.com/chrisjbillington/zprocess.svg?branch=master)](https://travis-ci.com/chrisjbillington/zprocess)

[![codecov](https://codecov.io/gh/chrisjbillington/zprocess/branch/master/graph/badge.svg)](https://codecov.io/gh/chrisjbillington/zprocess)-->

Add a `dist_conda` command to `setuptools`, allowing you to generate conda packages with
`python setup.py dist_conda`, with as much information as possible determined
automatically.

To install:

    pip install setuptools_conda

or

    conda install -c cbillington setuptools_conda

Docs coming soon - for now see the setup.py of this project for an example, or clone
this repo and run `python setup.py conda_dist -h` to read the help text for the
available options.