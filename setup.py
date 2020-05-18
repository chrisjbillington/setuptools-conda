from setuptools import setup

from setuptools_conda import dist_conda

SETUP_REQUIRES = INSTALL_REQUIRES = [
    "setuptools",
    "setuptools_scm",
    "importlib_metadata;    python_version < '3.8'",
    "conda-build",
    "conda-verify",
]

setup(
    name='setuptools_conda',
    use_scm_version=True,
    description="Add a dist_conda command to your setup.py",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Chris Billington',
    author_email='chrisjbillington@gmail.com',
    url='http://github.com/chrisjbillington/setuptools_conda',
    license="BSD",
    packages=['setuptools_conda'],
    setup_requires=SETUP_REQUIRES,
    install_requires=INSTALL_REQUIRES,
    include_package_data=True,
    python_requires=">=3.6",
    cmdclass={'dist_conda': dist_conda},
    command_options={'dist_conda': {'pythons': (__file__, '3.6, 3.7')}},
)
