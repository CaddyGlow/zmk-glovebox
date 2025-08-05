"""Variable resolution system for layout JSON data.

This module provides variable substitution capabilities for keyboard layout files,
allowing users to define global variables and reference them throughout the layout
using ${variable_name} syntax.
"""

import re
from typing import Any

from glovebox.core.structlog_logger import StructlogMixin, get_struct_logger


class VariableError(Exception):
    """Base exception for variable resolution errors."""


class UndefinedVariableError(VariableError):
    """Raised when a variable is not defined."""


class CircularReferenceError(VariableError):
    """Raised when circular variable reference is detected."""


class InvalidVariableExpressionError(VariableError):
    """Raised when variable expression syntax is invalid."""


class VariableResolver(StructlogMixin):
    """Handles variable substitution in layout JSON data.

    Supports the following variable syntax:
    - ${variable_name} - Basic variable substitution
    - ${variable_name:default} - Variable with default value fallback
    - ${nested.property} - Nested object property access
    """

    def __init__(self, variables: dict[str, Any]) -> None:
        """Initialize the variable resolver.

        Args:
            variables: Dictionary of variable name to value mappings
        """
        self.variables = variables
        self._resolved_cache: dict[str, Any] = {}
        self.logger = get_struct_logger(__name__)

    def resolve_value(self, value: Any) -> Any:
        """Resolve variables in a single value.

        Args:
            value: The value to resolve (string, dict, list, etc.)

        Returns:
            The value with all variables resolved

        Raises:
            UndefinedVariableError: If a variable is not defined
            CircularReferenceError: If circular reference is detected
            InvalidVariableExpressionError: If variable syntax is invalid
        """
        if isinstance(value, str):
            return self._substitute_string(value)
        elif isinstance(value, dict):
            return self.resolve_object(value)
        elif isinstance(value, list):
            return [self.resolve_value(item) for item in value]
        else:
            return value

    def resolve_object(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Recursively resolve variables in an object.

        Args:
            obj: Dictionary object to resolve variables in

        Returns:
            New dictionary with all variables resolved
        """
        resolved = {}
        for key, value in obj.items():
            # Skip the variables section to avoid self-referencing
            if key == "variables":
                resolved[key] = value
                continue
            resolved[key] = self.resolve_value(value)
        return resolved

    def flatten_layout(self, layout_data: dict[str, Any]) -> dict[str, Any]:
        """Return layout with all variables resolved and variables section removed.

        Args:
            layout_data: The layout data dictionary

        Returns:
            Flattened layout with variables resolved and variables section removed
        """
        if "variables" not in layout_data:
            return layout_data.copy()

        self.logger.debug(
            "Flattening layout with %d variables", len(layout_data["variables"])
        )

        # Resolve all variables in the layout
        resolved = self.resolve_object(layout_data)

        # Remove the variables section from the output
        flattened = {k: v for k, v in resolved.items() if k != "variables"}

        self.logger.debug("Layout flattened successfully")
        return flattened

    def _substitute_string(self, text: str) -> Any:
        """Handle ${variable_name} substitution in strings.

        Supports:
        - ${var} - Basic substitution
        - ${var:default} - With default value
        - ${nested.property} - Nested property access

        Args:
            text: String that may contain variable references

        Returns:
            Resolved value (may be string, int, bool, etc.)
        """
        # Pattern to match ${variable_name} or ${variable_name:default}
        pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1).strip()
            default_value = match.group(2) if match.group(2) is not None else None

            try:
                resolved_value = self._resolve_variable(var_name, default_value)
                return str(resolved_value)
            except UndefinedVariableError:
                if default_value is not None:
                    return default_value
                raise

        # Check if the entire string is a single variable reference
        full_match = re.fullmatch(pattern, text)
        if full_match:
            # Return the actual variable value (preserving type)
            var_name = full_match.group(1).strip()
            default_value = (
                full_match.group(2) if full_match.group(2) is not None else None
            )
            try:
                return self._resolve_variable(var_name, default_value)
            except UndefinedVariableError:
                if default_value is not None:
                    return self._coerce_type(default_value)
                raise

        # Replace all variable references in the string
        if re.search(pattern, text):
            try:
                return re.sub(pattern, replace_var, text)
            except UndefinedVariableError as e:
                raise UndefinedVariableError(f"In string '{text}': {e}") from e

        return text

    def _resolve_variable(self, var_name: str, default_value: str | None = None) -> Any:
        """Resolve a variable name to its value.

        Args:
            var_name: Name of the variable (may include nested access like 'timing.fast')
            default_value: Default value if variable is not found

        Returns:
            The resolved variable value

        Raises:
            UndefinedVariableError: If variable is not defined and no default provided
            CircularReferenceError: If circular reference detected
        """
        # Check cache first
        cache_key = f"{var_name}:{default_value or ''}"
        if cache_key in self._resolved_cache:
            return self._resolved_cache[cache_key]

        # Detect circular references
        self._detect_circular_references(var_name, set())

        # Handle nested property access (e.g., 'timing.fast')
        if "." in var_name:
            parts = var_name.split(".")
            current = self.variables

            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    if default_value is not None:
                        value = self._coerce_type(default_value)
                        self._resolved_cache[cache_key] = value
                        return value
                    raise UndefinedVariableError(f"Variable '{var_name}' not found")

            # Recursively resolve if the value contains variables
            resolved_value = self.resolve_value(current)
            self._resolved_cache[cache_key] = resolved_value
            return resolved_value

        # Simple variable access
        if var_name in self.variables:
            resolved_value = self.resolve_value(self.variables[var_name])
            self._resolved_cache[cache_key] = resolved_value
            return resolved_value

        if default_value is not None:
            value = self._coerce_type(default_value)
            self._resolved_cache[cache_key] = value
            return value

        raise UndefinedVariableError(f"Variable '{var_name}' not found")

    def _detect_circular_references(self, var_name: str, chain: set[str]) -> None:
        """Detect and prevent circular variable references.

        Args:
            var_name: Variable name being resolved
            chain: Set of variable names in the current resolution chain

        Raises:
            CircularReferenceError: If circular reference detected
        """
        if var_name in chain:
            chain_list = list(chain) + [var_name]
            raise CircularReferenceError(
                f"Circular reference detected: {' -> '.join(chain_list)}"
            )

        # For nested access, only check the root variable
        root_var = var_name.split(".")[0]
        if root_var not in self.variables:
            return

        # Check if the variable value contains references to variables in the chain
        var_value = self.variables[root_var]
        if isinstance(var_value, str):
            pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"
            for match in re.finditer(pattern, var_value):
                referenced_var = match.group(1).strip()
                new_chain = chain | {var_name}
                self._detect_circular_references(referenced_var, new_chain)

    def _coerce_type(self, value: str) -> Any:
        """Coerce string values to appropriate types.

        Args:
            value: String value to coerce

        Returns:
            Value coerced to appropriate type (int, bool, or string)
        """
        # Try to convert to int
        try:
            return int(value)
        except ValueError:
            pass

        # Try to convert to float
        try:
            return float(value)
        except ValueError:
            pass

        # Try to convert to bool
        lower_value = value.lower()
        if lower_value in ("true", "yes", "1"):
            return True
        elif lower_value in ("false", "no", "0"):
            return False

        # Return as string
        return value

    def get_variable_usage(self, layout_data: dict[str, Any]) -> dict[str, list[str]]:
        """Get a report of which variables are used where in the layout.

        Args:
            layout_data: The layout data to analyze

        Returns:
            Dictionary mapping variable names to list of paths where they're used
        """
        usage: dict[str, list[str]] = {}

        def scan_object(obj: Any, path: str = "") -> None:
            if isinstance(obj, str):
                pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"
                for match in re.finditer(pattern, obj):
                    var_name = match.group(1).strip()
                    if var_name not in usage:
                        usage[var_name] = []
                    usage[var_name].append(path)
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    if key != "variables":  # Skip variables section
                        new_path = f"{path}.{key}" if path else key
                        scan_object(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    scan_object(item, new_path)

        scan_object(layout_data)
        return usage

    def validate_variables(self, layout_data: dict[str, Any]) -> list[str]:
        """Validate that all variable references can be resolved.

        Args:
            layout_data: The layout data to validate

        Returns:
            List of validation error messages (empty if all valid)
        """
        errors: list[str] = []

        try:
            # Try to resolve the entire layout
            self.resolve_object(layout_data)
        except VariableError as e:
            errors.append(str(e))

        # Check for unused variables
        usage = self.get_variable_usage(layout_data)
        for var_name in self.variables:
            if var_name not in usage:
                errors.append(f"Variable '{var_name}' is defined but never used")

        return errors
