from typing import Any

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from glovebox.layout.models import (
    ComboBehavior,
    HoldTapBehavior,
    InputListener,
    LayoutBinding,
    MacroBehavior,
)


class LayerModel(BaseModel):
    layer_names: list[str]
    layers: list[list[str]]

    @field_validator("layers")
    @classmethod
    def validate_layers_count_matches_names(
        cls, v: list[list[str]], info: ValidationInfo
    ) -> list[list[str]]:
        if "layer_names" in info.data:
            layer_names = info.data["layer_names"]
            if len(v) != len(layer_names):
                raise ValueError(
                    f"Number of layers ({len(v)}) must match number of layer names ({len(layer_names)})"
                )
        return v


# Base dataset - original layout
BASE_LAYOUT = LayerModel(
    layer_names=["base", "lower", "raise", "adjust"],
    layers=[
        # base layer - QWERTY layout
        [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],
        # lower layer - numbers and symbols
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],
        # raise layer - function keys
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        # adjust layer - media and system keys
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 1: Single key change - Q to A (Dvorak-like change)
SINGLE_KEY_CHANGE = LayerModel(
    layer_names=["base", "lower", "raise", "adjust"],
    layers=[
        [
            "&kp A",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],  # Q -> A
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 2: Multiple key changes in same layer
MULTIPLE_KEY_CHANGES = LayerModel(
    layer_names=["base", "lower", "raise", "adjust"],
    layers=[
        [
            "&kp A",
            "&kp W",
            "&kp D",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],  # Q->A, E->D
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 3: Layer reordering - swap lower and raise
LAYER_REORDER = LayerModel(
    layer_names=["base", "raise", "lower", "adjust"],  # swapped order
    layers=[
        [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],  # raise moved up
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],  # lower moved down
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 4: Layer addition
LAYER_ADDITION = LayerModel(
    layer_names=["base", "lower", "raise", "nav", "adjust"],  # added nav layer
    layers=[
        [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        [
            "&kp LEFT",
            "&kp DOWN",
            "&kp UP",
            "&kp RIGHT",
            "&kp HOME",
            "&kp END",
            "&kp PG_DN",
            "&kp PG_UP",
            "&trans",
            "&trans",
        ],  # new nav layer
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 5: Layer removal
LAYER_REMOVAL = LayerModel(
    layer_names=["base", "lower", "raise"],  # removed adjust layer
    layers=[
        [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
    ],
)

# Test Case 6: Entire layer content change
LAYER_CONTENT_CHANGE = LayerModel(
    layer_names=["base", "lower", "raise", "adjust"],
    layers=[
        [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],
        # Completely different lower layer - symbols instead of numbers
        [
            "&kp EXCL",
            "&kp AT",
            "&kp HASH",
            "&kp DLLR",
            "&kp PRCNT",
            "&kp CARET",
            "&kp AMPS",
            "&kp STAR",
            "&kp LPAR",
            "&kp RPAR",
        ],
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 7: Complex change - multiple operations
COMPLEX_CHANGE = LayerModel(
    layer_names=[
        "base",
        "symbols",
        "raise",
        "nav",
        "system",
    ],  # renamed lower->symbols, adjust->system, added nav
    layers=[
        [
            "&kp A",
            "&kp W",
            "&kp D",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],  # key changes in base
        [
            "&kp EXCL",
            "&kp AT",
            "&kp HASH",
            "&kp DLLR",
            "&kp PRCNT",
            "&kp CARET",
            "&kp AMPS",
            "&kp STAR",
            "&kp LPAR",
            "&kp RPAR",
        ],  # content change
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        [
            "&kp LEFT",
            "&kp DOWN",
            "&kp UP",
            "&kp RIGHT",
            "&kp HOME",
            "&kp END",
            "&kp PG_DN",
            "&kp PG_UP",
            "&trans",
            "&trans",
        ],  # new nav layer
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&bt BT_CLR",
            "&bt BT_NXT",
            "&bt BT_PRV",
            "&trans",
        ],  # system changes
    ],
)

# Test Case 8: Partial layer change - some positions changed, some untouched
PARTIAL_LAYER_CHANGE = LayerModel(
    layer_names=["base", "lower", "raise", "adjust"],
    layers=[
        [
            "&kp Q",
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],
        [
            "&kp N1",
            "&kp N2",
            "&kp HASH",
            "&kp DLLR",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp STAR",
            "&kp N9",
            "&kp N0",
        ],  # positions 2, 3, 7 changed
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],
    ],
)

# Test Case 9: Layer move + key change - move adjust layer to second position and change a key in base
LAYER_MOVE_WITH_KEY_CHANGE = LayerModel(
    layer_names=[
        "base",
        "adjust",
        "lower",
        "raise",
    ],  # moved adjust from last to second
    layers=[
        [
            "&kp A",  # Changed Q -> A
            "&kp W",
            "&kp E",
            "&kp R",
            "&kp T",
            "&kp Y",
            "&kp U",
            "&kp I",
            "&kp O",
            "&kp P",
        ],  # base layer with key change
        [
            "&kp C_PREV",
            "&kp C_PLAY",
            "&kp C_NEXT",
            "&kp C_VOL_DN",
            "&kp C_VOL_UP",
            "&kp C_MUTE",
            "&trans",
            "&trans",
            "&trans",
            "&trans",
        ],  # adjust layer moved to position 1
        [
            "&kp N1",
            "&kp N2",
            "&kp N3",
            "&kp N4",
            "&kp N5",
            "&kp N6",
            "&kp N7",
            "&kp N8",
            "&kp N9",
            "&kp N0",
        ],  # lower layer moved to position 2
        [
            "&kp F1",
            "&kp F2",
            "&kp F3",
            "&kp F4",
            "&kp F5",
            "&kp F6",
            "&kp F7",
            "&kp F8",
            "&kp F9",
            "&kp F10",
        ],  # raise layer moved to position 3
    ],
)


# Enhanced LayerModel with behaviors, macros, and combos
class EnhancedLayerModel(BaseModel):
    layer_names: list[str]
    layers: list[list[str]]
    hold_taps: list[HoldTapBehavior] = Field(default_factory=list)
    combos: list[ComboBehavior] = Field(default_factory=list)
    macros: list[MacroBehavior] = Field(default_factory=list)
    input_listeners: list[InputListener] = Field(default_factory=list)

    @field_validator("layers")
    @classmethod
    def validate_layers_count_matches_names(
        cls, v: list[list[str]], info: ValidationInfo
    ) -> list[list[str]]:
        if "layer_names" in info.data:
            layer_names = info.data["layer_names"]
            if len(v) != len(layer_names):
                raise ValueError(
                    f"Number of layers ({len(v)}) must match number of layer names ({len(layer_names)})"
                )
        return v


# Test Case 10: Base layout with behaviors, macros, and combos
BASE_WITH_BEHAVIORS = EnhancedLayerModel(
    layer_names=["base", "lower", "raise"],
    layers=[
        ["&kp Q", "&kp W", "&kp E", "&ht_a", "&combo_space"],
        ["&kp N1", "&kp N2", "&kp N3", "&macro_hello", "&kp N5"],
        ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],
    ],
    hold_taps=[
        HoldTapBehavior(
            name="ht_a",
            description="Hold-tap for A key",
            tappingTermMs=200,
            quickTapMs=125,
            flavor="tap-preferred",
            bindings=["&kp", "&kp"],
        )
    ],
    combos=[
        ComboBehavior(
            name="combo_space",
            description="Space combo",
            timeoutMs=50,
            keyPositions=[2, 3],
            binding=LayoutBinding(value="&kp", params=[]),
        )
    ],
    macros=[
        MacroBehavior(
            name="macro_hello",
            description="Types hello world",
            waitMs=40,
            tapMs=30,
            bindings=[
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),
            ],
        )
    ],
)

# Test Case 11: Modified behaviors - changed parameters and added new ones
MODIFIED_BEHAVIORS = EnhancedLayerModel(
    layer_names=["base", "lower", "raise"],
    layers=[
        ["&kp Q", "&kp W", "&kp E", "&ht_a", "&combo_space"],
        ["&kp N1", "&kp N2", "&kp N3", "&macro_hello", "&kp N5"],
        ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],
    ],
    hold_taps=[
        HoldTapBehavior(
            name="ht_a",
            description="Hold-tap for A key - modified",
            tappingTermMs=250,  # Changed from 200
            quickTapMs=150,  # Changed from 125
            flavor="balanced",  # Changed from tap_preferred
            bindings=["&kp", "&kp"],  # Changed LSHIFT to LCTRL
        ),
        HoldTapBehavior(
            name="ht_new",  # New hold-tap
            description="New hold-tap for B key",
            tappingTermMs=180,
            quickTapMs=100,
            flavor="tap-preferred",
            bindings=["&kp", "&kp"],
        ),
    ],
    combos=[
        ComboBehavior(
            name="combo_space",
            description="Space combo - modified",
            timeoutMs=75,  # Changed from 50
            keyPositions=[2, 3, 4],  # Added position 4
            binding=LayoutBinding(
                value="&kp", params=[]
            ),  # Changed from SPACE to ENTER
        ),
        ComboBehavior(
            name="combo_new",  # New combo
            description="New escape combo",
            timeoutMs=60,
            keyPositions=[0, 1],
            binding=LayoutBinding(value="&kp", params=[]),
        ),
    ],
    macros=[
        MacroBehavior(
            name="macro_hello",
            description="Types hello world - modified",
            waitMs=50,  # Changed from 40
            tapMs=35,  # Changed from 30
            bindings=[
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),  # Changed E to I
                LayoutBinding(value="&kp", params=[]),  # Added space
                LayoutBinding(value="&kp", params=[]),  # Changed L to T
                LayoutBinding(value="&kp", params=[]),  # Changed L to H
                LayoutBinding(value="&kp", params=[]),  # Changed O to E
                LayoutBinding(value="&kp", params=[]),  # Added R
                LayoutBinding(value="&kp", params=[]),  # Added E
            ],
        )
        # Note: macro_hello modified to type "HI THERE" instead of "HELLO"
    ],
)

# Test Case 12: Removed and added behaviors
BEHAVIOR_CHANGES = EnhancedLayerModel(
    layer_names=["base", "lower", "raise"],
    layers=[
        ["&kp Q", "&kp W", "&kp E", "&ht_new_only", "&combo_new_only"],
        ["&kp N1", "&kp N2", "&kp N3", "&macro_new_only", "&kp N5"],
        ["&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5"],
    ],
    hold_taps=[
        HoldTapBehavior(
            name="ht_new_only",  # Completely different hold-tap
            description="Replacement hold-tap",
            tappingTermMs=300,
            quickTapMs=200,
            flavor="hold-preferred",
            bindings=["&kp", "&kp"],
        )
    ],
    combos=[
        ComboBehavior(
            name="combo_new_only",  # Completely different combo
            description="Replacement combo",
            timeoutMs=100,
            keyPositions=[1, 2],
            binding=LayoutBinding(value="&kp", params=[]),
        )
    ],
    macros=[
        MacroBehavior(
            name="macro_new_only",  # Completely different macro
            description="Replacement macro",
            waitMs=20,
            tapMs=15,
            bindings=[
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),
                LayoutBinding(value="&kp", params=[]),
            ],
        )
    ],
)

# Dictionary of all test cases for easy access
TEST_CASES = {
    "base": BASE_LAYOUT,
    "single_key_change": SINGLE_KEY_CHANGE,
    "multiple_key_changes": MULTIPLE_KEY_CHANGES,
    "layer_reorder": LAYER_REORDER,
    "layer_addition": LAYER_ADDITION,
    "layer_removal": LAYER_REMOVAL,
    "layer_content_change": LAYER_CONTENT_CHANGE,
    "complex_change": COMPLEX_CHANGE,
    "partial_layer_change": PARTIAL_LAYER_CHANGE,
    "layer_move_with_key_change": LAYER_MOVE_WITH_KEY_CHANGE,
}

# Enhanced test cases with behaviors
BEHAVIOR_TEST_CASES = {
    "base_with_behaviors": BASE_WITH_BEHAVIORS,
    "modified_behaviors": MODIFIED_BEHAVIORS,
    "behavior_changes": BEHAVIOR_CHANGES,
}

# Test scenarios for diffing and patching
TEST_SCENARIOS = [
    {
        "name": "Single Key Change",
        "description": "Change one key binding in base layer",
        "from": "base",
        "to": "single_key_change",
        "expected_changes": ["layers[0][0]: '&kp Q' -> '&kp A'"],
    },
    {
        "name": "Multiple Key Changes",
        "description": "Change multiple keys in same layer",
        "from": "base",
        "to": "multiple_key_changes",
        "expected_changes": [
            "layers[0][0]: '&kp Q' -> '&kp A'",
            "layers[0][2]: '&kp E' -> '&kp D'",
        ],
    },
    {
        "name": "Layer Reordering",
        "description": "Swap positions of two layers",
        "from": "base",
        "to": "layer_reorder",
        "expected_changes": [
            "layer_names[1]: 'lower' -> 'raise'",
            "layer_names[2]: 'raise' -> 'lower'",
        ],
    },
    {
        "name": "Layer Addition",
        "description": "Add a new navigation layer",
        "from": "base",
        "to": "layer_addition",
        "expected_changes": ["Added layer 'nav' at position 3"],
    },
    {
        "name": "Layer Removal",
        "description": "Remove the adjust layer",
        "from": "base",
        "to": "layer_removal",
        "expected_changes": ["Removed layer 'adjust'"],
    },
    {
        "name": "Complete Layer Content Change",
        "description": "Replace entire layer content",
        "from": "base",
        "to": "layer_content_change",
        "expected_changes": ["layers[1]: Complete replacement"],
    },
    {
        "name": "Complex Multi-Operation Change",
        "description": "Multiple types of changes in one operation",
        "from": "base",
        "to": "complex_change",
        "expected_changes": [
            "Multiple layer renames",
            "Key changes",
            "Layer addition",
            "Content changes",
        ],
    },
    {
        "name": "Partial Layer Modification",
        "description": "Change some positions in a layer, leave others unchanged",
        "from": "base",
        "to": "partial_layer_change",
        "expected_changes": ["layers[1][2,3,7]: Selective position changes"],
    },
    {
        "name": "Layer Move with Key Change",
        "description": "Move a layer to different position AND change a key in another layer",
        "from": "base",
        "to": "layer_move_with_key_change",
        "expected_changes": [
            "layers[0][0]: '&kp Q' -> '&kp A'",
            "layer_names[1]: 'lower' -> 'adjust'",
            "layer_names[2]: 'raise' -> 'lower'",
            "layer_names[3]: 'adjust' -> 'raise'",
            "Layer content moved due to reordering",
        ],
    },
]

# Test scenarios for behavior-based diffing
BEHAVIOR_SCENARIOS = [
    {
        "name": "Modified Behavior Parameters",
        "description": "Change parameters of existing behaviors and add new ones",
        "from": "base_with_behaviors",
        "to": "modified_behaviors",
        "expected_changes": [
            "hold_taps['ht_a']: Parameter changes (tapping_term_ms, flavor, bindings)",
            "hold_taps: Added 'ht_new'",
            "combos['combo_space']: Parameter changes (timeout_ms, key_positions, binding)",
            "combos: Added 'combo_new'",
            "macros['macro_hello']: Parameter and binding changes",
        ],
    },
    {
        "name": "Behavior Replacement",
        "description": "Remove all existing behaviors and replace with new ones",
        "from": "base_with_behaviors",
        "to": "behavior_changes",
        "expected_changes": [
            "hold_taps: Removed 'ht_a', Added 'ht_new_only'",
            "combos: Removed 'combo_space', Added 'combo_new_only'",
            "macros: Removed 'macro_hello', Added 'macro_new_only'",
            "Layer bindings reference new behavior names",
        ],
    },
]


if __name__ == "__main__":
    # Print all test cases as JSON for inspection
    import json

    print("=== TEST CASES ===\n")
    for name, layout in TEST_CASES.items():
        print(f"--- {name.upper()} ---")
        print(
            json.dumps(
                layout.model_dump(by_alias=True, exclude_unset=True, mode="json"),
                indent=2,
            )
        )
        print()

    print("\n=== TEST SCENARIOS ===\n")
    for scenario in TEST_SCENARIOS:
        print(f"Scenario: {scenario['name']}")
        print(f"Description: {scenario['description']}")
        print(f"From: {scenario['from']} -> To: {scenario['to']}")
        print(f"Expected: {scenario['expected_changes']}")
        print()
