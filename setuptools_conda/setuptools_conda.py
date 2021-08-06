import sys
import os
import shutil
from subprocess import call
import shlex
from setuptools import Command
import json
from textwrap import dedent
import hashlib
from pathlib import Path
import configparser
import re
import itertools

import toml
import distlib.markers


if not os.getenv('CONDA_PREFIX'):
    msg = "You cannot use setuptools-conda outside of a conda environment"
    raise EnvironmentError(msg)


# Mapping of supported Python environment markers usable in setuptools requirements
# lists to conda bools. We will translate for example 'sys_platform==win32' to [win],
# which is the conda equivalent. `python_version` is handled separately.
PLATFORM_VAR_TRANSLATION = {
    'sys_platform': {'win32': 'win', 'linux': 'linux', 'darwin': 'osx'},
    'platform_system': {'Windows': 'win', 'Linux': 'linux', 'Darwin': 'osx'},
    'os_name': {'nt': 'win', 'posix': 'unix'},
    'platform_machine': {
        'x86_64': 'x86_64',
        'AMD64': 'x86_64',
        'arm64': 'arm64',
        'i386': 'x86',
    },
}


# Command line args that can be used in place of "setup.py" for projects that lack a
# setup.py, runs a minimal setup.py similar to what pip does for projects with no
# setup.py.
_SETUP_PY_STUB = [
    "-c",
    'import sys, setuptools; sys.argv[0] = __file__ = "setup.py"; setuptools.setup()',
]


def run(cmd, **kwargs):
    print('[running]:', *[shlex.quote(arg) for arg in cmd])
    rc = call(cmd, **kwargs)
    if rc:
        sys.exit(rc)
    return rc


def setup_py(project_dir):
    """Returns a list of command line arguments to be used in place of ["setup.py"]. If
    setup.py exists, then this is just ["setup.py"]. Otherwise, if setup.cfg or
    pyproject.toml exists, returns args that pass a code snippet to Python with "-c" to
    execute a minimal setup.py calling setuptools.setup(). If none of pyproject.toml,
    setup.cfg, or setup.py exists, raises an exception."""
    if Path(project_dir, 'setup.py').exists():
        return ['setup.py']
    elif any(Path(project_dir, s).exists() for s in ['setup.cfg', 'pyproject.toml']):
        return _SETUP_PY_STUB
    msg = f"""{project_dir} does not look like a python project directory: contains no
        setup.py, setup.cfg, or pyproject.toml"""
    raise RuntimeError(' '.join(msg.split))


# Couldn't figure out how to use PyYAML to produce output looking like conda recipes are
# usually formatted:
def yaml_lines(obj, indent=2):
    lines = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list, tuple)):
                lines.append(f'{key}:')
                for line in yaml_lines(value):
                    lines.append((' ' * indent + line).rstrip())
                if lines and lines[-1]:
                    lines.append('')
            else:
                lines.append(f'{key}: {value}')
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            for line in yaml_lines(item):
                lines.append(line.rstrip())
        if lines and lines[-1]:
            lines.append('')
    else:
        lines.append(f'- {obj}')
    return lines


def split(s, delimiter=','):
    """Split a string on given delimiter or newlines and return the results stripped of
    whitespace"""
    return [
        item.strip() for item in s.replace(delimiter, '\n').splitlines() if item.strip()
    ]


def split_requirement(requirement):
    """split a requirements line such as "foo<7,>2; sys_platform == 'win32'" into
    ("foo", "<7,>2", "sys_platform == 'win32'")"""
    splitchars =' \t~<>=!;'
    name = requirement
    for char in splitchars:
        name = name.split(char, 1)[0].strip()
    rest = requirement[len(name) :].strip()
    if not rest:
        version_specifiers = env_marker = ""
    elif ';' in rest:
        version_specifiers, env_marker = rest.split(';', 1)
    else:
        version_specifiers = rest
        env_marker = ""
    if not version_specifiers.strip():
        version_specifiers = None
    if not env_marker.strip():
        env_marker = None
    return name, version_specifiers, env_marker


def condify_name(name, name_replacements=None):
    """Given a name, replace the package name with its entry, if any, in the dict
    name_replacements, otherwise make the package name lowercase and replace,
    underscores with hyphens."""
    if name_replacements is None:
        name_replacements = {}
    return name_replacements.get(name, name.lower().replace("_", "-"))


def _version_split(version):
    # Copied from packaging.specifiers.py, used by condify_version_specifier to extract
    # prefix used for "compatible" version operator
    _prefix_regex = re.compile(r"^([0-9]+)((?:a|b|c|rc)[0-9]+)$")
    result = []
    for item in version.split("."):
        match = _prefix_regex.search(item)
        if match:
            result.extend(match.groups())
        else:
            result.append(item)
    return result


