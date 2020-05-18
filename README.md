# setuptools_conda
<!-- 
[![Build Status](https://travis-ci.com/chrisjbillington/zprocess.svg?branch=master)](https://travis-ci.com/chrisjbillington/zprocess)

[![codecov](https://codecov.io/gh/chrisjbillington/zprocess/branch/master/graph/badge.svg)](https://codecov.io/gh/chrisjbillington/zprocess)-->

Add a `dist_conda` command to your `setup.py`, allowing you to generate conda packages
with `python setup.py dist_conda`, with as much information as possible determined
automatically. More powerful than `conda-build`'s `bdist_conda` - this package can build
for multiple Pythons, allows you to specify any package names that differ between conda
and PyPI, and converts a wider range of environment markers in dependencies such as:

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

To install:

    conda install -c cbillington setuptools_conda

or if you want to install with pip for some reason (though this package is not useful
outside a conda environment):
    
     pip install setuptools_conda
    
To build a conda package of your project, add the following to your setup.py:

```python
try:
    from setuptools_conda import dist_conda
    cmdclass = {'dist_conda': dist_conda}
except ImportError:
    cmdclass = {}

setup(
    use_scm_version=True,
    cmdclass=cmdclass,
```

The `try: except:` will allow your setup.py to still function normally outside of a conda
environment when `setuptools_conda` is not installed.

If `setuptools_conda` is installed, then you may build a conda package by running:
```bash
$ python setup.py dist_conda
```

The resulting conda package will be in `conda_packages/<architecture>/` and can be
installed with `conda install conda_packages/<architecture>/<pkgfile>` or uploaded to
your account on anaconda.org with:
```
anaconda upload conda_packages/<architecture>/<pkgfile>
```

You may customise `dist_conda` to build for multiple Python versions at once, or many
other options - see the full list of optiond below. Options may be passed in on the
command line, or in a `setup.cfg` file in the `[dist_conda]` section:

```ini
[dist_conda]
pythons = 3.6, 3.7
noarch = True
```

They can also be set if you need to with the command_options argument in `setup.py`:

```python
setup(
      ...
      command_options = (
          {
              'dist_conda': {
                  'pythons': (__file__, '3.6, 3.7'),
                  'noarch': (__file__, True),
              }
          },
      )
      ...
      )
```


```
$ python setup.py dist_conda -h

<snip>

Options for 'dist_conda' command:
  --pythons                 Minor Python versions to build for, as a comma-
                            separated list e.g. '2.7, 3.6'. Also accepts a
                            list of strings if passed into `setup()` via
                            `command_options`. Defaults to current Python
                            version
  --build-number (-n)       Conda build number. Defaults to zero
  --license-file (-l)       License file to include in the conda package.
                            Defaults to any file in the working directory
                            named 'LICENSE', 'COPYING', or 'COPYRIGHT', case
                            insensitive and ignoring extensions. Set to 'None'
                            to not include a license file even if one of the
                            above is present.
  --build-string (-s)       Conda build string.
  --setup-requires          Build dependencies, as a comma-separated list in
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
                            option to specify the mapping when they differ. If
                            the only difference is case, no entry  is needed -
                            names will automatically be converted to lower
                            case.
  --link-scripts            Comma-separated list of link scripts to include,
                            such as post-link.sh, pre-unlink.bat etc. These
                            will be placed in the recipe directory before
                            building. If passed to `setup()` via
                            `command_options`, this shound instead be a
                            dictionary mapping link script filenames to their
                            contents.
  --noarch                  Build platform-independent packages. Only set this
                            if your dependencies are the same on all platforms
                            and you have no compiled extensions.
```

