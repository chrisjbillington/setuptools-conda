import sys
import os
from setuptools import setup
import sysconfig
from pathlib import Path

# Normally packages don't have to do this - the dist_conda command should be
# automatically available. But since we're installing it, it isn't there yet!
from setuptools_conda.setuptools_conda import dist_conda
CMDCLASS = {'dist_conda': dist_conda}

VERSION_SCHEME = {
    "version_scheme": os.getenv("SCM_VERSION_SCHEME", "guess-next-dev"),
    "local_scheme": os.getenv("SCM_LOCAL_SCHEME", "node-and-date"),
}

SITE_PACKAGES = sysconfig.get_path('purelib')

# Add the dist_conda command to both stdlib distutils (if it exists - will be removed in
# Python 3.12) and the one vendored in setuptools, so the command exists regardless of
# which is in use:
stdlib_distutils = Path(SITE_PACKAGES).parent / 'distutils' / 'command'
setuptools_distutils = Path(SITE_PACKAGES) / 'setuptools' / '_distutils' / 'command'
DATA_FILES = [
    (str(setuptools_distutils.relative_to(sys.prefix)), ["dist_conda.py"]),
]
if stdlib_distutils.exists():
    DATA_FILES.append(
        (str(stdlib_distutils.relative_to(sys.prefix)), ["dist_conda.py"])
    )

setup(
    use_scm_version=VERSION_SCHEME,
    cmdclass=CMDCLASS,
    data_files=DATA_FILES,
)