def _get_compatible_prefix(version):
    # Get everything except the last item in the version, but ignore post and dev
    # releases and treat the pre-release as its own segment. This logic copied from
    # packaging.specifiers.Specifier._compare_compatible() in order to be PEP440
    # compliant. Don't append ".*" - this is superfluous and deprecated in conda.
    return ".".join(
        list(
            itertools.takewhile(
                lambda x: (not x.startswith("post") and not x.startswith("dev")),
                _version_split(version),
            )
        )[:-1]
    )


def condify_version_specifier(specifier):
    OPERATORS = [
        "~=",
        "==",
        "!=",
        "<=",
        ">=",
        "<",
        ">",
        "===",
    ]
    # Remove all whitespace:
    specifier = specifier.replace(' ', '').replace('\t', '')
    # Find the operator:
    for operator in OPERATORS:
        if specifier.startswith(operator):
            break
    else:
        raise ValueError(f"invalid specifier {specifier}")

    _, version = specifier.split(operator, 1)

    if operator == '===':
        msg = """The '====' (arbitrary) version operator has no conda equivalent and is
            not supported"""
        raise ValueError(' '.join(msg.split()))
    elif operator == '~=':
        # Conda doesn't support ~=X.Y, but is equivalent to a >=X.Y,==X:
        return f'>={version},=={_get_compatible_prefix(version)}'
    elif version.endswith('.*'):
        # PEP440 '==X.Y.*' is equivalent to conda '==X.Y' 
        return f'{operator}{version[:-2]}'
    else:
        return specifier


def condify_version_specifiers(specifiers):
    return ','.join(condify_version_specifier(s) for s in specifiers.split(','))


def condify_env_marker(env_marker):
    """convert setuptools env_marker such as sys_platform == 'win32' into their conda
    equivalents, e.g. 'win'"""
    # delete quotes and the dot in the Python version, making it an int:
    for char in '\'".':
        env_marker = env_marker.replace(char, '')
    # Replace all runs of whitespace with a single space
    env_marker = ' '.join(env_marker.split())
    # Remove whitespace around operators:
    for operator in ['==', '!=', '<', '>', '<=', '>=']:
        env_marker = env_marker.replace(' ' + operator, operator)
        env_marker = env_marker.replace(operator + ' ', operator)

    # Replace Python version variable with conda equivalent:
    env_marker = env_marker.replace('python_version', 'py')

    # Replace var== and var!= with conda bools and their negations:
    for platform_var, mapping in PLATFORM_VAR_TRANSLATION.items():
        for value, conda_bool in mapping.items():
            env_marker = env_marker.replace(f'{platform_var}=={value}', conda_bool)
            env_marker = env_marker.replace(
                f'{platform_var}!={value}', 'not ' + conda_bool
            )
    return env_marker


def condify_requirement(requirement, name_replacements=None):
    """Convert a single requirement line in the format of
    `setuptools.Distribution.install_requires` and
    `setuptools.Distribution.extras_require` to the format required by conda"""
    if name_replacements is None:
        name_replacements = {}
    name, version_specifiers, env_marker = split_requirement(requirement)
    name = condify_name(name, name_replacements)
    if version_specifiers is not None:
        version_specifiers = condify_version_specifiers(version_specifiers)
    if env_marker is not None:
        env_marker = condify_env_marker(env_marker)
    result = name
    if version_specifiers is not None:
        result += f' {version_specifiers}'
    if env_marker is not None:
        result += f' # [{env_marker}]'
    return result


def condify_requirements(requires, name_replacements):
    """Convert requirements in the format of `setuptools.Distribution.install_requires`
    and `setuptools.Distribution.extras_require` to the format required by conda"""
    return [condify_requirement(line, name_replacements) for line in requires]


def get_setup_cfg_entry(proj, section, key, is_list=True):
    """Return setup_requires as read from proj/setup.cfg, if any"""
    setup_cfg = Path(proj, 'setup.cfg')
    if not setup_cfg.exists():
        return None
    config = configparser.ConfigParser()
    config.read("setup.cfg")
    try:
        value = config.get(section, key)
    except (configparser.NoOptionError, configparser.NoSectionError):
        return None
    if is_list:
        return split(value)
    return value


def get_pyproject_toml_entry(proj, *keys):
    """Return [build-system] requires as read from proj/pyproject.toml, if any"""
    pyproject_toml = Path(proj, 'pyproject.toml')
    if not pyproject_toml.exists():
        return None
    config = toml.load(pyproject_toml)
    try:
        for key in keys:
            config = config[key]
        return config
    except KeyError:
        return None


