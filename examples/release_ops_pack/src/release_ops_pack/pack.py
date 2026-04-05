"""Entry point for the example external ESE config pack."""

from pathlib import Path

from ese.pack_sdk import load_pack_definition_from_manifest


def load_pack():
    """Return the ConfigPackDefinition exported by this package."""
    return load_pack_definition_from_manifest(Path(__file__).with_name("ese_pack.yaml"))
