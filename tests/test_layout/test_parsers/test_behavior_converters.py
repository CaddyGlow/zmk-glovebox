"""Tests for AST behavior converters."""

from glovebox.layout.parsers.ast_behavior_converter import (
    create_ast_behavior_converter,
)
from glovebox.layout.parsers.ast_nodes import DTNode, DTProperty, DTValue, DTValueType


class TestTapDanceBehaviorConverter:
    """Tests for tap dance behavior converter."""

    def test_convert_tap_dance_basic(self):
        """Test basic tap dance conversion."""
        # Create a tap dance node
        node = DTNode("&td0")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-tap-dance",
                raw="zmk,behavior-tap-dance",
            ),
        )
        node.properties["label"] = DTProperty(
            "label",
            DTValue(DTValueType.STRING, "TD0", raw="TD0"),
        )
        node.properties["#binding-cells"] = DTProperty(
            "#binding-cells",
            DTValue(DTValueType.INTEGER, 0, raw="0"),
        )
        node.properties["tapping-term-ms"] = DTProperty(
            "tapping-term-ms",
            DTValue(DTValueType.INTEGER, 200, raw="<200>"),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(
                DTValueType.ARRAY,
                ["&kp N1", "&kp N2", "&kp N3"],
                raw="<&kp N1>, <&kp N2>, <&kp N3>",
            ),
        )

        converter = create_ast_behavior_converter()
        tap_dance = converter.convert_tap_dance_node(node)

        if tap_dance is None:
            # Debug output
            print("Node name:", node.name)
            print("Node properties:", list(node.properties.keys()))
            for name, prop in node.properties.items():
                print(f"  {name}: {prop.value.value if prop.value else None}")

        assert tap_dance is not None
        assert tap_dance.name == "td0"
        assert tap_dance.description == "TD0"
        assert tap_dance.tapping_term_ms == 200
        assert len(tap_dance.bindings) == 3
        assert tap_dance.bindings[0].value == "&kp"
        assert tap_dance.bindings[0].params[0].value == "N1"
        assert tap_dance.bindings[1].value == "&kp"
        assert tap_dance.bindings[1].params[0].value == "N2"
        assert tap_dance.bindings[2].value == "&kp"
        assert tap_dance.bindings[2].params[0].value == "N3"

    def test_convert_tap_dance_with_array_tapping_term(self):
        """Test tap dance conversion with array tapping-term-ms."""
        node = DTNode("&td1")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-tap-dance",
                raw="zmk,behavior-tap-dance",
            ),
        )
        # Array value for tapping-term-ms (some parsers return this)
        node.properties["tapping-term-ms"] = DTProperty(
            "tapping-term-ms",
            DTValue(DTValueType.ARRAY, [200], raw="<200>"),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(DTValueType.ARRAY, ["&kp A", "&kp B"], raw="<&kp A>, <&kp B>"),
        )

        converter = create_ast_behavior_converter()
        tap_dance = converter.convert_tap_dance_node(node)

        assert tap_dance is not None
        assert (
            tap_dance.tapping_term_ms == 200
        )  # Should extract first element from array

    def test_convert_tap_dance_invalid_compatible(self):
        """Test tap dance conversion with invalid compatible string."""
        node = DTNode("&not_tap_dance")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING, "zmk,behavior-hold-tap", raw="zmk,behavior-hold-tap"
            ),
        )

        converter = create_ast_behavior_converter()
        tap_dance = converter.convert_tap_dance_node(node)

        assert tap_dance is None

    def test_convert_tap_dance_with_defines(self):
        """Test tap dance conversion with define resolution."""
        node = DTNode("&td2")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-tap-dance",
                raw="zmk,behavior-tap-dance",
            ),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(
                DTValueType.ARRAY,
                ["&kp MY_KEY1", "&kp MY_KEY2"],
                raw="<&kp MY_KEY1>, <&kp MY_KEY2>",
            ),
        )

        defines = {"MY_KEY1": "A", "MY_KEY2": "B"}
        converter = create_ast_behavior_converter(defines)
        tap_dance = converter.convert_tap_dance_node(node)

        assert tap_dance is not None
        assert len(tap_dance.bindings) == 2
        assert tap_dance.bindings[0].params[0].value == "A"  # Resolved from MY_KEY1
        assert tap_dance.bindings[1].params[0].value == "B"  # Resolved from MY_KEY2


