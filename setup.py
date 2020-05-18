from setuptools import setup
import os
from setuptools_conda import dist_conda

CMDCLASS = {'dist_conda': dist_conda}

VERSION_SCHEME = {
    "version_scheme": os.getenv("SCM_VERSION_SCHEME", "guess-next-dev"),
    "local_scheme": os.getenv("SCM_LOCAL_SCHEME", "node-and-date"),
}

setup(
    use_scm_version=VERSION_SCHEME,
    cmdclass=CMDCLASS,
)
