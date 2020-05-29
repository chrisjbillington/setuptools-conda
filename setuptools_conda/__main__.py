from pathlib import Path
from subprocess import call
import sys
import argparse
import textwrap
import platform

WINDOWS = platform.system() == 'Windows'


def run(cmd, **kwargs):
    print('[running]:', ' '.join(cmd))
    # Shell=True is necessary on Windows for calls to conda, otherwise we get mysterious
    # breakage. But shell=True with a list of args totally changes this function on unix
    # so we avoid it:
    rc = call(cmd, shell=WINDOWS, **kwargs)
    if rc:
        sys.exit(rc)
    return rc


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

            1. --setup-requires passed in on the command line
            2. [dist_conda]/setup_requires in the project's setup.cfg
            3. [build-system]/requires in the project's pyproject.toml
            4. [options]/setup_requires in the project's setup.cfg

            This the same way the 'dist_conda' command gets build dependencies.

            Additional conda channels to enable to install the build requirements can be
            passed in with the '--channels' argument or set in [dist_conda]/channels in
            setup.cfg, any any PyPI:conda name differences can be passed in with the
            '--conda-name-differences' argument or configured in
            [dist_conda]/conda_name_differences in setup.cfg."""
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

    def getargvalue(argname, arglist):
        try:
            return arglist[arglist.index(argname) + 1]
        except IndexError:
            msg = f"Argument {argname} has no corresponding value"
            parser.print_usage()
            raise SystemExit(msg)
        except ValueError:
            pass
        for arg in arglist:
            if arg.startswith(f'{argname}='):
                return arg.split(f'{argname}=', 1)[1]

    def get_requires(proj, setup_args):
        arg = '--setup-requires'
        requires = getargvalue(arg, setup_args)
        if requires is not None:
            print(f"Using build requirements from {arg} command line argument")
            return split(requires)
        requires = get_setup_cfg_entry(proj, "dist_conda", "setup_requires")
        if requires is not None:
            print("Using build requirements from [dist_conda]/setup_requires")
            return requires
        requires = get_pyproject_toml_entry(proj, 'build-system', 'requires')
        if requires is not None:
            print("Using build requirements from [build-system]/requires")
            return requires
        requires = get_setup_cfg_entry(proj, "options", "setup_requires")
        if requires is not None:
            print("Using build requirements from [options]/setup_requires")
            return requires
        print("No build requirements")
        return []

    def get_channels(proj, setup_args):
        arg = '--channels'
        if arg in setup_args:
            print(f"Using extra channels from {arg} command line argument")
            return split(setup_args[setup_args.index(arg) + 1])
        channels = get_setup_cfg_entry(proj, "dist_conda", "channels")
        if channels is not None:
            print("Using extra channels from [dist_conda]/channels")
            return channels
        print("No extra channels")
        return []

    def get_name_differences(proj, setup_args):
        arg = '--conda-name-differences'
        if arg in setup_args:
            print(f"Using name differences from {arg} command line argument")
            name_differences = setup_args[setup_args.index(arg) + 1]
            return dict(split(item, ':') for item in split(name_differences))
        name_differences = get_setup_cfg_entry(
            proj, "dist_conda", "conda_name_differences"
        )
        if name_differences is not None:
            print("Using extra channels from [tools.setuptools-conda]/channels")
            return dict(split(item, ':') for item in name_differences)
        print("No name differences")
        return {}

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

    from setuptools_conda.setuptools_conda import (
        get_pyproject_toml_entry,
        get_setup_cfg_entry,
        evaluate_requirements,
        condify_name,
        split,
    )

    proj = Path(project_path)

    requires = get_requires(proj, setup_args)
    name_differences = get_name_differences(proj, setup_args)
    requires = [
        condify_name(s, name_differences) for s in evaluate_requirements(requires)
    ]
    channels = get_channels(proj, setup_args)

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