class TestStickyKeyBehaviorConverter:
    """Tests for sticky key behavior converter."""

    def test_convert_sticky_key_basic(self):
        """Test basic sticky key conversion."""
        node = DTNode("&sk")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-sticky-key",
                raw="zmk,behavior-sticky-key",
            ),
        )
        node.properties["label"] = DTProperty(
            "label",
            DTValue(DTValueType.STRING, "STICKY_KEY", raw="STICKY_KEY"),
        )
        node.properties["#binding-cells"] = DTProperty(
            "#binding-cells",
            DTValue(DTValueType.INTEGER, 1, raw="<1>"),
        )
        node.properties["release-after-ms"] = DTProperty(
            "release-after-ms",
            DTValue(DTValueType.INTEGER, 1000, raw="<1000>"),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(DTValueType.ARRAY, ["&kp"], raw="<&kp>"),
        )

        converter = create_ast_behavior_converter()
        sticky_key = converter.convert_sticky_key_node(node)

        assert sticky_key is not None
        assert sticky_key.name == "sk"
        assert sticky_key.description == "STICKY_KEY"
        assert sticky_key.release_after_ms == 1000
        assert sticky_key.quick_release is False
        assert sticky_key.lazy is False
        assert sticky_key.ignore_modifiers is False
        assert len(sticky_key.bindings) == 1
        assert sticky_key.bindings[0].value == "&kp"

    def test_convert_sticky_key_with_flags(self):
        """Test sticky key conversion with flags enabled."""
        node = DTNode("&sk_custom")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-sticky-key",
                raw="zmk,behavior-sticky-key",
            ),
        )
        node.properties["quick-release"] = DTProperty(
            "quick-release",
            DTValue(DTValueType.BOOLEAN, True, raw=""),
        )
        node.properties["lazy"] = DTProperty(
            "lazy",
            DTValue(DTValueType.BOOLEAN, True, raw=""),
        )
        node.properties["ignore-modifiers"] = DTProperty(
            "ignore-modifiers",
            DTValue(DTValueType.BOOLEAN, True, raw=""),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(DTValueType.ARRAY, ["&mo"], raw="<&mo>"),
        )

        converter = create_ast_behavior_converter()
        sticky_key = converter.convert_sticky_key_node(node)

        assert sticky_key is not None
        assert sticky_key.quick_release is True
        assert sticky_key.lazy is True
        assert sticky_key.ignore_modifiers is True

    def test_convert_sticky_key_invalid_compatible(self):
        """Test sticky key conversion with invalid compatible string."""
        node = DTNode("&not_sticky")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-tap-dance",
                raw="zmk,behavior-tap-dance",
            ),
        )

        converter = create_ast_behavior_converter()
        sticky_key = converter.convert_sticky_key_node(node)

        assert sticky_key is None


