from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile
from xml.etree import ElementTree

AUTO_JUSTIFICATION_CAPABILITIES = ("runFullTrust",)

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
            # Restricted capabilities normally use the rescap namespace.
            if name and ("restrictedcapabilities" in namespace.casefold() or name == "runFullTrust"):
                found.add(name)
    return tuple(sorted(found))

def build_restricted_capability_justification(capability: str, product_type: str) -> str | None:
    if capability != "runFullTrust":
        return None
    noun = "game" if product_type == "game" else "application"
    return (
        f"This product is a packaged Windows desktop {noun}. "
        "The runFullTrust capability is required because the package launches its normal "
        "desktop process at the standard desktop (medium integrity) trust level rather than "
        "as an AppContainer application. The capability is used only to run the packaged "
        f"desktop {noun} and provide its normal local desktop functionality. "
        "It is not used to request administrator elevation."
    )

def build_package_justifications(path: str | Path, product_type: str) -> tuple[dict[str, str], tuple[str, ...]]:
    explanations: dict[str, str] = {}
    unresolved: list[str] = []
    for capability in restricted_capabilities_from_package(path):
        text = build_restricted_capability_justification(capability, product_type)
        if text:
            explanations[capability] = text
        else:
            unresolved.append(capability)
    return explanations, tuple(unresolved)
