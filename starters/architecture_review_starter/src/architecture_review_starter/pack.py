"""Entry point for the architecture-review starter pack."""

from pathlib import Path

from ese.pack_sdk import load_pack_definition_from_manifest


def load_pack():
    """Return the config pack exported by this starter repository."""
    return load_pack_definition_from_manifest(Path(__file__).with_name("ese_pack.yaml"))
