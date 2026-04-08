"""Compatibility-friendly SDK for ESE application bundles."""

from __future__ import annotations

from ese.starter_sdk import (
    APPLICATION_BUNDLE_MANIFEST_NAME,
)
from ese.starter_sdk import (
    STARTER_MANIFEST_NAME as LEGACY_STARTER_MANIFEST_NAME,
)
from ese.starter_sdk import (
    StarterProject as BundleProject,
)
from ese.starter_sdk import (
    StarterProjectError as BundleProjectError,
)
from ese.starter_sdk import (
    describe_starter_project as describe_bundle_project,
)
from ese.starter_sdk import (
    load_starter_project as load_bundle_project,
)
from ese.starter_sdk import (
    resolve_starter_manifest as resolve_bundle_manifest,
)
from ese.starter_sdk import (
    scaffold_starter_project as scaffold_bundle_project,
)
from ese.starter_sdk import (
    smoke_test_starter_project as smoke_test_bundle_project,
)

__all__ = [
    "APPLICATION_BUNDLE_MANIFEST_NAME",
    "LEGACY_STARTER_MANIFEST_NAME",
    "BundleProject",
    "BundleProjectError",
    "describe_bundle_project",
    "load_bundle_project",
    "resolve_bundle_manifest",
    "scaffold_bundle_project",
    "smoke_test_bundle_project",
]
