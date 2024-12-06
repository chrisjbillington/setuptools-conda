import sys
from setuptools import setup
import sysconfig
from pathlib import Path

# Normally packages don't have to do this - the dist_conda command should be
# automatically available. But since we're installing it, it isn't there yet!
from setuptools_conda.setuptools_conda import dist_conda

SITE_PACKAGES = sysconfig.get_path('purelib')

# Add the dist_conda command to distutils vendored in setuptools:
setuptools_distutils = Path(SITE_PACKAGES) / 'setuptools' / '_distutils' / 'command'
DATA_FILES = [
    (str(setuptools_distutils.relative_to(sys.prefix)), ["dist_conda.py"]),
]
print(DATA_FILES)
setup(cmdclass={'dist_conda': dist_conda}, data_files=DATA_FILES)
