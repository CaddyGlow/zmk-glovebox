#!/usr/bin/env python3
"""Demo script to show layer reference handling in action."""

from glovebox.layout.models import LayoutData
from glovebox.layout.utils.layer_references import (
    create_layer_mapping_for_remove,
    find_layer_references,
    update_layer_references,
)


def main():
    """Demonstrate layer reference tracking and updating."""
    # Create a simple layout with layer references
    layout_dict = {
        "keyboard": "test",
        "title": "Layer Reference Demo",
        "layer_names": ["Base", "Nav", "Num", "Sym"],
        "layers": [
            # Base layer
            ["&kp Q", "&mo 1", "&lt 2 SPACE", "&tog 3"],
            # Nav layer
            ["&to 0", "&trans", "&trans", "&trans"],
            # Num layer
            ["&trans", "&mo 3", "&trans", "&trans"],
            # Sym layer
            ["&to 0", "&mo 1", "&trans", "&trans"],
        ],
    }

    # Load the layout
    layout = LayoutData.model_validate(layout_dict)

    print("=== Original Layout ===")
    print(f"Layers: {layout.layer_names}")

    # Find all layer references
    refs = find_layer_references(layout)
    print("\n=== Layer References Found ===")
    for ref in refs:
        layer_name = layout.layer_names[ref.layer_index]
        print(f"- {layer_name}[{ref.binding_index}]: {ref.behavior} {ref.layer_id}")

    # Simulate removing Nav layer (index 1)
    print("\n=== Removing Nav Layer (index 1) ===")

    # Create mapping for the removal
    mapping = create_layer_mapping_for_remove(4, [1])
    print(f"Layer mapping: {mapping}")

    # Update references
    updated_layout, warnings = update_layer_references(layout, mapping)

    print("\n=== Warnings ===")
    for warning in warnings:
        print(f"- {warning}")

    # Show updated references
    print("\n=== Updated Layer References ===")
    refs = find_layer_references(updated_layout)
    for ref in refs:
        # Note: layer names haven't been updated in this demo
        print(
            f"- Layer {ref.layer_index}[{ref.binding_index}]: {ref.behavior} {ref.layer_id}"
        )

    print("\n=== Summary ===")
    print("- References to removed layer 1 generated warnings")
    print("- &lt 2 SPACE was updated to &lt 1 SPACE")
    print("- &tog 3 was updated to &tog 2")
    print("- &mo 3 was updated to &mo 2")
    print(
        "\nThis ensures keyboard functionality remains intact after layer operations!"
    )


if __name__ == "__main__":
    main()
