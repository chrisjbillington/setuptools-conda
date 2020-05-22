import sys
import os
import shutil
from subprocess import check_call
from setuptools import Command
import json
from textwrap import dedent
import hashlib

# Mapping of supported Python environment markers usable in setuptools requirements
# lists to conda bools. We will translate for example 'sys_platform==win32' to [win32],
# which is the conda equivalent. `python_version` is handled separately.
PLATFORM_VAR_TRANSLATION = {
    'sys_platform': {'win32': 'win', 'linux': 'linux', 'darwin': 'osx'},
    'platform_system': {'Windows': 'win', 'Linux': 'linux', 'Darwin': 'osx'},
    'os_name': {'nt': 'win', 'posix': 'unix'},
    'platform_machine': {'x86_64': 'x86_64'},
}

_here = os.path.dirname(os.path.abspath(__file__))
CONDA_BUILD_TEMPLATE = os.path.join(_here, 'conda_build_config.yaml.template')
META_YAML_TEMPLATE = os.path.join(_here, 'meta.yaml.template')


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


def _split(s, delimiter=','):
    """Split a string on given delimiter or newlines and return the results stripped of
    whitespace"""
    return [item.strip() for item in s.replace(delimiter, '\n').splitlines()]


def condify_requirements(requires, extras_require, name_replacements):
    """Convert requirements in the format of `setuptools.Distribution.install_requires`
    and `setuptools.Distribution.extras_require` to the format required by conda"""
    result = []
    requires = requires.copy()
    for qualifier, requirements in extras_require.items():
        qualifier = qualifier.replace(':', '')
        for requirement in requirements:
            requires.append('%s; %s' % (requirement, qualifier))

    for line in requires:
        # Do any name substitutions:
        parts = line.split(';', 1)
        for pypiname, condaname in name_replacements.items():
            parts[0] = parts[0].replace(pypiname, condaname)
        # Lower-case the package name:
        parts[0] = parts[0].lower()
        line = ';'.join(parts)
        # Put any platform/version selector into conda format:
        if ';' in line:
            requirement, qualifier = line.split(';')
            # delete quotes and the dot in the Python version, making it an int:
            for char in '\'".':
                qualifier = qualifier.replace(char, '')
            line = requirement.strip() + ' # [' + qualifier.strip() + ']'
        # Replace all runs of whitespace with a single space
        line = ' '.join(line.split())
        # Remove whitespace around operators:
        for operator in ['==', '!=', '<', '>', '<=', '>=']:
            line = line.replace(' ' + operator, operator)
            line = line.replace(operator + ' ', operator)
        if '~=' in line:
            raise ValueError("setuptools_conda does not support '~= version operator'")

        # Replace Python version variable with conda equivalent:
        line = line.replace('python_version', 'py')

        # Replace var== and var!= with conda bools and their negations:
        for platform_var, mapping in PLATFORM_VAR_TRANSLATION.items():
            for value, conda_bool in mapping.items():
                line = line.replace(f'{platform_var}=={value}', conda_bool)
                line = line.replace(f'{platform_var}!={value}', 'not ' + conda_bool)
        result.append(line)

    return result


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
                `command_options`. Defaults to the list of Python versions found in
                package classifiers of the form 'Programming Language :: Python :: 3.7'
                or the current Python version if none present.
                """
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
                Defaults to the `setup_requires` argument to `setup()`, and can
                therefore be omitted if the build dependencies when building for conda
                do not differ."""
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
            'conda-name-differences=',
            None,
            dedent(
                """\
                Mapping of PyPI package names to conda package names, as a
                comma-separated list of colon-separated names, e.g.
                'PyQt5:pyqt,beautifulsoup4:beautiful-soup'. Also accepts a dict if
                passed into `setup()` via `command_options`. Conda packages usually
                share a name with their PyPI equivalents, but use this option to specify
                the mapping when they differ. If the only difference is case, no entry 
                is needed - names will automatically be converted to lower case."""
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
                Build platform-independent packages. Only set this if your dependencies
                are the same on all platforms and Python versions you support, and you
                have no compiled extensions."""
            ),
        ),
        # (
        #     'conda-input-dist-type',
        #     None,
        #     dedent(
        #         """\

        #         'sdist', or 'wheel': What kind of dist, to initially build and pass
        #         specify """
        #     ),
        # ),
    ]

    BUILD_DIR = 'conda_build'
    RECIPE_DIR = os.path.join(BUILD_DIR, 'recipe')
    CONDA_BLD_PATH = os.path.join(BUILD_DIR, 'conda-bld')
    DIST_DIR = 'conda_packages'

    def initialize_options(self):
        if not os.getenv('CONDA_PREFIX'):
            raise RuntimeError("Must activate a conda environment to run dist_conda")
        self.VERSION = self.distribution.get_version()
        self.NAME = self.distribution.get_name()
        self.setup_requires = None
        self.install_requires = None
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

    def finalize_options(self):
        if self.license_file is None:
            msg = """No file called LICENSE, COPYING or COPYRIGHT with any extension
                found"""
            raise RuntimeError(dedent(msg))
        if isinstance(self.pythons, str):
            self.pythons = _split(self.pythons)
        self.build_number = int(self.build_number)
        if self.license_file == 'None':
            self.license_file = None
        if self.license_file is not None and not os.path.exists(self.license_file):
            raise ValueError("License file %s 'doesn't exist'" % self.license_file)

        if isinstance(self.conda_name_differences, str):
            self.conda_name_differences = dict(
                _split(item, ':') for item in _split(self.conda_name_differences)
            )

        if self.setup_requires is None:
            self.SETUP_REQUIRES = condify_requirements(
                self.distribution.setup_requires, {}, self.conda_name_differences
            )
        else:
            if isinstance(self.setup_requires, str):
                self.setup_requires = _split(self.setup_requires)
            self.SETUP_REQUIRES = condify_requirements(
                self.setup_requires, {}, self.conda_name_differences
            )

        if self.install_requires is None:
            self.RUN_REQUIRES = condify_requirements(
                self.distribution.install_requires,
                self.distribution.extras_require,
                self.conda_name_differences,
            )
        else:
            if isinstance(self.install_requires, str):
                self.install_requires = _split(self.install_requires)
            self.RUN_REQUIRES = condify_requirements(
                self.install_requires, {}, self.conda_name_differences
            )

        if isinstance(self.link_scripts, str):
            link_scripts = {}
            for name in _split(self.link_scripts):
                with open(name) as f:
                    link_scripts[os.path.basename(name)] = f.read()
            self.link_scripts = link_scripts

        self.noarch = bool(self.noarch)

        if self.pythons and self.noarch:
            msg = """Can't specify `pythons` and `noarch` simultaneously"""
            raise ValueError(msg)

        if not (self.pythons or self.noarch):
            for line in self.distribution.get_classifiers():
                parts = [s.strip() for s in line.split('::')]
                if len(parts) == 3 and parts[0:2] == ['Programming Language', 'Python']:
                    if len(parts[2].split('.')) == 2:
                        self.pythons.append(parts[2])
        if not self.pythons:
            self.pythons = [f'{sys.version_info.major}.{sys.version_info.minor}']

    def run(self):
        # Clean
        shutil.rmtree(self.BUILD_DIR, ignore_errors=True)
        shutil.rmtree('build', ignore_errors=True)
        os.makedirs(self.RECIPE_DIR)

        # Run sdist to make a source tarball in the recipe dir:
        check_call(
            # [
            #     sys.executable,
            #     'setup.py',
            #     'bdist_wheel',
            #     '--dist-dir=' + self.BUILD_DIR,
            # ]
            [sys.executable, 'setup.py', 'bdist_wheel', '--dist-dir=' + self.BUILD_DIR]
        )

        # dist = '%s-%s.tar.gz' % (self.NAME, self.VERSION)
        (dist,) = [p for p in os.listdir(self.BUILD_DIR) if p.endswith('.whl')]
        with open(os.path.join(self.BUILD_DIR, dist), 'rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        # Build config:
        build_config_yaml = os.path.join(self.RECIPE_DIR, 'conda_build_config.yaml')
        with open(build_config_yaml, 'w') as f:
            f.write('\n'.join(yaml_lines({'python': self.pythons})))

        # Recipe:
        package_details = {
            'package': {'name': self.NAME, 'version': self.VERSION,},
            'source': {'url': f'../{dist}', 'sha256': sha256},
            'build': {
                # 'script': "{{ PYTHON }} -m pip install . -vv",
                'number': self.build_number,
            },
            'requirements': {
                'build': [],
                'host': ['python', 'pip', 'wheel'] + self.SETUP_REQUIRES,
                'run': ['python'] + self.RUN_REQUIRES,
            },
            'about': {
                'home': self.HOME,
                'summary': self.SUMMARY,
                'license': self.LICENSE,
            },
        }

        with open(os.path.join(self.RECIPE_DIR, 'build.sh'), 'w') as f:
            f.write(
                dedent(
                    f"""\
                    #!/bin/bash
                    set -ex
                    unset _PYTHON_SYSCONFIGDATA_NAME
                    unset _CONDA_PYTHON_SYSCONFIGDATA_NAME
                    "$PYTHON" -m pip install {dist}
                    """
                )
            )

        with open(os.path.join(self.RECIPE_DIR, 'bld.bat'), 'w') as f:
            f.write(
                dedent(
                    f"""\
                    set _PYTHON_SYSCONFIGDATA_NAME=
                    set _CONDA_PYTHON_SYSCONFIGDATA_NAME=
                    %PYTHON% -m pip install {dist}
                    EXIT /B %ERRORLEVEL%
                    """
                )
            )


        if self.noarch:
            package_details['build']['noarch'] = 'python'
        if self.build_string is not None:
            package_details['build']['string'] = self.build_string
        if self.distribution.entry_points is not None:
            console_scripts = self.distribution.entry_points.get('console_scripts', [])
            gui_scripts = self.distribution.entry_points.get('gui_scripts', [])
            package_details['build']['entry_points'] = console_scripts + gui_scripts
        if self.license_file is not None:
            # package_details['about']['license_file'] = self.license_file
            shutil.copy(self.license_file, self.BUILD_DIR)
            package_details['about']['license_file'] = f'../{self.license_file}'

        if False: #self.distribution.ext_modules is not None:
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

        environ = os.environ.copy()
        environ['CONDA_BLD_PATH'] = os.path.abspath(self.CONDA_BLD_PATH)
        check_call(
            ['conda-build', '--no-test', self.RECIPE_DIR,], env=environ,
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
