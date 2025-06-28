"""Helper functions for compilation services."""

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glovebox.firmware.models import BuildResult


if TYPE_CHECKING:
    from glovebox.config.profile import KeyboardProfile
    from glovebox.protocols import MetricsProtocol


logger = logging.getLogger(__name__)


def convert_json_to_keymap_content(
    json_file: Path,
    keyboard_profile: "KeyboardProfile",
    session_metrics: "MetricsProtocol | None" = None,
) -> tuple[str | None, str | None, BuildResult]:
    """Convert JSON layout file to keymap and config content strings.

    This generates the keymap and config content in memory without writing temporary files.
    Used by compilation services that need the content as strings first.

    Args:
        json_file: Path to JSON layout file
        keyboard_profile: Keyboard profile for layout generation
        session_metrics: Optional session metrics for tracking operations

    Returns:
        Tuple of (keymap_content, config_content, result) where:
        - keymap_content: Generated keymap content as string (None if failed)
        - config_content: Generated config content as string (None if failed)
        - result: BuildResult with success/error information
    """
    try:
        # Import layout dependencies
        from glovebox.adapters import create_file_adapter, create_template_adapter
        from glovebox.layout import (
            create_behavior_registry,
        )
        from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
        from glovebox.layout.utils import process_json_file
        from glovebox.layout.utils.generation import (
            build_template_context,
            generate_kconfig_conf,
        )
        from glovebox.layout.zmk_generator import ZmkFileContentGenerator

        # Create adapters and services
        file_adapter = create_file_adapter()
        template_adapter = create_template_adapter()
        behavior_registry = create_behavior_registry()
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)
        dtsi_generator = ZmkFileContentGenerator(behavior_formatter)

        # Create a dummy session metrics if none provided
        if session_metrics is None:
            from glovebox.core.cache import create_default_cache
            from glovebox.core.metrics.session_metrics import SessionMetrics

            cache_manager = create_default_cache(tag="compilation_helpers")
            session_metrics = SessionMetrics(
                cache_manager=cache_manager, session_uuid="helper-session"
            )

        # Process JSON file to get layout data
        def process_layout_data(layout_data: Any) -> tuple[str, str]:
            # Register behaviors before processing
            from glovebox.layout.behavior.analysis import register_layout_behaviors

            register_layout_behaviors(keyboard_profile, layout_data, behavior_registry)

            # Generate config content
            config_content, _ = generate_kconfig_conf(layout_data, keyboard_profile)

            # Generate keymap content using the same logic as generate_keymap_file
            context = build_template_context(
                layout_data, keyboard_profile, dtsi_generator
            )

            # Get template content from keymap configuration
            keymap_section = keyboard_profile.keyboard_config.keymap
            inline_template = keymap_section.keymap_dtsi
            template_file = keymap_section.keymap_dtsi_file

            # Render template based on source type
            if inline_template:
                keymap_content = template_adapter.render_string(
                    inline_template, context
                )
            elif template_file:
                from glovebox.layout.utils.core_operations import (
                    resolve_template_file_path,
                )

                template_path = resolve_template_file_path(
                    keyboard_profile.keyboard_name, template_file
                )
                keymap_content = template_adapter.render_template(
                    template_path, context
                )
            else:
                from glovebox.core.errors import LayoutError

                raise LayoutError(
                    "No keymap template available in keyboard configuration. "
                    "Specify either keymap_dtsi (inline) or keymap_dtsi_file (template file)."
                )

            return keymap_content, config_content

        # Process the JSON file and generate content
        def process_and_convert(layout_data: Any) -> tuple[str, str]:
            # Use the data-based conversion method
            keymap_content, config_content, result = (
                convert_layout_data_to_keymap_content(
                    layout_data, keyboard_profile, session_metrics
                )
            )
            if not result.success:
                raise Exception(
                    f"Content conversion failed: {'; '.join(result.errors)}"
                )

            # We know these are not None due to success check
            assert keymap_content is not None
            assert config_content is not None
            return keymap_content, config_content

        keymap_content, config_content = process_json_file(
            json_file,
            "JSON to content conversion",
            process_and_convert,
            file_adapter,
        )

        return keymap_content, config_content, BuildResult(success=True)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("JSON to content conversion failed: %s", e, exc_info=exc_info)
        return None, None, BuildResult(success=False, errors=[str(e)])


def convert_json_to_keymap(
    json_file: Path,
    keyboard_profile: "KeyboardProfile",
    session_metrics: "MetricsProtocol | None" = None,
) -> tuple[Path | None, Path | None, BuildResult]:
    """Convert JSON layout file to keymap and config files.

    This is a convenience wrapper that generates content in memory first,
    then writes temporary files only when needed by compilation services.

    Args:
        json_file: Path to JSON layout file
        keyboard_profile: Keyboard profile for layout generation
        session_metrics: Optional session metrics for tracking operations

    Returns:
        Tuple of (keymap_file, config_file, result) where:
        - keymap_file: Path to generated keymap file (None if failed)
        - config_file: Path to generated config file (None if failed)
        - result: BuildResult with success/error information
    """
    # Generate content in memory first
    keymap_content, config_content, result = convert_json_to_keymap_content(
        json_file, keyboard_profile, session_metrics
    )

    if not result.success:
        return None, None, result

    # Only write temporary files when we have valid content
    try:
        temp_dir = tempfile.mkdtemp(prefix="json_to_keymap_")
        temp_path = Path(temp_dir)

        keymap_file = temp_path / "layout.keymap"
        config_file = temp_path / "layout.conf"

        # Write content to temporary files (we know content is not None here)
        assert keymap_content is not None
        assert config_content is not None
        keymap_file.write_text(keymap_content)
        config_file.write_text(config_content)

        return keymap_file, config_file, BuildResult(success=True)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error("Failed to write temporary files: %s", e, exc_info=exc_info)
        return None, None, BuildResult(success=False, errors=[str(e)])


