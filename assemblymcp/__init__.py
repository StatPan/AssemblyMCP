"""AssemblyMCP - MCP Server for Korean National Assembly Open API"""

import warnings
from importlib.metadata import PackageNotFoundError, version


def _load_package_version() -> str:
    try:
        # Local dev environments can retain stale dist-info after editable reinstalls.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return version("assemblymcp")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _load_package_version()
