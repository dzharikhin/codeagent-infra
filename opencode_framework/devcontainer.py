"""Devcontainer detection and evaluation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json


STANDARD_DEVCONTAINER_PATHS = [
    ".devcontainer/devcontainer.json",
    ".devcontainer.json",
    ".devcontainer/devcontainer.yaml",
    ".devcontainer/devcontainer.yml",
]


@dataclass
class DevcontainerInfo:
    """Information about an existing devcontainer."""
    
    path: str
    format: str  # "json" or "yaml"
    compatible: bool
    incompatibility_reason: Optional[str] = None
    content: Optional[dict] = None


def detect_devcontainer(repo_root: Path) -> Optional[DevcontainerInfo]:
    """Detect standard devcontainer files.
    
    Only checks standard locations:
    - .devcontainer/devcontainer.json
    - .devcontainer.json
    - .devcontainer/devcontainer.yaml
    - .devcontainer/devcontainer.yml
    """
    for rel_path in STANDARD_DEVCONTAINER_PATHS:
        dc_path = repo_root / rel_path
        if not dc_path.is_file():
            continue
        
        file_format = "yaml" if rel_path.endswith((".yaml", ".yml")) else "json"
        
        content = None
        compatible = True
        incompatibility_reason = None
        
        if file_format == "json":
            try:
                content = json.loads(dc_path.read_text())
                compatible, incompatibility_reason = evaluate_compatibility(content)
            except json.JSONDecodeError as e:
                compatible = False
                incompatibility_reason = f"Invalid JSON: {e}"
        
        return DevcontainerInfo(
            path=str(dc_path),
            format=file_format,
            compatible=compatible,
            incompatibility_reason=incompatibility_reason,
            content=content,
        )
    
    return None


def evaluate_compatibility(devcontainer_content: dict) -> tuple[bool, Optional[str]]:
    """Evaluate if a devcontainer is compatible with the framework.
    
    Basic compatibility rules:
    - Must have a valid image or build context
    - Should not have conflicting postCreateCommand
    """
    if "image" not in devcontainer_content and "build" not in devcontainer_content:
        return False, "No 'image' or 'build' specified"
    
    return True, None
