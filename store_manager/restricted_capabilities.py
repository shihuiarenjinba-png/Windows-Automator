from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any
import zipfile
from xml.etree import ElementTree

AUTO_JUSTIFICATION_CAPABILITIES = ("runFullTrust",)
RUNFULLTRUST_PACKAGE_WARNING = (
    "Package acceptance validation warning: The following restricted capabilities "
    "require approval before you can use them in your app: runFullTrust."
)


@dataclass
class RestrictedCapabilityJustification:
    """Owner-reviewed Store explanation bound to one exact package."""

    text: str = ""
    source: str = "owner_required"
    confirmed: bool = False
    package_sha256: str = ""

    @classmethod
    def from_value(cls, value: Any) -> "RestrictedCapabilityJustification":
        if isinstance(value, cls):
            return cls(value.text, value.source, value.confirmed, value.package_sha256)
        if isinstance(value, str):
            # Legacy queue files contained only text. Never infer confirmation.
            return cls(text=value, source="legacy_text", confirmed=False)
        if isinstance(value, dict):
            return cls(
                text=str(value.get("text") or ""),
                source=str(value.get("source") or "owner_required"),
                confirmed=bool(value.get("confirmed", False)),
                package_sha256=str(value.get("package_sha256") or ""),
            )
        return cls()


def normalize_explanation_text(text: str) -> str:
    """Normalize only line endings and surrounding whitespace."""

    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def classify_package_warning(text: str) -> tuple[str, tuple[str, ...]]:
    """Classify only the exact observed restricted-capability warning."""

    messages = [message.strip() for message in text.split(" | ") if message.strip()]
    if messages and set(messages) == {RUNFULLTRUST_PACKAGE_WARNING}:
        return "RESTRICTED_CAPABILITY_REVIEW_REQUIRED", ("runFullTrust",)
    return "PACKAGE_VALIDATION_WARNING", ()


def _manifest_bytes_from_archive(raw: bytes | Path, depth: int = 0) -> list[bytes]:
    if depth > 3:
        return []
    try:
        archive = zipfile.ZipFile(raw)
    except (zipfile.BadZipFile, OSError):
        return []
    with archive:
        names = archive.namelist()
        manifests = [
            name for name in names
            if name.replace("\\", "/").casefold().endswith("appxmanifest.xml")
        ]
        if manifests:
            return [archive.read(name) for name in manifests]
        nested = [
            name for name in names
            if Path(name).suffix.casefold() in {".msix", ".appx", ".msixbundle", ".appxbundle"}
        ]
        out: list[bytes] = []
        for name in nested:
            out.extend(_manifest_bytes_from_archive(BytesIO(archive.read(name)), depth + 1))
        return out


def restricted_capabilities_from_package(path: str | Path) -> tuple[str, ...]:
    found: set[str] = set()
    for raw in _manifest_bytes_from_archive(Path(path)):
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError:
            continue
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] != "Capability":
                continue
            namespace = node.tag.split("}", 1)[0].lstrip("{") if "}" in node.tag else ""
            name = str(node.attrib.get("Name") or "").strip()
            if name and ("restrictedcapabilities" in namespace.casefold() or name == "runFullTrust"):
                found.add(name)
    return tuple(sorted(found))


def build_restricted_capability_justification(
    capability: str,
    product_type: str,
    product_name: str = "",
) -> str | None:
    """Build the approved fixed template; unknown capabilities never use AI prose."""

    if capability != "runFullTrust":
        return None
    noun = "game" if product_type == "game" else "application"
    subject = product_name.strip() or "This product"
    return (
        f"{subject} is a packaged Windows desktop {noun} that runs as a normal Win32 desktop process. "
        f"The runFullTrust capability is required so the packaged {noun} can launch and operate its "
        "desktop process at medium integrity outside the AppContainer sandbox, including its local "
        "runtime and save-data functionality. It is not used to request administrator elevation or "
        "bypass Windows security controls."
    )


def package_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exact_capability_match(manifest_capabilities: tuple[str, ...], partner_capabilities: tuple[str, ...]) -> bool:
    """Require the exact set and exactly one Partner Center field per capability."""

    return len(partner_capabilities) == len(set(partner_capabilities)) and set(manifest_capabilities) == set(partner_capabilities)


def sync_package_justifications(
    path: str | Path,
    product_type: str,
    product_name: str,
    existing: dict[str, Any] | None = None,
) -> tuple[dict[str, RestrictedCapabilityJustification], tuple[str, ...]]:
    """Reconcile capability records with the current package and invalidate stale confirmation."""

    detected = restricted_capabilities_from_package(path)
    current_sha = package_sha256(path)
    old = {key: RestrictedCapabilityJustification.from_value(value) for key, value in (existing or {}).items()}
    records: dict[str, RestrictedCapabilityJustification] = {}
    unresolved: list[str] = []
    for capability in detected:
        prior = old.get(capability)
        template = build_restricted_capability_justification(capability, product_type, product_name)
        if template is None:
            if (
                prior
                and prior.package_sha256.casefold() == current_sha.casefold()
                and prior.text.strip()
                and prior.source in {"manual_ui", "owner_input"}
                and prior.confirmed
            ):
                records[capability] = prior
            else:
                records[capability] = RestrictedCapabilityJustification(
                    text=prior.text if prior else "",
                    source=prior.source if prior and prior.text else "owner_required",
                    confirmed=False,
                    package_sha256=current_sha,
                )
                unresolved.append(capability)
            continue
        if prior and prior.package_sha256.casefold() == current_sha.casefold():
            records[capability] = prior
        elif prior and prior.text and prior.source in {"manual_ui", "owner_input"}:
            records[capability] = RestrictedCapabilityJustification(
                text=prior.text,
                source=prior.source,
                confirmed=False,
                package_sha256=current_sha,
            )
        else:
            records[capability] = RestrictedCapabilityJustification(
                text=template,
                source="fixed_template",
                confirmed=False,
                package_sha256=current_sha,
            )
    return records, tuple(unresolved)


def build_package_justifications(
    path: str | Path,
    product_type: str,
    product_name: str = "",
) -> tuple[dict[str, RestrictedCapabilityJustification], tuple[str, ...]]:
    return sync_package_justifications(path, product_type, product_name)
