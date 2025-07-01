"""Model conversion utilities for keymap parsing."""

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from glovebox.layout.models import ConfigDirective, KeymapComment, KeymapInclude

    class ModelConverterProtocol(Protocol):
        pass


class ModelFactory:
    """Factory for creating model instances from dictionaries."""

    @staticmethod
    def create_comment(comment_dict: dict[str, object]) -> "KeymapComment":
        """Convert comment dictionary to KeymapComment model instance."""
        from glovebox.layout.models import KeymapComment

        line_value = comment_dict.get("line", 0)
        return KeymapComment(
            text=str(comment_dict.get("text", "")),
            line=int(line_value) if isinstance(line_value, int | str) else 0,
            context=str(comment_dict.get("context", "")),
            is_block=bool(comment_dict.get("is_block", False)),
        )

    @staticmethod
    def create_include(include_dict: dict[str, object]) -> "KeymapInclude":
        """Convert include dictionary to KeymapInclude model instance."""
        from glovebox.layout.models import KeymapInclude

        line_value = include_dict.get("line", 0)
        return KeymapInclude(
            path=str(include_dict.get("path", "")),
            line=int(line_value) if isinstance(line_value, int | str) else 0,
            resolved_path=str(include_dict.get("resolved_path", "")),
        )

    @staticmethod
    def create_directive(directive_dict: dict[str, object]) -> "ConfigDirective":
        """Convert config directive dictionary to ConfigDirective model instance."""
        from glovebox.layout.models import ConfigDirective

        line_value = directive_dict.get("line", 0)
        return ConfigDirective(
            directive=str(directive_dict.get("directive", "")),
            condition=str(directive_dict.get("condition", "")),
            value=str(directive_dict.get("value", "")),
            line=int(line_value) if isinstance(line_value, int | str) else 0,
        )


class CommentSetter:
    """Utility for setting global comments on converter instances."""

    def __init__(self, model_converter: "ModelConverterProtocol") -> None:
        """Initialize with model converter instance."""
        self.model_converter = model_converter

    def set_global_comments(self, global_comments: list[dict[str, object]]) -> None:
        """Set global comments on all converter instances."""
        converter_attributes = [
            "hold_tap_converter",
            "macro_converter",
            "combo_converter",
            "tap_dance_converter",
            "sticky_key_converter",
            "caps_word_converter",
            "mod_morph_converter",
        ]

        for attr_name in converter_attributes:
            if hasattr(self.model_converter, attr_name):
                converter = getattr(self.model_converter, attr_name)
                if hasattr(converter, "_global_comments"):
                    converter._global_comments = global_comments


def create_model_factory() -> ModelFactory:
    """Create model factory instance."""
    return ModelFactory()


def create_comment_setter(model_converter: "ModelConverterProtocol") -> CommentSetter:
    """Create comment setter for a model converter."""
    return CommentSetter(model_converter)
