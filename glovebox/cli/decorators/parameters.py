"""Legacy CLI parameter decorators module.

DEPRECATED: All decorators in this module have been removed in favor of the IOCommand pattern.

This module previously contained parameter processing decorators like:
- @with_input_file → Use IOCommand.load_input()
- @with_output_file → Use IOCommand.write_output()
- @with_format → Use IOCommand.format_and_print()
- @with_input_output → Use IOCommand methods
- @with_input_output_format → Use IOCommand methods

For new code, inherit from IOCommand and use its methods directly.
For constants, import from glovebox.cli.helpers.parameter_helpers instead.
"""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)

# This module is now empty - all functionality has been moved to:
# - IOCommand class in glovebox.cli.core.command_base
# - Helper functions in glovebox.cli.helpers.parameter_helpers