class TestCapsWordBehaviorConverter:
    """Tests for caps word behavior converter."""

    def test_convert_caps_word_basic(self):
        """Test basic caps word conversion."""
        node = DTNode("&caps_word")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-caps-word",
                raw="zmk,behavior-caps-word",
            ),
        )
        node.properties["label"] = DTProperty(
            "label",
            DTValue(DTValueType.STRING, "CAPS_WORD", raw="CAPS_WORD"),
        )
        node.properties["#binding-cells"] = DTProperty(
            "#binding-cells",
            DTValue(DTValueType.INTEGER, 0, raw="<0>"),
        )
        node.properties["mods"] = DTProperty(
            "mods",
            DTValue(DTValueType.INTEGER, 8, raw="<MOD_LSFT>"),  # MOD_LSFT = 8
        )

        converter = create_ast_behavior_converter()
        caps_word = converter.convert_caps_word_node(node)

        assert caps_word is not None
        assert caps_word.name == "caps_word"
        assert caps_word.description == "CAPS_WORD"
        assert caps_word.mods == 8
        assert len(caps_word.continue_list) == 0

    def test_convert_caps_word_with_continue_list(self):
        """Test caps word conversion with continue-list."""
        node = DTNode("&caps_word_custom")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-caps-word",
                raw="zmk,behavior-caps-word",
            ),
        )
        node.properties["continue-list"] = DTProperty(
            "continue-list",
            DTValue(
                DTValueType.ARRAY,
                ["UNDERSCORE", "MINUS", "BACKSPACE", "DELETE"],
                raw="<UNDERSCORE MINUS BACKSPACE DELETE>",
            ),
        )

        converter = create_ast_behavior_converter()
        caps_word = converter.convert_caps_word_node(node)

        assert caps_word is not None
        assert len(caps_word.continue_list) == 4
        assert "UNDERSCORE" in caps_word.continue_list
        assert "MINUS" in caps_word.continue_list
        assert "BACKSPACE" in caps_word.continue_list
        assert "DELETE" in caps_word.continue_list

    def test_convert_caps_word_with_defines(self):
        """Test caps word conversion with define resolution."""
        node = DTNode("&caps_word_defines")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-caps-word",
                raw="zmk,behavior-caps-word",
            ),
        )
        node.properties["continue-list"] = DTProperty(
            "continue-list",
            DTValue(
                DTValueType.ARRAY,
                ["MY_KEY1", "MY_KEY2"],
                raw="<MY_KEY1 MY_KEY2>",
            ),
        )
        node.properties["mods"] = DTProperty(
            "mods",
            DTValue(DTValueType.ARRAY, [8], raw="<8>"),  # Test array handling
        )

        defines = {"MY_KEY1": "UNDERSCORE", "MY_KEY2": "MINUS"}
        converter = create_ast_behavior_converter(defines)
        caps_word = converter.convert_caps_word_node(node)

        assert caps_word is not None
        assert caps_word.mods == 8  # Should extract first element from array
        assert len(caps_word.continue_list) == 2
        assert "UNDERSCORE" in caps_word.continue_list  # Resolved from MY_KEY1
        assert "MINUS" in caps_word.continue_list  # Resolved from MY_KEY2

    def test_convert_caps_word_invalid_compatible(self):
        """Test caps word conversion with invalid compatible string."""
        node = DTNode("&not_caps_word")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-sticky-key",
                raw="zmk,behavior-sticky-key",
            ),
        )

        converter = create_ast_behavior_converter()
        caps_word = converter.convert_caps_word_node(node)

        assert caps_word is None


class TestModMorphBehaviorConverter:
    """Tests for mod-morph behavior converter."""

    def test_convert_mod_morph_basic(self):
        """Test basic mod-morph conversion."""
        node = DTNode("&mm_bspc_del")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-mod-morph",
                raw="zmk,behavior-mod-morph",
            ),
        )
        node.properties["label"] = DTProperty(
            "label",
            DTValue(DTValueType.STRING, "BACKSPACE_DELETE", raw="BACKSPACE_DELETE"),
        )
        node.properties["#binding-cells"] = DTProperty(
            "#binding-cells",
            DTValue(DTValueType.INTEGER, 0, raw="<0>"),
        )
        node.properties["mods"] = DTProperty(
            "mods",
            DTValue(DTValueType.INTEGER, 8, raw="<MOD_LSFT>"),  # MOD_LSFT = 8
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(
                DTValueType.ARRAY,
                ["&kp BACKSPACE", "&kp DELETE"],
                raw="<&kp BACKSPACE>, <&kp DELETE>",
            ),
        )

        converter = create_ast_behavior_converter()
        mod_morph = converter.convert_mod_morph_node(node)

        assert mod_morph is not None
        assert mod_morph.name == "mm_bspc_del"
        assert mod_morph.description == "BACKSPACE_DELETE"
        assert mod_morph.mods == 8
        assert len(mod_morph.bindings) == 2
        assert mod_morph.bindings[0].value == "&kp"
        assert mod_morph.bindings[0].params[0].value == "BACKSPACE"
        assert mod_morph.bindings[1].value == "&kp"
        assert mod_morph.bindings[1].params[0].value == "DELETE"
        assert mod_morph.keep_mods is None

    def test_convert_mod_morph_with_keep_mods(self):
        """Test mod-morph conversion with keep-mods."""
        node = DTNode("&mm_custom")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-mod-morph",
                raw="zmk,behavior-mod-morph",
            ),
        )
        node.properties["mods"] = DTProperty(
            "mods",
            DTValue(
                DTValueType.INTEGER, 24, raw="<(MOD_LSFT|MOD_RSFT)>"
            ),  # 8 | 16 = 24
        )
        node.properties["keep-mods"] = DTProperty(
            "keep-mods",
            DTValue(DTValueType.INTEGER, 8, raw="<MOD_LSFT>"),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(
                DTValueType.ARRAY,
                ["&kp A", "&kp B"],
                raw="<&kp A>, <&kp B>",
            ),
        )

        converter = create_ast_behavior_converter()
        mod_morph = converter.convert_mod_morph_node(node)

        assert mod_morph is not None
        assert mod_morph.mods == 24
        assert mod_morph.keep_mods == 8

    def test_convert_mod_morph_exactly_two_bindings(self):
        """Test mod-morph must have exactly 2 bindings."""
        node = DTNode("&mm_invalid")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-mod-morph",
                raw="zmk,behavior-mod-morph",
            ),
        )
        node.properties["mods"] = DTProperty(
            "mods",
            DTValue(DTValueType.INTEGER, 8, raw="<8>"),
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(
                DTValueType.ARRAY,
                ["&kp A", "&kp B"],
                raw="<&kp A>, <&kp B>",
            ),
        )

        converter = create_ast_behavior_converter()
        mod_morph = converter.convert_mod_morph_node(node)

        assert mod_morph is not None
        assert len(mod_morph.bindings) == 2

    def test_convert_mod_morph_invalid_compatible(self):
        """Test mod-morph conversion with invalid compatible string."""
        node = DTNode("&not_mod_morph")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-caps-word",
                raw="zmk,behavior-caps-word",
            ),
        )

        converter = create_ast_behavior_converter()
        mod_morph = converter.convert_mod_morph_node(node)

        assert mod_morph is None

    def test_convert_mod_morph_with_defines(self):
        """Test mod-morph conversion with define resolution."""
        node = DTNode("&mm_defines")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-mod-morph",
                raw="zmk,behavior-mod-morph",
            ),
        )
        node.properties["mods"] = DTProperty(
            "mods",
            DTValue(DTValueType.ARRAY, [8], raw="<8>"),  # Test array handling
        )
        node.properties["bindings"] = DTProperty(
            "bindings",
            DTValue(
                DTValueType.ARRAY,
                ["&kp KEY1", "&kp KEY2"],
                raw="<&kp KEY1>, <&kp KEY2>",
            ),
        )

        defines = {"KEY1": "HOME", "KEY2": "END"}
        converter = create_ast_behavior_converter(defines)
        mod_morph = converter.convert_mod_morph_node(node)

        assert mod_morph is not None
        assert mod_morph.mods == 8  # Should extract first element from array
        assert len(mod_morph.bindings) == 2
        assert mod_morph.bindings[0].params[0].value == "HOME"  # Resolved from KEY1
        assert mod_morph.bindings[1].params[0].value == "END"  # Resolved from KEY2


