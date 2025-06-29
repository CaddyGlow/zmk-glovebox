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

        return KeymapComment(
            text=comment_dict.get("text", ""),
            line=comment_dict.get("line", 0),
            context=comment_dict.get("context", ""),
            is_block=comment_dict.get("is_block", False),
        )

    @staticmethod
    def create_include(include_dict: dict[str, object]) -> "KeymapInclude":
        """Convert include dictionary to KeymapInclude model instance."""
        from glovebox.layout.models import KeymapInclude

        return KeymapInclude(
            path=include_dict.get("path", ""),
            line=include_dict.get("line", 0),
            resolved_path=include_dict.get("resolved_path", ""),
        )

    @staticmethod
    def create_directive(directive_dict: dict[str, object]) -> "ConfigDirective":
        """Convert config directive dictionary to ConfigDirective model instance."""
        from glovebox.layout.models import ConfigDirective

        return ConfigDirective(
            directive=directive_dict.get("directive", ""),
            condition=directive_dict.get("condition", ""),
            value=directive_dict.get("value", ""),
            line=directive_dict.get("line", 0),
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
