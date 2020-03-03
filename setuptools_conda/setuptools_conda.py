import sys
import os
import shutil
from subprocess import check_call, Popen, PIPE
from string import Template
from setuptools import Command
import json
from textwrap import dedent
import hashlib

PLATFORMS = ['win-32', 'win-64', 'linux-32', 'linux-64', 'osx-64']
PLATFORM_QUALIFIERS = ['win32', 'win64', 'linux32', 'linux64', 'osx']
PLATFORMS_TO_QUALIFIERS = dict(zip(PLATFORMS, PLATFORM_QUALIFIERS))

_here = os.path.dirname(os.path.abspath(__file__))
CONDA_BUILD_TEMPLATE = os.path.join(_here, 'conda_build_config.yaml.template')
META_YAML_TEMPLATE = os.path.join(_here, 'meta.yaml.template')


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
        # Replace sys_platform== and != with conda bools and their negations:
        for platform in PLATFORM_QUALIFIERS:
            line = line.replace('sys_platform==%s' % platform, platform)
            line = line.replace('sys_platform!=%s' % platform, 'not ' + platform)
        result.append(line)
    return result


def evaluate_requirements(requires, py, platform):
    """Given a Python major.minor version as a string e.g. '3.6', and a platform
    as a string  e.g. win-32, the qualifiers for each requirement in the list
    and return the requirements that apply"""
    assert platform in PLATFORMS
    platform = PLATFORMS_TO_QUALIFIERS[platform]
    namespace = {plat: plat == platform for plat in PLATFORM_QUALIFIERS}
    # This will break if there's ever a Python 4, but it's how conda does it!
    namespace['py'] = int(py.replace('.', ''))
    results = []
    for line in requires:
        if '#' in line:
            requirement, qualifier = line.split('#')
            qualifier = qualifier.split('[', 1)[1].rsplit(']')[0]
            if eval(qualifier, namespace):
                results.append(requirement)
        else:
            results.append(line)
    return results


def add_requirements(pkgfile, requirements):
    """Add run requirements to the given package file"""
    from conda_build.convert import (
        extract_temporary_directory,
        update_index_file,
        create_target_archive,
    )

    temp_dir = extract_temporary_directory(pkgfile)
    platform = os.path.basename(os.path.dirname(pkgfile))
    update_index_file(temp_dir, platform, requirements, verbose=False)
    output_dir = os.path.dirname(os.path.dirname(pkgfile))
    create_target_archive(pkgfile, temp_dir, platform, output_dir)
    shutil.rmtree(temp_dir)


class NotARepo(OSError):
    pass


def git_call(cmd):
    """Calls a command, raising NotARepo if there is no git repo there."""
    try:
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
    except OSError:
        # Git not installed, or repo path doesn't exist or isn't a directory.
        raise NotARepo(1, cmd, "Couldn't run git command - path might not exist")
    if proc.returncode:
        # Something went wrong - repo got deleted while we were reading it, or something
        # like that.
        raise NotARepo(proc.returncode, cmd, output=(stdout + stderr))
    return stdout.decode('utf8')