def evaluate_requirements(entries):
    """Evaluate env markers and return a list of the requirements that are needed in the
    current environment required"""
    requirements = []
    for entry in entries:
        entry = entry.replace(" ", "")
        if not entry:
            continue
        if ';' not in entry:
            requirements.append(entry)
            continue
        requirement, marker = entry.split(';', 1)
        if distlib.markers.interpret(marker):
            requirements.append(requirement)
    return requirements


class dist_conda(Command):
    description = "Make conda packages"
    user_options = [
        (
            'pythons=',
            None,
            dedent(
                """\
                Minor Python versions to build for, as a comma-separated list e.g. '2.7,
                3.6'. Also accepts a list of strings if passed into `setup()` via
                `command_options`. Defaults to the current Python version."""
            ),
        ),
        ('build-number=', 'n', "Conda build number. Defaults to zero"),
        (
            'license-file=',
            'l',
            dedent(
                """\
                License file to include in the conda package. Defaults to any file in
                the working directory named 'LICENSE', 'COPYING', or 'COPYRIGHT', case
                insensitive and ignoring extensions. Set to 'None' to not include a
                license file even if one of the above is present."""
            ),
        ),
        ('build-string=', 's', "Conda build string."),
        (
            'setup-requires=',
            None,
            dedent(
                """\
                Build dependencies, as a comma-separated list in standard setuptools
                format, e.g. 'foo >= 2.0; sys_platform=="win32",bar==2.3'. Also accepts
                a list of strings if passed into `setup()` via `command_options`.
                Defaults to any requirements listed in a `pyproject.toml` under
                [build-system]/requires, or if none, any requirements listed in the
                `setup_requires` setuptools configuration option. Can be be omitted if
                the build dependencies when building for conda do not differ."""
            ),
        ),
        (
            'install-requires=',
            None,
            dedent(
                """\
                Runtime dependencies, as a comma-separated list in standard setuptools
                format, e.g. 'foo >= 2.0; sys_platform=="win32",bar==2.3'. Also accepts
                a list of strings if passed into `setup()` via `command_options`.
                Defaults to the `install_requires` argument to `setup()`, and can
                therefore be omitted if the runtime dependencies when running in conda
                do not differ."""
            ),
        ),
        (
            'ignore-run-exports=',
            None,
            dedent(
                """\
                Comma-separated list of conda packages that should *not* be considered
                runtime dependencies, even if they are declared in run_exports of a
                build dependency. run_exports declared by build dependencies are
                normally automatically considered run dependencies, for example
                libraries that were linked against at build-time - but this can be
                undesirable when it creates a brittle dependency on a specific version
                of a library which is not actually required at runtime. Also accepts a
                list of strings if passed into `setup()` via `command_options`."""
            ),
        ),
        (
            'channels=',
            'c',
            dedent(
                """\
                Additional channels to search for build requirements during the build,
                as a comma-separated list, or a list of strings if passed in via
                setup.py. Defaults to [tools.setuptools-conda]/channels listed in a
                `pyproject.toml` file, if any."""
            ),
        ),
        (
            'conda-name-differences=',
            None,
            dedent(
                """\
                Mapping of PyPI package names to conda package names, as a
                comma-separated list of colon-separated names, e.g.
                'PyQt5:pyqt,beautifulsoup4:beautiful-soup'. Also accepts a dict if
                passed into `setup()` via `command_options`. Conda packages usually
                share a name with their PyPI equivalents, but use this option to specify
                the mapping when they differ. If the only difference is lowercasing or
                conversion of underscores into hyphens, no entry is needed - these
                changes are made automatically."""
            ),
        ),
        (
            'link-scripts=',
            None,
            dedent(
                """\
                Comma-separated list of link scripts to include, such as post-link.sh,
                pre-unlink.bat etc. These will be placed in the recipe directory before
                building. If passed to `setup()` via `command_options`, this shound
                instead be a dictionary mapping link script filenames to their
                contents."""
            ),
        ),
        (
            'noarch',
            None,
            dedent(
                """\
                Build a platform-independent package. Only set this if your dependencies
                are the same on all platforms and Python versions you support, and you
                have no compiled extensions."""
            ),
        ),
        (
            'from-wheel',
            None,
            dedent(
                """\
                Whether to build a wheel before invoking conda-build. By default
                setuptools-conda invokes conda-build on an sdist such that any
                compilation of extensions will be done in the conda build environment.
                However, if your extensions are not able to be compiled with conda's
                compiler configuration, you might set this option to pass conda-build a
                wheel that has been pre-compiled with the system configuration. In this
                case, setuptools-conda will only produce a conda package for the current
                Python version."""
            ),
        ),
        (
            'from-downloaded-wheel',
            None,
            dedent(
                """\
                Whether to avoid local building at all and download a wheel from PyPI
                before invoking conda-build. For projects with tricky build environment
                requirements, this can be a way to essentially repackage an existing
                wheel without having to any building at all. Requires that the exact
                version as understood by setuptools is availalble on PyPI as a wheel. In
                this case, setuptools-conda will only produce a conda package for the
                current Python version."""
            ),
        ),
    ]

    BUILD_DIR = 'conda_build'
    RECIPE_DIR = os.path.join(BUILD_DIR, 'recipe')
    CONDA_BLD_PATH = os.path.join(BUILD_DIR, 'conda-bld')
    DIST_DIR = 'conda_packages'

    def initialize_options(self):
        self.VERSION = self.distribution.get_version()
        self.NAME = condify_name(self.distribution.get_name())
        self.setup_requires = None
        self.install_requires = None
        self.ignore_run_exports = []
        self.channels = None
        self.HOME = self.distribution.get_url()
        self.LICENSE = self.distribution.get_license()
        self.SUMMARY = self.distribution.get_description()

        self.license_file = None
        for filename in os.listdir('.'):
            if os.path.splitext(filename.upper())[0] in [
                'LICENSE',
                'COPYING',
                'COPYRIGHT',
            ]:
                self.license_file = filename
                break
        self.pythons = []
        self.build_number = 0
        self.conda_name_differences = {}
        self.build_string = None
        self.link_scripts = {}
        self.noarch = False
        self.from_wheel = False
        self.from_downloaded_wheel = False

    def finalize_options(self):
        if self.license_file is None:
            msg = """No file called LICENSE, COPYING or COPYRIGHT with any extension
                found"""
            raise RuntimeError(dedent(msg))
        if isinstance(self.pythons, str):
            self.pythons = split(self.pythons)
        self.build_number = int(self.build_number)
        if self.license_file == 'None':
            self.license_file = None
        if self.license_file is not None and not os.path.exists(self.license_file):
            raise ValueError("License file %s 'doesn't exist'" % self.license_file)

        if isinstance(self.conda_name_differences, str):
            self.conda_name_differences = dict(
                split(item, ':') for item in split(self.conda_name_differences)
            )

        if self.setup_requires is None:
            setup_requires = get_pyproject_toml_entry('.', 'build-system', 'requires')
            if setup_requires is None:
                setup_requires = self.distribution.setup_requires
            self.SETUP_REQUIRES = condify_requirements(
                setup_requires, self.conda_name_differences
            )
        else:
            if isinstance(self.setup_requires, str):
                self.setup_requires = split(self.setup_requires)
            self.SETUP_REQUIRES = condify_requirements(
                self.setup_requires, self.conda_name_differences
            )

        if self.install_requires is None:
            self.RUN_REQUIRES = condify_requirements(
                self.distribution.install_requires, self.conda_name_differences,
            )
        else:
            if isinstance(self.install_requires, str):
                self.install_requires = split(self.install_requires)
            self.RUN_REQUIRES = condify_requirements(
                self.install_requires, self.conda_name_differences
            )

        if isinstance(self.ignore_run_exports, str):
            self.ignore_run_exports = split(self.ignore_run_exports)

        if self.channels is None:
            self.channels = get_pyproject_toml_entry(
                '.', 'tools', 'setuptools-conda', 'channels'
            )
            if self.channels is None:
                self.channels = []
        elif isinstance(self.channels, str):
            self.channels = split(self.channels)

        if isinstance(self.link_scripts, str):
            link_scripts = {}
            for name in split(self.link_scripts):
                with open(name) as f:
                    link_scripts[os.path.basename(name)] = f.read()
            self.link_scripts = link_scripts

        self.noarch = bool(self.noarch)

        if self.pythons and self.noarch:
            msg = """Can't specify `pythons` and `noarch` simultaneously"""
            raise ValueError(msg)

        if self.pythons and (self.from_wheel or self.from_downloaded_wheel):
            msg = """Can't specify `pythons` if `from_wheel or `from_downloaded_wheel`
                is set"""
            raise ValueError(' '.join(msg.split()))

        if not self.pythons:
            self.pythons = [f'{sys.version_info.major}.{sys.version_info.minor}']

    def run(self):
        # Clean
        shutil.rmtree(self.BUILD_DIR, ignore_errors=True)
        shutil.rmtree('build', ignore_errors=True)
        os.makedirs(self.RECIPE_DIR)

        if self.from_downloaded_wheel:
            # Download a wheel:
            cmd = [
                'pip',
                'download',
                '--only-binary=:all:',
                '--no-deps',
                '--dest',
                self.BUILD_DIR,
                f'{self.NAME}=={self.VERSION}',
            ]
            run(cmd)

        else:
            # Run sdist or bdist_wheel to make a source tarball or wheel in the recipe
            # dir:
            cmd = [sys.executable, *setup_py('.')]
            if self.from_wheel:
                cmd += ['bdist_wheel']
            else:
                cmd += ['sdist', '--formats=gztar']
            cmd += ['--dist-dir=' + self.BUILD_DIR]

        run(cmd)

        if self.from_wheel or self.from_downloaded_wheel:
            dist = [p for p in os.listdir(self.BUILD_DIR) if p.endswith('.whl')][0]
        else:
            dist = f'{self.distribution.get_name()}-{self.VERSION}.tar.gz'

        with open(os.path.join(self.BUILD_DIR, dist), 'rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        # Build config:
        build_config_yaml = os.path.join(self.RECIPE_DIR, 'conda_build_config.yaml')
        with open(build_config_yaml, 'w') as f:
            f.write('\n'.join(yaml_lines({'python': self.pythons})))

        pip_target = dist if (self.from_wheel or self.from_downloaded_wheel) else '.'

        # Recipe:
        package_details = {
            'package': {'name': self.NAME, 'version': self.VERSION,},
            'source': {'url': f'../{dist}', 'sha256': sha256},
            'build': {
                'script': "{{ PYTHON }} -m pip install " + pip_target,
                'number': self.build_number,
            },
            'requirements': {
                'build': [],
                'host': ['python', 'pip', 'wheel'] + self.SETUP_REQUIRES,
                'run': ['python'] + self.RUN_REQUIRES,
            },
            'about': {
                'home': self.HOME,
                'summary': repr(self.SUMMARY),
                'license': repr(self.LICENSE),
            },
        }

        if self.noarch:
            package_details['build']['noarch'] = 'python'
        if self.build_string is not None:
            package_details['build']['string'] = self.build_string
        if self.ignore_run_exports:
            package_details['build']['ignore_run_exports'] = self.ignore_run_exports
        if self.distribution.entry_points is not None:
            console_scripts = self.distribution.entry_points.get('console_scripts', [])
            gui_scripts = self.distribution.entry_points.get('gui_scripts', [])
            package_details['build']['entry_points'] = console_scripts + gui_scripts
        if self.license_file is not None:
            shutil.copy(self.license_file, self.BUILD_DIR)
            package_details['about']['license_file'] = f'../{self.license_file}'

        if self.distribution.ext_modules is not None and not self.from_wheel:
            compilers = ["{{ compiler('c') }}", "{{ compiler('cxx') }}"]
            package_details['requirements']['build'].extend(compilers)
        else:
            # No need for this section then:
            del package_details['requirements']['build']

        with open(os.path.join(self.RECIPE_DIR, 'meta.yaml'), 'w') as f:
            f.write('\n'.join(yaml_lines(package_details)))

        # Link scripts:
        for name, contents in self.link_scripts.items():
            with open(os.path.join(self.RECIPE_DIR, name), 'w') as f:
                f.write(contents)

        # Arguments for extra channels to be searched during build:
        channel_args = []
        for chan in self.channels:
            channel_args += ['-c', chan]

        environ = os.environ.copy()
        environ['CONDA_BLD_PATH'] = os.path.abspath(self.CONDA_BLD_PATH)
        run(
            ['conda-build', '--no-test', self.RECIPE_DIR] + channel_args, env=environ,
        )

        if self.noarch:
            platform = 'noarch'
        else:
            from conda_build.config import Config

            config = Config()
            platform = config.host_subdir

        repodir = os.path.join(self.CONDA_BLD_PATH, platform)
        with open(os.path.join(repodir, 'repodata.json')) as f:
            pkgs = [os.path.join(repodir, pkg) for pkg in json.load(f)["packages"]]

        if not os.path.exists(self.DIST_DIR):
            os.mkdir(self.DIST_DIR)
        dist_subdir = os.path.join(self.DIST_DIR, platform)
        if not os.path.exists(dist_subdir):
            os.mkdir(dist_subdir)

        for pkg in pkgs:
            print("copying %s to %s" % (os.path.basename(pkg), dist_subdir))
            shutil.copy(pkg, dist_subdir)
