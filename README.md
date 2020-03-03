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

Docs coming soon - for now see the `setup.py` of this project for an example, and below
is the output of `python setup.py dist_conda -h` listing available options that may be
passed on the command line or via `command_options` in `setup()`. A more complete
example is the `setup.py` of the [zprocess
project](https://github.com/chrisjbillington/zprocess/), which actually has non-trivial
dependencies.

```
$ python setup.py dist_conda -h

<snip>

Options for 'dist_conda' command:
  --pythons                 Minor Python versions to build for, as a comma-
                            separated list e.g. '2.7,3.6'. Also accepts a list
                            of strings if passed into `setup()` via
                            `command_options`. Defaults to current Python
                            version
  --platforms               Platforms to build for, as a comma-separated list
                            of one or more of win-32,win-64,linux-32,linux-
                            64,osx-64, or 'all' for all of them. Also accepts
                            a list of strings if passed into `setup()` via
                            `command_options`. Defaults to the current
                            platform.
  --force-conversion (-f)   Perform conversion to other platforms even if the
                            build contains platform-specific C extensions or
                            binaries. These extensions will not be converted,
                            but this may be acceptable if for example the
                            package bundles precompiled executables or
                            libraries for multiple platforms, that it laods
                            dynamically.
  --build-number (-n)       Conda build number. Defaults to zero
  --license-file (-l)       License file to include in the conda package.
                            Defaults to any file in the working directory
                            named 'LICENSE', 'COPYING', or 'COPYRIGHT', case
                            insensitive and ignoring extensions. Set to 'None'
                            to not include a license file even if one of the
                            above is present.
  --build-string (-s)       Conda build string.
  --setup-requires           Build dependencies, as a comma-separated list in
                            standard setuptools format, e.g. 'foo >= 2.0;
                            sys_platform=="win32",bar==2.3'. Also accepts a
                            list of strings if passed into `setup()` via
                            `command_options`. Defaults to the
                            `setup_requires` argument to `setup()`, and can
                            therefore be omitted if the build dependencies
                            when building for conda do not differ.
  --install-requires        Runtime dependencies, as a comma-separated list in
                            standard setuptools format, e.g. 'foo >= 2.0;
                            sys_platform=="win32",bar==2.3'. Also accepts a
                            list of strings if passed into `setup()` via
                            `command_options`. Defaults to the
                            `install_requires` argument to `setup()`, and can
                            therefore be omitted if the runtime dependencies
                            when running in conda do not differ.
  --conda-name-differences  Mapping of PyPI package names to conda package
                            names, as a comma-separated list of colon-
                            separated names, e.g.
                            'PyQt5:pyqt,beautifulsoup4:beautiful-soup'. Also
                            accepts a dict if passed into `setup()` via
                            `command_options`. Conda packages usually share a
                            name with their PyPI equivalents, but use this
                            option to specify the mapping when they differ.
  --no-dev-buildstring      Disable the following behavuour: If no build
                            string is given and the package version contains
                            the string 'dev', and the current working
                            directory is a git repository (and the git
                            executable can be found), then setuptools_conda
                            will set the build string to
                            'pyXY_<branchname>_<shorthash>_<buildnumber>'. Any
                            hyphens in the branch name are replaced by
                            underscores. This is useful to create uniquely-
                            named builds for testing unmerged pull requests,
                            etc.
  --link-scripts            Comma-separated list of link scripts to include,
                            such as post-link.sh, pre-unlink.bat etc. These
                            will be placed in the recipe directory before
                            building. If passed to `setup()` via
                            `command_options`, this shound instead be a
                            dictionary mapping link script filenames to their
                            contents.
```