class TestBehaviorConverterEdgeCases:
    """Test edge cases for all behavior converters."""

    def test_convert_with_missing_properties(self):
        """Test converters handle missing properties gracefully."""
        # Tap dance without bindings
        node = DTNode("&td_empty")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-tap-dance",
                raw="zmk,behavior-tap-dance",
            ),
        )

        converter = create_ast_behavior_converter()
        tap_dance = converter.convert_tap_dance_node(node)

        # Should return None because tap dance requires at least 2 bindings
        assert tap_dance is None

    def test_convert_with_invalid_numeric_values(self):
        """Test converters handle invalid numeric values."""
        node = DTNode("&sk_invalid")
        node.properties["compatible"] = DTProperty(
            "compatible",
            DTValue(
                DTValueType.STRING,
                "zmk,behavior-sticky-key",
                raw="zmk,behavior-sticky-key",
            ),
        )
        node.properties["release-after-ms"] = DTProperty(
            "release-after-ms",
            DTValue(DTValueType.STRING, "not_a_number", raw="not_a_number"),
        )

        converter = create_ast_behavior_converter()
        sticky_key = converter.convert_sticky_key_node(node)

        assert sticky_key is not None
        assert (
            sticky_key.release_after_ms is None
        )  # Should be None due to conversion failure

    def test_convert_with_empty_node(self):
        """Test converters handle empty nodes."""
        node = DTNode("")

        converter = create_ast_behavior_converter()

        assert converter.convert_tap_dance_node(node) is None
        assert converter.convert_sticky_key_node(node) is None
        assert converter.convert_caps_word_node(node) is None
        assert converter.convert_mod_morph_node(node) is None

    def test_convert_with_none_node(self):
        """Test converters handle None nodes."""
        converter = create_ast_behavior_converter()

        # These should not crash
        assert converter.convert_tap_dance_node(None) is None  # type: ignore[arg-type]
        assert converter.convert_sticky_key_node(None) is None  # type: ignore[arg-type]
        assert converter.convert_caps_word_node(None) is None  # type: ignore[arg-type]
        assert converter.convert_mod_morph_node(None) is None  # type: ignore[arg-type]
