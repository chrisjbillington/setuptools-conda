# setuptools-conda

Build a conda package from a setuptools project.

## Table of Contents

   * [Installation and usage](#installation-and-usage)
   * [build and install setuptools-conda from source](#build-and-install-setuptools-conda-from-source)
   * [Help text of setuptools-conda](#help-text-of-setuptools-conda)
   * [Help text of setuptools-conda build command](#help-text-of-setuptools-conda-build-command)
   * [Help text of setuptools-conda install-requirements command](#help-text-of-setuptools-conda-install-requirements-command)
   * [Help text of python setup.py dist_conda distutils command](#help-text-of-python-setuppy-dist_conda-distutils-command)

## Installation and usage

To install:
```bash 
$ conda install -c labscript-suite setuptools-conda
```
To make a conda package: in your project directory, run:
```bash
$ setuptools-conda build .
```

The resulting conda package will be in `conda_packages/<architecture>/` and can be
installed with `conda install conda_packages/<architecture>/<pkgfile>` or uploaded to
your account on anaconda.org with (you'll need to install `anaconda-client`):
``` bash
$ anaconda upload conda_packages/<architecture>/<pkgfile>
```

`setuptools-conda build` installs the project's build dependencies, as declared in a
`pyproject.toml`, `setup.cfg` or `setup.py`, and then runs `python setup.py dist_conda`,
where `dist_conda` is a distutils command added by `setuptools-conda`. You can also run
`python setup.py dist_conda` yourself. See below for the full documentation of the
`setuptools-conda build` command and the `dist_conda` command to `setup.py`.

`setuptools-conda` also provides a command `setuptools-conda install-requirements` that
will install a project or projects build and runtime requirements with conda. This
allows one to then make an editable install with `pip install --no-deps -e .` whilst
ensuring all of a project's dependencies are without `pip` installing missing
dependencies from PyPI into a conda environment, which can be problematic.

`setuptools-conda` aims to be as comprehensive as possible, allowing you to generate
conda packages with `setuptools-conda build` or `python setup.py dist_conda`, with as
much information as possible determined automatically. More powerful than
`conda-build`'s `bdist_conda` - this package can build for multiple Python versions,
allows you to specify any package names that differ between conda and PyPI, and converts
a wider range of environment markers in dependencies such as:

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

In most cases, you should not need to modify a project's code at all to use
`setuptools-conda`, though if it's your project you're building, you may wish to add
configurations settings to `setup.cfg` in order to avoid passing them all as command
line arguments at build time.

You may customise `dist_conda` to build for multiple Python versions at once, or many
other options - see the full list of options in the help text of the `dist_conda`
command below. Options may be passed in on the command line, or in a `setup.cfg` file in
the `[dist_conda]` section:

```ini
[dist_conda]
conda_name_differences = PyQt5:pyqt
pythons = 3.6, 3.7
noarch = True
```

or in `pyproject.toml` in the `[tool.setuptools_conda]` section:

```toml
[tool.setuptools_conda]
conda_name_differences = {PyQt5 = "pyqt"}
pythons = ["3.12", "3.13"]
noarch = true
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
)
```


## build and install `setuptools-conda` from source

`setuptools-conda` can build a conda package of itself. To build and install it, run the
following in an activated conda environment:

``` bash
git clone https://github.com/chrisjbillington/setuptools-conda
cd setuptools-conda/
python -m setuptools_conda build --noarch .
conda install conda_build/conda-bld/noarch/setuptools-conda-<version>-<build>.tar.bz2
```

## Note on local testing of built packages

`setuptools-conda` copies built conda package files the `conda_packages` directory
within your project directory for easy uploading. However, for local testing you'll want
to avoid installing package files from this directory. This is because `conda`
associates all packages installed from file with the folder they came from, as if that
folder is a package channel.

To keep conda happy in this respect, for local testing, you'll want to install the
package file from the directory where `conda-build` originally created it within the `conda_build` directory in your project directory:
 ```bash
conda install conda_build/conda-bld/noarch/setuptools-conda-<version>-<build>.tar.bz2
```

## Help text of `setuptools-conda`


```
$ python setuptools-conda -h
usage: setuptools-conda [-h] {build,install-requirements} ...

positional arguments:
  {build,install-requirements}
                        Action to perform, either "build" or "install-requirements". For
                        help on arguments accepted by a given command, run
                        'setuptools-conda <command> -h'
    build               Build a conda package from a setuptools project.

                        Installs the build requirements of the project with conda, and
                        then runs 'python setup.py dist_conda', passing remaining
                        arguments. This is similar to 'pip wheel' etc in the presence of
                        a pyproject.toml file (but without build isolation - the
                        dependencies will be installed in the current environment). A
                        typical way to call this script would be as 'setuptools-conda
                        build [args] .' from the working directory of a project, where
                        '[args]' are any additional arguments you want to pass to the
                        'dist_conda' command. See 'python setup.py dist_conda -h' for a
                        full list of accepted arguments.

                        Build requirements are searched for in the places in order,
                        stopping on the first found:

                        1. --setup-requires passed in on the command line
                        2. [dist_conda]/setup_requires in the project's setup.cfg
                        3. [build-system]/requires in the project's pyproject.toml
                        4. [options]/setup_requires in the project's setup.cfg

                        This the same way the 'dist_conda' command gets build
                        dependencies.

                        Additional conda channels to enable to install the build
                        requirements can be passed in with the '--channels' argument or
                        set in [dist_conda]/channels in setup.cfg, any any PyPI:conda
                        name differences can be passed in with the
                        '--conda-name-differences' argument or configured in
                        [dist_conda]/conda_name_differences in setup.cfg.
    install-requirements

                        Install the requirements of the given project(s). This will
                        install both the build and runtime requirements of all packages
                        given. Build dependencies are determined from the same sources
                        as the 'build' command.

                        Runtime requirements are searched for in the places in order,
                        stopping on the first found:

                        1. --install-requires passed in on the command line
                        2. [tool.setuptools_conda]/install_requires in the project's
                           pyproject.toml
                        2. [dist_conda]/install_requires in the project's setup.cfg
                        4. [options]/install_requires in the project's setup.cfg or
                           setup.py (obtained via 'python setup.py egg_info')

                        any any PyPI:conda name differences can be passed in with the
                        '--conda-name-differences' argument or configured in
                        pyproject.toml [tool.setuptools_conda]/conda_name_differences or
                        setup.cfg [dist_conda]/conda_name_differences.

                        Any runtime requirements that themselves are in the list of
                        projects to install requirements for will not be installed. This
                        is intended to facilitate running `pip install -e --no-deps` to
                        create editable installs for a set of projects, for which one
                        would not want to install those projects normally in addition to
                        in editable mode.

options:
  -h, --help            show this help message and exit
```

## Help text of `setuptools-conda build` command

```
$ python setuptools-conda build -h
usage: setuptools-conda build [-h] [setup_args [setup_args ...]] project_path

positional arguments:
  setup_args    Arguments to pass to setup.py as 'python setup.py dist_conda
                [setup_args]'; e.g. '--noarch'
  project_path  Path to project; e.g. '.' if the project's `setup.py`,
                `pyproject.toml` or `setup.cfg` are in the current working
                directory.

optional arguments:
  -h, --help    show this help message and exit
```

## Help text of `setuptools-conda install-requirements` command
```
$ python setuptools-conda install-requirements -h
usage: setuptools-conda install-requirements [-h] [--setup-requires SETUP_REQUIRES]
                                             [--install-requires INSTALL_REQUIRES]
                                             [--conda-name-differences CONDA_NAME_DIFFERENCES]
                                             [--channels CHANNELS]
                                             projects [projects ...]

positional arguments:
  projects              Project directories to install dependencies for

optional arguments:
  -h, --help            show this help message and exit
  --setup-requires SETUP_REQUIRES
                        Build requirements override. 'See python setup.py dist_conda -h'
  --install-requires INSTALL_REQUIRES
                        Install requirements override. 'See python setup.py dist_conda
                        -h'
  --conda-name-differences CONDA_NAME_DIFFERENCES
                        PyPI:conda name differences override. 'See python setup.py
                        dist_conda -h'"
  --channels CHANNELS   Channels to search for build requires. 'See python setup.py
                        dist_conda -h'
  ```

## Help text of `python setup.py dist_conda` distutils command

```
$ python setup.py dist_conda -h

<snip>

Options for 'dist_conda' command:
  --pythons                 Minor Python versions to build for, as a comma-
                            separated list e.g. '2.7, 3.6'. Also accepts a
                            list of strings if passed into `setup()` via
                            `command_options`. Defaults to the current Python
                            version.
  --build-number (-n)       Conda build number. Defaults to zero
  --license                 Manually specify the type of license for the conda
                            package. Defaults to the license defined in the 
                            package metadata.
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
                            `command_options`. Defaults to any requirements
                            listed in a `pyproject.toml` under [build-
                            system]/requires, or if none, any requirements
                            listed in the `setup_requires` setuptools
                            configuration option. Can be be omitted if the
                            build dependencies when building for conda do not
                            differ.
  --install-requires        Runtime dependencies, as a comma-separated list in
                            standard setuptools format, e.g. 'foo >= 2.0;
                            sys_platform=="win32",bar==2.3'. Also accepts a
                            list of strings if passed into `setup()` via
                            `command_options`. Defaults to the
                            `install_requires` argument to `setup()`, and can
                            therefore be omitted if the runtime dependencies
                            when running in conda do not differ.
  --ignore-run-exports      Comma-separated list of conda packages that should
                            *not* be considered runtime dependencies, even if
                            they are declared in run_exports of a build
                            dependency. run_exports declared by build
                            dependencies are normally automatically considered
                            run dependencies, for example libraries that were
                            linked against at build-time - but this can be
                            undesirable when it creates a brittle dependency
                            on a specific version of a library which is not
                            actually required at runtime. Also accepts a list
                            of strings if passed into `setup()` via
                            `command_options`.
  --channels (-c)           Additional channels to search for build
                            requirements during the build, as a comma-
                            separated list, or a list of strings if passed in
                            via setup.py. Defaults to [tools.setuptools-
                            conda]/channels listed in a `pyproject.toml` file,
                            if any.
  --conda-name-differences  Mapping of PyPI package names to conda package
                            names, as a comma-separated list of colon-
                            separated names, e.g.
                            'PyQt5:pyqt,beautifulsoup4:beautiful-soup'. Also
                            accepts a dict if passed into `setup()` via
                            `command_options`. Conda packages usually share a
                            name with their PyPI equivalents, but use this
                            option to specify the mapping when they differ. If
                            the only difference is lowercasing or conversion
                            of underscores into hyphens, no entry is needed -
                            these changes are made automatically.
  --link-scripts            Comma-separated list of link scripts to include,
                            such as post-link.sh, pre-unlink.bat etc. These
                            will be placed in the recipe directory before
                            building. If passed to `setup()` via
                            `command_options`, this shound instead be a
                            dictionary mapping link script filenames to their
                            contents.
  --noarch                  Build a platform-independent package. Only set
                            this if your dependencies are the same on all
                            platforms and Python versions you support, and you
                            have no compiled extensions.
  --from-wheel              Whether to build a wheel before invoking conda-
                            build. By default setuptools-conda invokes conda-
                            build on an sdist such that any compilation of
                            extensions will be done in the conda build
                            environment. However, if your extensions are not
                            able to be compiled with conda's compiler
                            configuration, you might set this option to pass
                            conda-build a wheel that has been pre-compiled
                            with the system configuration. In this case,
                            setuptools-conda will only produce a conda package
                            for the current Python version.
  --from-downloaded-wheel   Whether to avoid local building at all and
                            download a wheel from PyPI before invoking conda-
                            build. For projects with tricky build environment
                            requirements, this can be a way to essentially
                            repackage an existing wheel without having to any
                            building at all. Requires that the exact version
                            as understood by setuptools is availalble on PyPI
                            as a wheel. In this case, setuptools-conda will
                            only produce a conda package for the current
                            Python version.
  --build-dir               Directory used by setuptools-conda for storing the
                            recipe and other temporary build files. Defaults
                            to ./conda_build
  --croot                   Value of --croot to pass to conda-build, used as
                            its build directory. Defaults to <build-dir>/conda
                            -bld. Setting this to a very short path can be
                            useful on Windows, where conda-build sometimes
                            chokes on very long filepaths.
```
