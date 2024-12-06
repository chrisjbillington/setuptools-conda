from pathlib import Path
import importlib.metadata

root = Path(__file__).parent.parent
if (root / '.git').is_dir():
    from setuptools_scm import get_version
    __version__ = get_version(
        root, version_scheme="release-branch-semver", local_scheme="no-local-version"
    )
else:
    try:
        __version__ = importlib.metadata.version(__package__)
    except importlib.metadata.PackageNotFoundError:
        __version__ = None
