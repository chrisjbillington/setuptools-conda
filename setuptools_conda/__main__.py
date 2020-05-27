from pathlib import Path
from subprocess import call
import sys
import os
import argparse
import textwrap
import platform

WINDOWS = platform.system() == 'Windows'

get_pyproject_toml_entry = None
get_setup_cfg_entry = None


def run(cmd, **kwargs):
    print('[running]:', ' '.join(cmd))
    # Shell=True is necessary on Windows for calls to conda, otherwise we get mysterious
    # breakage. But shell=True with a list of args totally changes this function on unix
    # so we avoid it:
    rc = call(cmd, shell=WINDOWS, **kwargs)
    if rc:
        sys.exit(rc)
    return rc


def get_requires(proj):
    requires = get_pyproject_toml_entry(proj, 'build-system', 'requires')
    if requires is not None:
        print("Using build requirements from [build-system]/requires")
        return requires
    requires = get_setup_cfg_entry(proj, "dist_conda", "setup_requires")
    if requires is not None:
        print("Using build requirements from [dist_conda]/setup_requires")
        return requires
    requires = get_setup_cfg_entry(proj, "options", "setup_requires")
    if requires is not None:
        print("Using build requirements from [options]/setup_requires")
        return requires
    print("No build requirements found")
    requires = []


def get_channels(proj):
    channels = get_pyproject_toml_entry(proj, "tools", "setuptools-conda", "channels")
    if channels is not None:
        print("Using extra channels from [tools.setuptools-conda]/channels")
        return channels
    channels = get_setup_cfg_entry(proj, "dist_conda", "channels")
    if channels is not None:
        print("Using extra channels from [tools.setuptools-conda]/channels")
        return channels
    print("No extra channels specified")
    return []


def main():
    # Since setuptools_conda is self-hosting, it needs toml and distlib to read its own
    # requirements just to know that it needs to install toml and distlib! So bootstrap
    # that up if necessary.

    parser = argparse.ArgumentParser(
        prog='setuptools-conda',
        description=textwrap.dedent(
            """\
            Build a conda package from a setuptools project.

            Installs the build requirements of the project with conda, and then runs
            'python setup.py dist_conda', passing remaining arguments. This is similar
            to 'pip wheel' etc in the presence of a pyproject.toml file (but without
            build isolation - the dependencies will be installed in the current
            environment). A typical way to call this script would be as
            'setuptools-conda build [args] .' from the working directory of a project,
            where '[args]' are any additional arguments you want to pass to the
            'dist_conda' command. See 'python setup.py dist_conda -h' for a full list of
            accepted arguments.

            Build requirements are searched for in the places in order, stopping on the
            first found:

            1. [build-system]/requires in the project's pyproject.toml
            2. [dist_conda]/setup_requires in the project's setup.cfg
            3. [options]/setup_requires in the project's setup.cfg

            Additional conda channels to enable to install the build requirements are
            searched for in the following places in order, stopping on the first found:

            1. [tools.setuptools-conda]/channels in the project's pyproject.toml
            2. [dist_conda]/channels in the project's setup.cfg

            Note that when running 'python setup.py dist_conda', dist_conda will receive
            configuration from setup.cfg with higher priority, which is the opposite of
            what we do here. So use one or the other for configuring build dependencies,
            not both lest the two become inconsistent.
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        action="store",
        choices=['build'],
        dest="action",
        help="""Action to perform. Only 'build' is presently supported, but more actions
            may be added in the future.""",
    )

    parser.add_argument(
        action="store",
        dest="setup_args",
        nargs="*",
        help="""Arguments to pass to setup.py as 'python setup.py dist_conda
        [setup_args]'; e.g. '--noarch'""",
    )

    parser.add_argument(
        'project_path',
        action="store",
        help="""Path to project; e.g. '.' if the project's `setup.py`, `pyproject.toml`
        or `setup.cfg` are in the current working directory.""",
    )

    # We don't actually use this, it's just for help and error-checking on the 'action'
    # arg. We'll parse setup_args and project_path ourselves, in order to workaround
    # https://bugs.python.org/issue9334
    _ = parser.parse_known_args()

    setup_args = sys.argv[2:-1]
    project_path = sys.argv[-1]

    # Bootstrap up our own requirements just to run the functions for getting
    # requirements:
    need = ["toml", "distlib"]
    for name in need[:]:
        try:
            __import__(name)
            need.remove(name)
        except ImportError:
            pass
    if need:
        run(['conda', 'install', '-y'] + need)

    global get_pyproject_toml_entry
    global get_setup_cfg_entry

    from setuptools_conda.setuptools_conda import (
        get_pyproject_toml_entry,
        get_setup_cfg_entry,
        evaluate_requirements,
    )

    proj = Path(project_path)

    requires = get_requires(proj)
    requires = evaluate_requirements(requires)
    channels = get_channels(proj)

    chan_args = []
    for chan in channels:
        chan_args += ['--channel', chan]

    if requires:
        run(['conda', 'install', '-y',] + chan_args + requires)

    sys.exit(
        run([sys.executable, 'setup.py', 'dist_conda'] + setup_args, cwd=str(proj),)
    )


if __name__ == '__main__':
    main()
