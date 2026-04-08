"""Entry point for the installed architecture-review application bundle."""

from pathlib import Path

from ese.application_bundles import load_application_bundle_from_manifest


def load_application_bundle():
    """Return the installed application bundle exported by this package."""
    return load_application_bundle_from_manifest(Path(__file__).with_name("ese_application.yaml"))
