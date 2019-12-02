# setuptools_conda
<!-- 
[![Build Status](https://travis-ci.com/chrisjbillington/zprocess.svg?branch=master)](https://travis-ci.com/chrisjbillington/zprocess)

[![codecov](https://codecov.io/gh/chrisjbillington/zprocess/branch/master/graph/badge.svg)](https://codecov.io/gh/chrisjbillington/zprocess)-->

Add a `dist_conda` command to your `setup.py`, allowing you to generate conda packages
with `python setup.py dist_conda`, with as much information as possible determined
automatically. More powerful than `conda-build`'s `bdist_conda` - this package can build
for multiple Pythons, allows you to specify any package names that differ between conda
and PyPI, runs `conda-convert` to convert packages for multiple platforms. It supports
python-version-specific and platform-specific requirements such as 

```
INSTALL_REQUIRES = [
    "pyzmq >=18.0",
    "ipaddress;         python_version == '2.7'",
    "subprocess32;      python_version == '2.7'",
    "enum34;            python_version == '2.7'",
    "pywin32;           sys_platform == 'win32'",
    "windows-curses;    sys_platform == 'win32'",
]
```

and will create converted packages for each platform and Python version with the correct
dependencies after evaluating the selector expressions for each package.

To install:

    pip install setuptools_conda

or

    conda install -c cbillington setuptools_conda

Docs coming soon - for now see the `setup.py` of this project for an example, or clone
this repo and run `python setup.py bdist_conda -h` to read the help text for the
available options.

A more complete example is the `setup.py` of the [zprocess
project](https://github.com/chrisjbillington/zprocess/), which actually has non-trivial
dependencies.