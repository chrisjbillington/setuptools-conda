import os
from setuptools_scm import get_version
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata

VERSION_SCHEME = {
    "version_scheme": os.getenv("SCM_VERSION_SCHEME", "guess-next-dev"),
    "local_scheme": os.getenv("SCM_LOCAL_SCHEME", "node-and-date"),
}

try:
    __version__ = importlib_metadata.version(__package__)
except importlib_metadata.PackageNotFoundError:
    __version__ = None


__version__ = get_version(
    '..', relative_to=__file__, fallback_version=__version__, **VERSION_SCHEME
)
        
