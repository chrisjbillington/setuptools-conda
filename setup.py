from setuptools import setup

from setuptools_conda import dist_conda

setup(
    use_scm_version=True,
    cmdclass={'dist_conda': dist_conda},
)
