"""Behavior data model for keyboard layout behaviors.

This module provides a dedicated Pydantic model for behavior definitions
that can be decomposed into separate behavior files during component extraction.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from glovebox.models.base import GloveboxBaseModel


class BehaviorData(GloveboxBaseModel):
    """Model for keyboard layout behavior definitions.

    This model contains all the behavior-related fields that can be
    extracted from the main layout into a separate behaviors.json file.
    """

    # Variables for substitution
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Global variables for substitution using ${variable_name} syntax",
    )

    # User behavior definitions
    hold_taps: list[Any] = Field(default_factory=list, alias="holdTaps")
    combos: list[Any] = Field(default_factory=list)
    macros: list[Any] = Field(default_factory=list)
    input_listeners: list[Any] = Field(default_factory=list, alias="inputListeners")

    # Configuration parameters
    config_parameters: list[Any] = Field(
        default_factory=list, alias="config_parameters"
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with proper field names and JSON serialization."""
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)

    def is_empty(self) -> bool:
        """Check if this behavior data contains any actual behavior definitions.

        Returns:
            True if all behavior lists are empty and no variables defined
        """
        return (
            not self.variables
            and not self.hold_taps
            and not self.combos
            and not self.macros
            and not self.input_listeners
            and not self.config_parameters
        )

    def merge_with(self, other: BehaviorData) -> BehaviorData:
        """Merge this behavior data with another, combining all lists.

        Args:
            other: Other BehaviorData to merge with

        Returns:
            New BehaviorData with combined behaviors
        """
        # Merge variables (other takes precedence for conflicts)
        merged_variables = {**self.variables, **other.variables}

        return BehaviorData(
            variables=merged_variables,
            holdTaps=self.hold_taps + other.hold_taps,
            combos=self.combos + other.combos,
            macros=self.macros + other.macros,
            inputListeners=self.input_listeners + other.input_listeners,
            config_parameters=self.config_parameters + other.config_parameters,
        )