def convert_layout_data_to_keymap_content(
    layout_data: Any,
    keyboard_profile: "KeyboardProfile",
    session_metrics: "MetricsProtocol | None" = None,
) -> tuple[str | None, str | None, BuildResult]:
    """Convert layout data to keymap and config content strings.

    This is the data-based version that works with in-memory layout data
    instead of reading from files. Supports stdin input through CLI commands.

    Args:
        layout_data: Layout data object (LayoutData)
        keyboard_profile: Keyboard profile for layout generation
        session_metrics: Optional session metrics for tracking operations

    Returns:
        Tuple of (keymap_content, config_content, result) where:
        - keymap_content: Generated keymap content as string (None if failed)
        - config_content: Generated config content as string (None if failed)
        - result: BuildResult with success/error information
    """
    try:
        # Import layout dependencies
        from glovebox.adapters import create_template_adapter
        from glovebox.layout import create_behavior_registry
        from glovebox.layout.behavior.formatter import BehaviorFormatterImpl
        from glovebox.layout.utils.generation import (
            build_template_context,
            generate_kconfig_conf,
        )
        from glovebox.layout.zmk_generator import ZmkFileContentGenerator

        # Create adapters and services
        template_adapter = create_template_adapter()
        behavior_registry = create_behavior_registry()
        behavior_formatter = BehaviorFormatterImpl(behavior_registry)
        dtsi_generator = ZmkFileContentGenerator(behavior_formatter)

        # Create a dummy session metrics if none provided
        if session_metrics is None:
            from glovebox.core.cache_v2 import (
                create_default_cache,  # type: ignore[import-untyped]
            )
            from glovebox.core.metrics.session_metrics import SessionMetrics

            cache_manager = create_default_cache(tag="compilation_helpers")
            session_metrics = SessionMetrics(
                cache_manager=cache_manager, session_uuid="helper-session"
            )

        # Register behaviors before processing
        from glovebox.layout.behavior.analysis import register_layout_behaviors

        register_layout_behaviors(keyboard_profile, layout_data, behavior_registry)

        # Generate config content
        config_content, _ = generate_kconfig_conf(layout_data, keyboard_profile)

        # Generate keymap content using the same logic as generate_keymap_file
        context = build_template_context(layout_data, keyboard_profile, dtsi_generator)

        # Get template content from keymap configuration
        keymap_section = keyboard_profile.keyboard_config.keymap
        inline_template = keymap_section.keymap_dtsi
        template_file = keymap_section.keymap_dtsi_file

        # Render template based on source type
        if inline_template:
            keymap_content = template_adapter.render_string(inline_template, context)
        elif template_file:
            from glovebox.layout.utils.core_operations import (
                resolve_template_file_path,
            )

            template_path = resolve_template_file_path(
                keyboard_profile.keyboard_name, template_file
            )
            keymap_content = template_adapter.render_template(template_path, context)
        else:
            from glovebox.core.errors import LayoutError

            raise LayoutError(
                "No keymap template available in keyboard configuration. "
                "Specify either keymap_dtsi (inline) or keymap_dtsi_file (template file)."
            )

        return keymap_content, config_content, BuildResult(success=True)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error(
            "Layout data to content conversion failed: %s", e, exc_info=exc_info
        )
        return None, None, BuildResult(success=False, errors=[str(e)])


def convert_layout_data_to_keymap(
    layout_data: Any,
    keyboard_profile: "KeyboardProfile",
    session_metrics: "MetricsProtocol | None" = None,
) -> tuple[Path | None, Path | None, BuildResult]:
    """Convert layout data to keymap and config files.

    This is the data-based version that works with in-memory layout data
    and generates temporary files for compilation services that need file paths.

    Args:
        layout_data: Layout data object (LayoutData)
        keyboard_profile: Keyboard profile for layout generation
        session_metrics: Optional session metrics for tracking operations

    Returns:
        Tuple of (keymap_file, config_file, result) where:
        - keymap_file: Path to generated keymap file (None if failed)
        - config_file: Path to generated config file (None if failed)
        - result: BuildResult with success/error information
    """
    # Generate content in memory first
    keymap_content, config_content, result = convert_layout_data_to_keymap_content(
        layout_data, keyboard_profile, session_metrics
    )

    if not result.success:
        return None, None, result

    # Only write temporary files when we have valid content
    try:
        temp_dir = tempfile.mkdtemp(prefix="layout_data_to_keymap_")
        temp_path = Path(temp_dir)

        keymap_file = temp_path / "layout.keymap"
        config_file = temp_path / "layout.conf"

        # Write content to temporary files (we know content is not None here)
        assert keymap_content is not None
        assert config_content is not None
        keymap_file.write_text(keymap_content)
        config_file.write_text(config_content)

        return keymap_file, config_file, BuildResult(success=True)

    except Exception as e:
        exc_info = logger.isEnabledFor(logging.DEBUG)
        logger.error(
            "Failed to write temporary files for layout data: %s", e, exc_info=exc_info
        )
        return None, None, BuildResult(success=False, errors=[str(e)])
