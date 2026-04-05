"""
HIVE215 Test Configuration

Sets up import paths for the governance overlay modules.
Directories starting with numbers are not valid Python package names,
so we create importable aliases.
"""

import importlib
import importlib.util
import os
import sys
from pathlib import Path

# Root of the project
PROJECT_ROOT = Path(__file__).parent.parent

# Add project root to path
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_package_from_path(package_name: str, dir_path: Path) -> None:
    """Load a directory as a Python package under the given name."""
    if package_name in sys.modules:
        return
    init_path = dir_path / "__init__.py"
    if not init_path.exists():
        # Create a virtual package
        import types
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(dir_path)]
        pkg.__package__ = package_name
        sys.modules[package_name] = pkg
    else:
        spec = importlib.util.spec_from_file_location(
            package_name, str(init_path),
            submodule_search_locations=[str(dir_path)]
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            mod.__path__ = [str(dir_path)]
            sys.modules[package_name] = mod
            spec.loader.exec_module(mod)


def _load_subpackage(parent_name: str, sub_name: str, dir_path: Path) -> None:
    """Load a subdirectory as a subpackage."""
    full_name = f"{parent_name}.{sub_name}"
    if full_name in sys.modules:
        return
    import types
    pkg = types.ModuleType(full_name)
    pkg.__path__ = [str(dir_path)]
    pkg.__package__ = full_name
    sys.modules[full_name] = pkg


# Map numbered directories to importable names
_PACKAGE_MAP = {
    "two_domain_kernels": PROJECT_ROOT / "2_domain_kernels",
    "three_constraint_ports": PROJECT_ROOT / "3_constraint_ports",
}

_SUBPACKAGE_MAP = {
    "three_constraint_ports": {
        "voice_ports": PROJECT_ROOT / "3_constraint_ports" / "voice_ports",
        "supabase_ports": PROJECT_ROOT / "3_constraint_ports" / "supabase_ports",
        "ui_ports": PROJECT_ROOT / "3_constraint_ports" / "ui_ports",
        "upload_ports": PROJECT_ROOT / "3_constraint_ports" / "upload_ports",
        "external_api_ports": PROJECT_ROOT / "3_constraint_ports" / "external_api_ports",
        "llm_ports": PROJECT_ROOT / "3_constraint_ports" / "llm_ports",
        "inbound_ports": PROJECT_ROOT / "3_constraint_ports" / "inbound_ports",
        "outbound_ports": PROJECT_ROOT / "3_constraint_ports" / "outbound_ports",
    },
}

# Load all packages
for pkg_name, pkg_path in _PACKAGE_MAP.items():
    _load_package_from_path(pkg_name, pkg_path)

for parent_name, subs in _SUBPACKAGE_MAP.items():
    for sub_name, sub_path in subs.items():
        _load_subpackage(parent_name, sub_name, sub_path)
