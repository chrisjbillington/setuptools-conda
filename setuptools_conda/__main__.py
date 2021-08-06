from pathlib import Path
from subprocess import call, check_output
import shlex
import sys
import argparse
import textwrap
import platform
import tempfile

WINDOWS = platform.system() == 'Windows'


def main():
    # Since setuptools_conda is self-hosting, it needs toml and distlib to read its own
    # requirements just to know that it needs to install toml and distlib! So bootstrap
    # that up if necessary.

    parser = argparse.ArgumentParser(
        prog='setuptools-conda', formatter_class=argparse.RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        help=textwrap.dedent(
            """\
                        Action to perform, either "build" or "install-requirements". For
                        help on arguments accepted by a given command, run
                        'setuptools-conda <command> -h'
            """
        ),
    )

    parser_build = subparsers.add_parser(
        "build",
        help=textwrap.dedent(
            """\
                        Build a conda package from a setuptools project.

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
                        [dist_conda]/conda_name_differences in setup.cfg."""
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser_build.add_argument(
        action="store",
        dest="setup_args",
        nargs="*",
        help=textwrap.dedent(
            """\
                        Arguments to pass to setup.py as 'python setup.py dist_conda
                        [setup_args]'; e.g. '--noarch'"""
        ),
    )

    parser_build.add_argument(
        'project_path',
        action="store",
        help=textwrap.dedent(
            """\
                        Path to project; e.g. '.' if the project's `setup.py`,
                        `pyproject.toml` or `setup.cfg` are in the current working
                        directory.
            """
        ),
    )

    parser_install_requirements = subparsers.add_parser(
        "install-requirements",
        help=textwrap.dedent(
            """\

                        Install the requirements of the given project(s). This will
                        install both the build and runtime requirements of all packages
                        given. Build dependencies are determined from the same sources
                        as the 'build' command.

                        Runtime requirements are searched for in the places in order,
                        stopping on the first found:

                        1. --install-requires passed in on the command line
                        2. [dist_conda]/install_requires in the project's setup.cfg
                        4. [options]/install_requires in the project's setup.cfg or
                           setup.py (obtained via 'python setup.py egg_info')

                        any any PyPI:conda name differences can be passed in with the
                        '--conda-name-differences' argument or configured in
                        [dist_conda]/conda_name_differences in setup.cfg.

                        Any runtime requirements that themselves are in the list of
                        projects to install requirements for will not be installed. This
                        is intended to facilitate running `pip install -e --no-deps` to
                        create editable installs for a set of projects, for which one
                        would not want to install those projects normally in addition to
                        in editable mode.
            """
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser_install_requirements.add_argument(
        "--setup-requires",
        action="store",
        default=None,
        help=textwrap.dedent(
            """\
                        Build requirements override. 'See python setup.py dist_conda -h'
            """
        ),
    )

    parser_install_requirements.add_argument(
        "--install-requires",
        action="store",
        default=None,
        help=textwrap.dedent(
            """\
                        Install requirements override. 'See python setup.py dist_conda
                        -h'
            """
        ),
    )

    parser_install_requirements.add_argument(
        "--conda-name-differences",
        action="store",
        default=None,
        help=textwrap.dedent(
            """\
                        PyPI:conda name differences override. 'See python setup.py
                        dist_conda -h'"
            """
        ),
    )

    parser_install_requirements.add_argument(
        "--channels",
        action="store",
        default=None,
        help=textwrap.dedent(
            """\
                        Channels to search for build requires. 'See python setup.py
                        dist_conda -h'
            """
        ),
    )

    parser_install_requirements.add_argument(
        action="store",
        dest="projects",
        nargs="+",
        help=textwrap.dedent(
            """\
                        Project directories to install dependencies for
            """
        ),
    )

    def run_conda_cmd(cmd, **kwargs):
        print('[running]:', *[shlex.quote(arg) for arg in cmd])
        # Shell=True is necessary on Windows for calls to conda, otherwise we get
        # mysterious breakage. But shell=True with a list of args totally changes this
        # function on unix so we avoid it:
        rc = call(cmd, shell=WINDOWS, **kwargs)
        if rc:
            sys.exit(rc)
        return rc

    def get_output(cmd, **kwargs):
        print('[running]:', *[shlex.quote(arg) for arg in cmd])
        return check_output(cmd, shell=WINDOWS, **kwargs).decode('utf8').strip()

    def getargvalue(argname, args):
        """if arglist is a list, manually look for an arg --argname return its value. If
        args is a namespace object, simply return args.argname"""
        if hasattr(args, argname.replace('-', '_')):
            return getattr(args, argname.replace('-', '_'))
        try:
            return args[args.index(f'--{argname}') + 1]
        except IndexError:
            msg = f"Argument --{argname} has no corresponding value"
            parser.print_usage()
            raise SystemExit(msg)
        except ValueError:
            pass
        for arg in args:
            if arg.startswith(f'--{argname}='):
                return arg.split(f'--{argname}=', 1)[1]

    def get_project_name(proj):
        return get_output([sys.executable, *setup_py(proj), '--name'], cwd=str(proj))

    def get_build_requires(proj, args):
        arg = 'setup-requires'
        requires = getargvalue(arg, args)
        if requires is not None:
            print(f"Using build requirements from --{arg} command line argument")
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

    def get_run_requires(proj, args):
        arg = 'install-requires'
        requires = getargvalue(arg, args)
        if requires is not None:
            print(f"Using run requirements from --{arg} command line argument")
            return split(requires)
        requires = get_setup_cfg_entry(proj, "dist_conda", "setup_requires")
        if requires is not None:
            print("Using run requirements from [dist_conda]/setup_requires")
            return requires
        with tempfile.TemporaryDirectory(prefix='egg-info-tempdir-') as tempdir:
            get_output(
                [
                    sys.executable,
                    *setup_py(proj),
                    'egg_info',
                    '--egg-base',
                    tempdir,
                ],
                cwd=str(proj),
            )
            egg_info = [
                f
                for f in Path(tempdir).iterdir()
                if f.name.endswith('.egg-info') and f.is_dir()
            ]
            if not egg_info:
                msg = "no .egg-info directory after running setup.py egg_info"
                raise RuntimeError(msg)
            if len(egg_info) > 1:
                msg = "multiple .egg-info directories after running setup.py egg_info"
                raise RuntimeError(msg)
            requires_file = Path(egg_info[0], 'requires.txt')
            if requires_file.exists():
                requires = requires_file.read_text().splitlines()
            else:
                requires = []
        # Ignore extras sections:
        for i, item in enumerate(requires):
            if not item.strip() or item.startswith('['):
                requires = requires[:i]
                break
        if requires:
            print("Using run requirements from egg_info")
            return requires
        print("No run requirements")
        return []

    def get_channels(proj, args):
        arg = 'channels'
        chans = getargvalue(arg, args)
        if chans is not None:
            print(f"Using extra channels from --{arg} command line argument")
            return split(chans)
        channels = get_setup_cfg_entry(proj, "dist_conda", "channels")
        if channels is not None:
            print("Using extra channels from [dist_conda]/channels")
            return channels
        print("No extra channels")
        return []

    def get_name_differences(proj, args):
        arg = 'conda-name-differences'
        name_differences = getargvalue(arg, args)
        if name_differences is not None:
            print(f"Using name differences from --{arg} command line argument")
            return dict(split(item, ':') for item in split(name_differences))
        name_differences = get_setup_cfg_entry(
            proj, "dist_conda", "conda_name_differences"
        )
        if name_differences is not None:
            print("Using extra channels from [tools.setuptools-conda]/channels")
            return dict(split(item, ':') for item in name_differences)
        print("No name differences")
        return {}

    def remove_projects(requirements, projects):
        """Remove any requirements on the given projects from the given requirements
        list, modifying it in-place."""
        splitchars = ' <>=!'
        for requirement in requirements[:]:
            name = requirement
            for char in splitchars:
                name = name.split(char, 1)[0]
            if name in projects:
                print(f'Ignoring requirement {requirement}')
                requirements.remove(requirement)

    # For the build command we'll parse setup_args and project_path ourselves, in order
    # to workaround https://bugs.python.org/issue9334:
    args, _ = parser.parse_known_args()
    CMD = args.command
    if CMD == 'build':
        setup_args = sys.argv[2:-1]
        args.projects = [sys.argv[-1]]
    else:
        # Otherwise we parse normally
        args = parser.parse_args()

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
        run_conda_cmd(['conda', 'install', '-y'] + need)

    from setuptools_conda.setuptools_conda import (
        get_pyproject_toml_entry,
        get_setup_cfg_entry,
        evaluate_requirements,
        condify_requirement,
        split,
        setup_py,
        run,
    )

    all_build_requires = []
    project_names = []

    additional_args = setup_args if CMD == 'build' else args

    print("\nGetting build requirements...")
    # Get all build requires:
    channels = []
    for project_path in args.projects:
        proj = Path(project_path)
        build_requires = get_build_requires(proj, additional_args)
        name_differences = get_name_differences(proj, additional_args)
        build_requires = [
            condify_requirement(s, name_differences)
            for s in evaluate_requirements(build_requires)
        ]
        all_build_requires.extend(build_requires)
        channels += get_channels(proj, additional_args)
    chan_args = []
    for chan in set(channels):
        chan_args += ['--channel', chan]

    # Remove duplicates:
    all_build_requires = list(set(all_build_requires))

    # Install them:
    if all_build_requires:
        run_conda_cmd(['conda', 'install', '-y'] + chan_args + all_build_requires)

    if CMD == 'build':
        print("\nBuilding...")
        proj = Path(args.projects[0])
        sys.exit(
            run(
                [sys.executable, *setup_py(proj), 'dist_conda'] + setup_args,
                cwd=str(proj),
            )
        )

    print("\nGetting run requirements...")
    all_run_requires = []
    project_names = []
    for project_path in args.projects:
        proj = Path(project_path)
        project_name = get_project_name(proj)
        project_names.append(project_name)
        name_differences = get_name_differences(proj, additional_args)
        run_requires = get_run_requires(proj, additional_args)
        run_requires = [
            condify_requirement(s, name_differences)
            for s in evaluate_requirements(run_requires)
        ]
        all_run_requires.extend(run_requires)

    # Remove exact duplicates:
    all_run_requires = list(set(all_run_requires))

    # Remove any projects we're installing requirements *for* from the list of
    # requirements to install:
    remove_projects(all_run_requires, project_names)

    # Install them:
    if all_run_requires:
        run_conda_cmd(['conda', 'install', '-y'] + all_run_requires)


if __name__ == '__main__':
    main()
