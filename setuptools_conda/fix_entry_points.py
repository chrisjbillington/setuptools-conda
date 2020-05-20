import sys
import sysconfig
try:
    import importlib.metadata as importlib_metadata
except ImportError:
    import importlib_metadata
from distlib.scripts import ScriptMaker


def fix_entry_points(distribution_names):
    """Re-make all entry_points for the given distributions. This is intended to be
    called as a post-link script for a conda package. This is a workaround for the fact
    that conda doesn't support GUI scripts."""

    # There are many places scripts can go, but we're in conda so the main scripts dir
    # at sysconfig.get_path('scripts') is the only possibility for us:
    maker = ScriptMaker(None, sysconfig.get_path('scripts'))
    maker.clobber = True  # Overwrite existing scripts
    maker.variants = {''}  # Don't make variants with Python major.minor suffixes

    for name in distribution_names:
        # Get the script specs and format them how Scriptmaker wants them
        distribution = importlib_metadata.Distribution.from_name(name)

        # There seems to be a bug where if you have a post-link script, conda doesn't
        # even create the console scripts correctly either. So we'll remake them too,
        # why not.
        console_scripts = [
            f'{e.name} = {e.value}'
            for e in distribution.entry_points
            if e.group == 'console_scripts'
        ]
        gui_scripts = [
            f'{e.name} = {e.value}'
            for e in distribution.entry_points
            if e.group == 'gui_scripts'
        ]

        # Make 'em:
        maker.make_multiple(console_scripts)
        maker.make_multiple(gui_scripts, {'gui': True})


if __name__ == '__main__':
    # TODO: argparse?
    fix_entry_points(sys.argv[1:])