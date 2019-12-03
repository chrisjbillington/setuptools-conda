from setuptools import setup
import os
from runpy import run_path

from setuptools_conda import dist_conda

INSTALL_REQUIRES = ["setuptools"]

setup(
    name='setuptools_conda',
    version=run_path(os.path.join('setuptools_conda', '__version__.py'))['__version__'],
    description="Add a dist_conda command to your setup.py",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='http://github.com/chrisjbillington/setuptools_conda',
    license="BSD",
    packages=['setuptools_conda'],
    zip_safe=False,
    setup_requires=['setuptools', 'setuptools_scm'],
    install_requires=[] if 'CONDA_BUILD' in os.environ else INSTALL_REQUIRES,
    include_package_data=True,
    python_requires=">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*",
    cmdclass={'dist_conda': dist_conda},
    command_options={
        'dist_conda': {
            'pythons': (__file__, ['3.6', '3.7', '3.8']),
            'platforms': (__file__, ['linux-64', 'win-32', 'win-64', 'osx-64']),
            'install_requires': (
                __file__,
                INSTALL_REQUIRES + ['conda-build', 'conda-verify'],
            ),
        },
    },
)
