from setuptools import setup
import os

from setuptools_conda import conda_dist, __version__

PYTHON_REQUIRES = ">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*"
SETUP_REQUIRES = ['setuptools', 'setuptools_scm']
INSTALL_REQUIRES = ["setuptools"]

setup(
    name='setuptools_conda',
    version=__version__,
    description="Add a conda_dist command to setuptools",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='http://github.com/chrisjbillington/setuptools_conda',
    license="BSD",
    packages=['setuptools_conda'],
    zip_safe=False,
    setup_requires=SETUP_REQUIRES,
    install_requires=[] if 'CONDA_BUILD' in os.environ else INSTALL_REQUIRES,
    include_package_data=True,
    python_requires=PYTHON_REQUIRES,
    cmdclass={'conda_dist': conda_dist},
    command_options={
        'conda_dist': {
            'pythons': (__file__, ['2.7', '3.5', '3.6', '3.7', '3.8']),
            'platforms': (__file__, 'all'),
        },
    },
)
