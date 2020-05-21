import sys
import os
from setuptools import setup
import distutils.sysconfig
from pathlib import Path

# Normally packages don't have to do this - the dist_conda command should be
# automatically available. But since we're installing it, it isn't there yet!
from dist_conda import dist_conda
CMDCLASS = {'dist_conda': dist_conda}

VERSION_SCHEME = {
    "version_scheme": os.getenv("SCM_VERSION_SCHEME", "guess-next-dev"),
    "local_scheme": os.getenv("SCM_LOCAL_SCHEME", "node-and-date"),
}

SITE_PACKAGES = distutils.sysconfig.get_python_lib()
dist_conda_path = Path(SITE_PACKAGES).parent / 'distutils' / 'command'
DATA_FILES = [(str(dist_conda_path.relative_to(sys.prefix)), ["dist_conda.py"],)]

setup(
    use_scm_version=VERSION_SCHEME,
    cmdclass=CMDCLASS,
    data_files=DATA_FILES,
)