class dist_conda(Command):
    description = "Make conda packages"
    user_options = [
        (
            'pythons=',
            None,
            dedent(
                """\
                Minor Python versions to build for, as a comma-separated list e.g.
                '2.7,3.6'. Also accepts a list of strings if passed into `setup()` via
                `command_options`. Defaults to current Python version"""
            ),
        ),
        (
            'platforms=',
            None,
            dedent(
                """\
                Platforms to build for, as a comma-separated list of one or more of
                win-32,win-64,linux-32,linux-64,osx-64, or 'all' for all of them. Also
                accepts a list of strings if passed into `setup()` via
                `command_options`. Defaults to the current platform."""
            ),
        ),
        (
            'force-conversion',
            'f',
            dedent(
                """\
                Perform conversion to other platforms even if the build contains
                platform-specific C extensions or binaries. These extensions will not be
                converted, but this may be acceptable if for example the package bundles
                precompiled executables or libraries for multiple platforms, that it
                laods dynamically."""
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
                the mapping when they differ."""
            ),
        ),
        (
            'no-dev-buildstring',
            None,
            dedent(
                """\
                Disable the following behavuour: If no build string is given and the
                package version contains the string 'dev', and the current working
                directory is a git repository (and the git executable can be found),
                then setuptools_conda will set the build string to
                'pyXY_<branchname>_<shorthash>_<buildnumber>'. Any hyphens in the branch
                name are replaced by underscores. This is useful to create
                uniquely-named builds for testing unmerged pull requests, etc."""
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
    ]

    BUILD_DIR = 'conda_build'
    RECIPE_DIR = os.path.join(BUILD_DIR, 'recipe')
    CONDA_BLD_PATH = os.path.join(BUILD_DIR, 'conda-bld')
    DIST_DIR = 'conda_packages'

    def initialize_options(self):
        if not os.getenv('CONDA_PREFIX'):
            raise RuntimeError("Must activate a conda environment to run dist_conda")
        from conda_build.config import Config

        config = Config()
        self.host_platform = config.host_subdir

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
        self.pythons = '%d.%d' % (sys.version_info.major, sys.version_info.minor)
        self.platforms = self.host_platform
        self.build_number = 0
        self.force_conversion = False
        self.conda_name_differences = {}
        self.build_string = None
        self.no_dev_buildstring = False
        self.link_scripts = {}

    def finalize_options(self):
        if self.license_file is None:
            msg = """No file called LICENSE, COPYING or COPYRIGHT with any extension
                found"""
            raise RuntimeError(dedent(msg))
        if self.platforms == 'all':
            self.platforms = PLATFORMS
        else:
            if isinstance(self.platforms, str):
                self.platforms = self.platforms.split(',')
            if not all(p in PLATFORMS for p in self.platforms):
                raise ValueError("Invalid platform list %s" % str(self.platforms))
        if isinstance(self.pythons, str):
            self.pythons = self.pythons.split(',')
        self.build_number = int(self.build_number)
        if self.license_file == 'None':
            self.license_file = None
        if self.license_file is not None and not os.path.exists(self.license_file):
            raise ValueError("License file %s 'doesn't exist'" % self.license_file)

        if isinstance(self.conda_name_differences, str):
            self.conda_name_differences = dict(
                item.split(':') for item in self.conda_name_differences.split(',')
            )

        if self.setup_requires is None:
            self.BUILD_REQUIRES = condify_requirements(
                self.distribution.setup_requires, {}, self.conda_name_differences
            )
        else:
            if isinstance(self.setup_requires, str):
                self.setup_requires = self.setup_requires.split(',')
            self.BUILD_REQUIRES = condify_requirements(
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
                self.install_requires = self.install_requires.split(',')
            self.RUN_REQUIRES = condify_requirements(
                self.install_requires, {}, self.conda_name_differences
            )


        if (
            'dev' in self.VERSION
            and self.build_string is None
            and not self.no_dev_buildstring
        ):
            try:
                branch = git_call(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip()
                hash = git_call(['git', 'rev-parse', '--short', 'HEAD']).strip()
                self.build_string = '_'.join(
                    [
                        "py{{ CONDA_PY }}",
                        branch.replace('-', '_'),
                        hash,
                        str(self.build_number),
                    ]
                )
            except NotARepo:
                pass

        if isinstance(self.link_scripts, str):
            link_scripts = {}
            for name in self.link_scripts.split(','):
                with open(name) as f:
                    link_scripts[os.path.basename(name)] = f.read()
            self.link_scripts = link_scripts


    def run(self):
        from conda_build.convert import retrieve_python_version

        # Clean
        shutil.rmtree(self.BUILD_DIR, ignore_errors=True)
        os.makedirs(self.RECIPE_DIR)

        # Run sdist to make a source tarball in the recipe dir:
        check_call(
            [
                sys.executable,
                'setup.py',
                'sdist',
                '--dist-dir=' + self.BUILD_DIR,
                '--formats=gztar',
            ]
        )

        tarball = '%s-%s.tar.gz' % (self.NAME, self.VERSION)
        with open(os.path.join(self.BUILD_DIR, tarball), 'rb') as f:
            sha256 = hashlib.sha256(f.read()).hexdigest()

        # Build:
        build_config_yaml = os.path.join(self.RECIPE_DIR, 'conda_build_config.yaml')
        template = Template(open(CONDA_BUILD_TEMPLATE).read())
        with open(build_config_yaml, 'w') as f:
            f.write(template.substitute(PYTHONS='\n  - '.join(self.pythons)))
        template = Template(open(META_YAML_TEMPLATE).read())
        if self.license_file is not None:
            shutil.copy(self.license_file, self.BUILD_DIR)
            license_file_line = "license_file: ../%s" % self.license_file
        else:
            license_file_line = ''
        if self.build_string is not None:
            build_string_line = "string: %s" % self.build_string
        else:
            build_string_line = ''
        with open(os.path.join(self.RECIPE_DIR, 'meta.yaml'), 'w') as f:
            f.write(
                template.substitute(
                    NAME=self.NAME,
                    VERSION=self.VERSION,
                    TARBALL=tarball,
                    SHA256=sha256,
                    BUILD_NUMBER=self.build_number,
                    BUILD_STRING_LINE=build_string_line,
                    BUILD_REQUIRES='\n    - '.join(self.BUILD_REQUIRES),
                    HOME=self.HOME,
                    LICENSE=self.LICENSE,
                    LICENSE_FILE_LINE=license_file_line,
                    SUMMARY=self.SUMMARY,
                )
            )

        # Link scripts:
        for name, contents in self.link_scripts.items():
            with open(os.path.join(self.RECIPE_DIR, name), 'w') as f:
                f.write(contents)

        environ = os.environ.copy()
        environ['CONDA_BLD_PATH'] = os.path.abspath(self.CONDA_BLD_PATH)
        check_call(
            ['conda-build', self.RECIPE_DIR], env=environ,
        )

        repodir = os.path.join(self.CONDA_BLD_PATH, self.host_platform)
        with open(os.path.join(repodir, 'repodata.json')) as f:
            pkgs = [os.path.join(repodir, pkg) for pkg in json.load(f)["packages"]]

        # Copy/Convert all the packages
        converted_dir = os.path.join(self.BUILD_DIR, 'converted')
        os.mkdir(converted_dir)
        for pkg in pkgs:
            if self.host_platform in self.platforms:
                destdir = os.path.join(converted_dir, self.host_platform)
                if not os.path.exists(destdir):
                    os.mkdir(destdir)
                print("copying %s to %s" % (os.path.basename(pkg), destdir))
                shutil.copy(pkg, destdir)

            for build_platform in self.platforms:
                if build_platform != self.host_platform:
                    convert_cmd = ['conda-convert', '-o', converted_dir]
                    if self.force_conversion:
                        convert_cmd += ['-f']
                    convert_cmd += ['-p', build_platform, pkg]
                    check_call(convert_cmd)

        # Add platform-specific requirements:
        for build_platform in self.platforms:
            subdir = os.path.join(converted_dir, build_platform)
            for pkg in os.listdir(subdir):
                pkg = os.path.join(subdir, pkg)
                py = retrieve_python_version(pkg).replace('python', '')
                requirements = evaluate_requirements(
                    self.RUN_REQUIRES, py, build_platform
                )
                print(
                    "Adding requirements to %s"
                    % os.path.join(os.path.sep.join(pkg.split(os.path.sep)[-2:]))
                )
                add_requirements(pkg, requirements)

        # Copy to dist dir:
        print("copying all packages to %s" % self.DIST_DIR)
        if not os.path.exists(self.DIST_DIR):
            os.mkdir(self.DIST_DIR)
        for build_platform in self.platforms:
            dist_subdir = os.path.join(self.DIST_DIR, build_platform)
            if not os.path.exists(dist_subdir):
                os.mkdir(dist_subdir)
            subdir = os.path.join(converted_dir, build_platform)
            for pkg in os.listdir(subdir):
                pkg = os.path.join(subdir, pkg)
                shutil.copy(pkg, dist_subdir)
