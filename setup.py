from setuptools import setup
import os

from setuptools_conda import bdist_conda

VERSION = '0.2.0'

# Auto generate a __version__ package for the package to import
with open(os.path.join('setuptools_conda', '__version__.py'), 'w') as f:
    f.write("__version__ = '%s'\n" % VERSION)

PYTHON_REQUIRES = ">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*"
SETUP_REQUIRES = ['setuptools', 'setuptools_scm']
INSTALL_REQUIRES = ["setuptools"]

setup(
    name='setuptools_conda',
    version=VERSION,
    description="Add a bdist_conda command to your setup.py",
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
    cmdclass={'bdist_conda': bdist_conda},
    command_options={
        'conda_dist': {
            'pythons': (__file__, ['2.7', '3.5', '3.6', '3.7', '3.8']),
            'platforms': (__file__, 'all'),
            'install_requires': (
                __file__,
                INSTALL_REQUIRES + ['conda-build', 'conda-verify'],
            ),
        },
    },
)
