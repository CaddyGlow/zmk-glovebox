import json
from datetime import datetime
from pathlib import Path
from typing import Any

from glovebox.layout.diffing.diff import LayoutDiffSystem
from glovebox.layout.diffing.patch import LayoutPatchSystem
from glovebox.layout.models import LayoutData


class LayoutDiffManager:
    """High-level manager for layout diffs and patches."""

    def __init__(self, base_layout_path: Path):
        self.base_layout_path = base_layout_path
        self.diff_system = LayoutDiffSystem()
        self.patch_system = LayoutPatchSystem()
        self.diff_history: list[dict[str, Any]] = []

    def load_layout(self, path: Path) -> LayoutData:
        """Load a layout from JSON file."""
        with path.open() as f:
            data = json.load(f)
        return LayoutData.model_validate(data)

    def create_diff_from_file(self, modified_layout_path: Path) -> dict[str, Any]:
        """Create diff between base layout and a modified layout file."""
        base = self.load_layout(self.base_layout_path)
        modified = self.load_layout(modified_layout_path)

        diff = self.diff_system.create_layout_diff(base, modified)

        # Store in history
        self.diff_history.append(
            {
                "timestamp": datetime.now(),
                "source": str(modified_layout_path),
                "diff": diff,
            }
        )

        return diff

    def save_diff(self, diff: dict[str, Any], output_path: Path) -> None:
        """Save diff to a JSON file."""
        with output_path.open("w") as f:
            json.dump(diff, f, indent=2)

    def apply_diff_from_file(self, diff_path: Path) -> LayoutData:
        """Apply a diff file to the base layout."""
        with diff_path.open() as f:
            diff = json.load(f)

        base = self.load_layout(self.base_layout_path)
        return self.patch_system.apply_patch(base, diff)

    def merge_multiple_diffs(self, diff_paths: list[Path]) -> LayoutData:
        """Apply multiple diffs in sequence."""
        current_layout = self.load_layout(self.base_layout_path)

        for diff_path in diff_paths:
            with diff_path.open() as f:
                diff = json.load(f)
            current_layout = self.patch_system.apply_patch(current_layout, diff)

        return current_layout

    def analyze_binding_changes(self, diff: dict[str, Any]) -> dict[str, Any]:
        """Analyze what specific bindings changed."""
        analysis: dict[str, Any] = {
            "total_binding_changes": 0,
            "changes_by_layer": {},
            "behavior_frequency": {},
        }

        movements = diff.get("movements", {})

        # Count behavior changes
        for change in movements.get("behavior_changes", []):
            analysis["total_binding_changes"] += 1

            layer = change["layer"]
            if layer not in analysis["changes_by_layer"]:
                analysis["changes_by_layer"][layer] = 0
            analysis["changes_by_layer"][layer] += 1

            # Track which behaviors are most commonly changed
            old_behavior = change["from"].get("value", "")
            new_behavior = change["to"].get("value", "")

            for behavior in [old_behavior, new_behavior]:
                if behavior:
                    if behavior not in analysis["behavior_frequency"]:
                        analysis["behavior_frequency"][behavior] = 0
                    analysis["behavior_frequency"][behavior] += 1

        return analysis


# Usage example
if __name__ == "__main__":
    # Initialize manager with base layout
    manager = LayoutDiffManager(Path("layouts/base_layout.json"))

    # Create diff from modified layout
    diff = manager.create_diff_from_file(Path("layouts/my_modified_layout.json"))

    # Save diff for version control
    manager.save_diff(diff, Path("diffs/my_changes.diff.json"))

    # Apply diff to create new layout
    patched_layout = manager.apply_diff_from_file(Path("diffs/my_changes.diff.json"))

    # Save the patched layout
    output_path = Path("layouts/patched_layout.json")
    with output_path.open("w") as f:
        json.dump(patched_layout.to_dict(), f, indent=2)

    # Analyze what changed
    analysis = manager.analyze_binding_changes(diff)
    print(f"Total binding changes: {analysis['total_binding_changes']}")
    print(f"Changes by layer: {analysis['changes_by_layer']}")
