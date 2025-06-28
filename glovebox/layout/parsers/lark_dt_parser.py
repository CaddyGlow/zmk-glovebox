"""Lark-based device tree parser for ZMK keymap files."""

import logging
from pathlib import Path
from typing import Any

from lark import Lark, Token, Tree, UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from .ast_nodes import DTComment, DTNode, DTProperty, DTValue, DTValueType


logger = logging.getLogger(__name__)


class LarkDTParser:
    """Lark-based device tree parser with grammar-driven parsing."""

    def __init__(self) -> None:
        """Initialize the Lark parser with device tree grammar."""
        self.logger = logging.getLogger(__name__)

        # Load grammar from file
        grammar_path = Path(__file__).parent / "devicetree.lark"

        try:
            self.parser = Lark.open(
                grammar_path,
                parser="lalr",  # Fast parser
                start="start",
                propagate_positions=True,  # Track line/column info
                maybe_placeholders=False,
                transformer=None,  # We'll transform manually
            )
        except Exception as e:
            self.logger.error("Failed to load device tree grammar: %s", e)
            raise

    def parse(self, content: str) -> list[DTNode]:
        """Parse device tree content into multiple root nodes.

        Args:
            content: Device tree source content

        Returns:
            List of parsed root nodes

        Raises:
            Exception: If parsing fails
        """
        try:
            # Parse content into Lark tree
            tree = self.parser.parse(content)

            # Transform Lark tree to DTNode objects
            roots = self._transform_tree(tree)

            self.logger.debug("Successfully parsed %d root nodes", len(roots))
            return roots

        except (UnexpectedCharacters, UnexpectedToken, UnexpectedEOF) as e:
            self.logger.error("Parse error: %s", e)
            raise Exception(f"Device tree parse error: {e}") from e
        except Exception as e:
            self.logger.error("Unexpected parsing error: %s", e)
            raise

    def parse_safe(self, content: str) -> tuple[list[DTNode], list[str]]:
        """Parse device tree content with error collection.

        Args:
            content: Device tree source content

        Returns:
            Tuple of (parsed nodes, error messages)
        """
        try:
            roots = self.parse(content)
            return roots, []
        except Exception as e:
            error_msg = str(e)
            self.logger.warning("Parsing failed with error: %s", error_msg)
            return [], [error_msg]

    def _transform_tree(self, tree: Tree) -> list[DTNode]:
        """Transform Lark parse tree to DTNode objects.

        Args:
            tree: Lark parse tree

        Returns:
            List of DTNode objects
        """
        roots: list[DTNode] = []

        # Process top-level items
        for item in tree.children:
            if isinstance(item, Tree):
                if item.data == "node":
                    node = self._transform_node(item)
                    if node:
                        roots.append(node)
                elif item.data == "reference_node_modification":
                    node = self._transform_reference_node_modification(item)
                    if node:
                        roots.append(node)
                # Skip other top-level items like includes, comments, etc. for now

        return roots

    def _transform_node(self, node_tree: Tree) -> DTNode | None:
        """Transform a node tree to DTNode.

        Args:
            node_tree: Lark tree representing a node

        Returns:
            DTNode object or None if transformation fails
        """
        try:
            label = None
            node_path = None
            children: dict[str, DTNode] = {}
            properties: dict[str, DTProperty] = {}
            comments: list[DTComment] = []

            # Check if this is a reference node modification
            if node_tree.data == "reference_node_modification":
                return self._transform_reference_node_modification(node_tree)

            # Extract node components
            for child in node_tree.children:
                if isinstance(child, Tree):
                    if child.data == "label":
                        label = self._extract_label(child)
                    elif child.data == "node_path":
                        node_path = self._extract_node_path(child)
                    elif child.data == "node":
                        # Nested node
                        nested_node = self._transform_node(child)
                        if nested_node:
                            children[nested_node.name] = nested_node
                    elif child.data == "property":
                        prop = self._transform_property(child)
                        if prop:
                            properties[prop.name] = prop
                    elif child.data == "comment":
                        comment = self._transform_comment(child)
                        if comment:
                            comments.append(comment)

            # Create DTNode
            if not node_path:
                self.logger.warning("Node missing path")
                return None

            # Extract name from path (last segment)
            path_parts = node_path.strip("/").split("/")
            name = path_parts[-1] if path_parts and path_parts[0] else "root"

            node = DTNode(
                name=name,
                label=label or "",
                line=getattr(node_tree.meta, "line", 0),
                column=getattr(node_tree.meta, "column", 0),
            )

            # Add properties and children
            node.properties = properties
            node.children = children
            node.comments = comments

            return node

        except Exception as e:
            self.logger.error("Failed to transform node: %s", e)
            return None

    def _transform_reference_node_modification(self, ref_tree: Tree) -> DTNode | None:
        """Transform a reference node modification to DTNode.

        Args:
            ref_tree: Lark tree representing a reference node modification (&node {...})

        Returns:
            DTNode object or None if transformation fails
        """
        try:
            node_name = None
            children: dict[str, DTNode] = {}
            properties: dict[str, DTProperty] = {}
            comments: list[DTComment] = []

            # Extract the referenced node name and contents
            for child in ref_tree.children:
                if isinstance(child, Token) and child.type == "IDENTIFIER":
                    node_name = str(child)
                elif isinstance(child, Tree):
                    if child.data == "node":
                        # Nested node
                        nested_node = self._transform_node(child)
                        if nested_node:
                            children[nested_node.name] = nested_node
                    elif child.data == "property":
                        prop = self._transform_property(child)
                        if prop:
                            properties[prop.name] = prop
                    elif child.data == "comment":
                        comment = self._transform_comment(child)
                        if comment:
                            comments.append(comment)

            if not node_name:
                self.logger.warning("Reference node missing name")
                return None

            # Create DTNode for the reference modification
            node = DTNode(
                name=node_name,
                label="",  # Reference modifications don't have labels
                line=getattr(ref_tree.meta, "line", 0),
                column=getattr(ref_tree.meta, "column", 0),
            )

            # Add properties and children
            node.properties = properties
            node.children = children
            node.comments = comments

            return node

        except Exception as e:
            self.logger.error("Failed to transform reference node: %s", e)
            return None

    def _extract_label(self, label_tree: Tree) -> str:
        """Extract label from label tree."""
        for child in label_tree.children:
            if isinstance(child, Token):
                return str(child)
        return ""

    def _extract_node_path(self, path_tree: Tree) -> str:
        """Extract node path from path tree."""
        if not path_tree.children:
            return "/"

        path_parts = []
        for child in path_tree.children:
            if isinstance(child, Tree) and child.data == "path_segment":
                segment = self._extract_path_segment(child)
                if segment:
                    path_parts.append(segment)
            elif isinstance(child, Token) and child.type == "IDENTIFIER":
                path_parts.append(str(child))

        if not path_parts:
            return "/"

        # Join path parts
        if len(path_parts) == 1:
            return path_parts[0]
        else:
            return "/" + "/".join(path_parts)

    def _extract_path_segment(self, segment_tree: Tree) -> str:
        """Extract path segment from segment tree."""
        parts = []
        for child in segment_tree.children:
            if isinstance(child, Token):
                parts.append(str(child))
        return "".join(parts)

    def _transform_property(self, prop_tree: Tree) -> DTProperty | None:
        """Transform property tree to DTProperty.

        Args:
            prop_tree: Lark tree representing a property

        Returns:
            DTProperty object or None if transformation fails
        """
        try:
            name = None
            value = None

            for child in prop_tree.children:
                if isinstance(child, Token) and child.type == "IDENTIFIER":
                    name = str(child)
                elif isinstance(child, Tree):
                    # Property value(s)
                    if child.data == "property_values":
                        value = self._transform_property_values(child)
                    else:
                        value = self._transform_value(child)

            if not name:
                return None

            return DTProperty(
                name=name,
                value=value,
                line=getattr(prop_tree.meta, "line", 0),
                column=getattr(prop_tree.meta, "column", 0),
            )

        except Exception as e:
            self.logger.error("Failed to transform property: %s", e)
            return None

    def _transform_property_values(self, values_tree: Tree) -> DTValue | None:
        """Transform property values (potentially comma-separated) to DTValue.

        Args:
            values_tree: Lark tree representing property values

        Returns:
            DTValue object (single value or array of values)
        """
        try:
            values = []
            
            # Process all value children
            for child in values_tree.children:
                if isinstance(child, Tree) and child.data in [
                    "string_value", "number_value", "array_value", 
                    "reference_value", "boolean_value"
                ]:
                    value = self._transform_value(child)
                    if value:
                        values.append(value)

            # If only one value, return it directly
            if len(values) == 1:
                return values[0]
            
            # Multiple values - convert to array of the actual values
            combined_values = []
            for val in values:
                if val.type == DTValueType.ARRAY:
                    # If it's already an array, extend with its values
                    combined_values.extend(val.value)
                else:
                    # Single value
                    combined_values.append(val.value)
            
            return DTValue(type=DTValueType.ARRAY, value=combined_values)

        except Exception as e:
            self.logger.error("Failed to transform property values: %s", e)
            return None

    def _transform_value(self, value_tree: Tree) -> DTValue | None:
        """Transform value tree to DTValue.

        Args:
            value_tree: Lark tree representing a value

        Returns:
            DTValue object or None if transformation fails
        """
        try:
            if value_tree.data == "string_value":
                return self._transform_string_value(value_tree)
            elif value_tree.data == "number_value":
                return self._transform_number_value(value_tree)
            elif value_tree.data == "array_value":
                return self._transform_array_value(value_tree)
            elif value_tree.data == "reference_value":
                return self._transform_reference_value(value_tree)
            elif value_tree.data == "boolean_value":
                return self._transform_boolean_value(value_tree)
            else:
                self.logger.warning("Unknown value type: %s", value_tree.data)
                return None

        except Exception as e:
            self.logger.error("Failed to transform value: %s", e)
            return None

    def _transform_string_value(self, string_tree: Tree) -> DTValue:
        """Transform string value."""
        for child in string_tree.children:
            if isinstance(child, Token) and child.type == "STRING":
                # Remove quotes
                string_val = str(child)[1:-1]
                return DTValue(type=DTValueType.STRING, value=string_val)

        return DTValue(type=DTValueType.STRING, value="")

    def _transform_number_value(self, number_tree: Tree) -> DTValue:
        """Transform number value."""
        for child in number_tree.children:
            if isinstance(child, Token):
                if child.type == "HEX_NUMBER":
                    # Convert hex to int
                    hex_val = int(str(child), 16)
                    return DTValue(type=DTValueType.INTEGER, value=hex_val)
                elif child.type == "DEC_NUMBER":
                    # Convert decimal to int
                    dec_val = int(str(child))
                    return DTValue(type=DTValueType.INTEGER, value=dec_val)

        return DTValue(type=DTValueType.INTEGER, value=0)

    def _transform_array_value(self, array_tree: Tree) -> DTValue:
        """Transform array value."""
        array_items = []

        for child in array_tree.children:
            if isinstance(child, Tree):
                if child.data == "array_content":
                    # Extract tokens from array content
                    array_items = self._extract_array_content(child)
                else:
                    item_value = self._transform_value(child)
                    if item_value:
                        array_items.append(item_value.value)

        return DTValue(type=DTValueType.ARRAY, value=array_items)

    def _extract_array_content(self, content_tree: Tree) -> list[str]:
        """Extract array content tokens and properly group behavior calls."""
        tokens = []
        current_behavior = None

        for child in content_tree.children:
            if isinstance(child, Tree) and child.data == "array_token":
                # Check if this is a reference token, function call, or other type
                for token_child in child.children:
                    if isinstance(token_child, Tree) and token_child.data == "reference_token":
                        # This is a behavior reference like &kp
                        if current_behavior is not None:
                            # Save previous behavior
                            tokens.append(current_behavior)
                        
                        # Extract the reference (should be &IDENTIFIER)
                        ref_parts = []
                        for ref_token in token_child.children:
                            if isinstance(ref_token, Token):
                                ref_parts.append(str(ref_token))
                        current_behavior = "".join(ref_parts)  # Should be "&kp"
                        
                    elif isinstance(token_child, Tree) and token_child.data == "function_call":
                        # This is a function call like LS(END)
                        function_str = self._extract_function_call(token_child)
                        if current_behavior is not None:
                            # Parameter for current behavior
                            current_behavior = f"{current_behavior} {function_str}"
                        else:
                            # Standalone function call
                            tokens.append(function_str)
                        
                    elif isinstance(token_child, Token):
                        if token_child.type == "IDENTIFIER":
                            if current_behavior is not None:
                                # This is a parameter for the current behavior
                                current_behavior = f"{current_behavior} {token_child}"
                            else:
                                # Standalone identifier
                                tokens.append(str(token_child))
                        elif token_child.type in ["HEX_NUMBER", "DEC_NUMBER"]:
                            if current_behavior is not None:
                                # Parameter for current behavior
                                current_behavior = f"{current_behavior} {token_child}"
                            else:
                                # Standalone number
                                tokens.append(str(token_child))
                        elif token_child.type == "STRING":
                            string_val = str(token_child)[1:-1]  # Remove quotes
                            if current_behavior is not None:
                                # Parameter for current behavior
                                current_behavior = f"{current_behavior} {string_val}"
                            else:
                                # Standalone string
                                tokens.append(string_val)

        # Don't forget the last behavior
        if current_behavior is not None:
            tokens.append(current_behavior)

        return tokens

    def _extract_function_call(self, func_tree: Tree) -> str:
        """Extract function call from function_call tree.
        
        Args:
            func_tree: Lark tree representing a function call
            
        Returns:
            String representation of the function call
        """
        func_name = ""
        args = []
        
        for child in func_tree.children:
            if isinstance(child, Token) and child.type == "IDENTIFIER":
                func_name = str(child)
            elif isinstance(child, Tree) and child.data == "function_args":
                args = self._extract_function_args(child)
        
        # Format as function call
        args_str = ",".join(args) if args else ""
        return f"{func_name}({args_str})"
    
    def _extract_function_args(self, args_tree: Tree) -> list[str]:
        """Extract function arguments from function_args tree.
        
        Args:
            args_tree: Lark tree representing function arguments
            
        Returns:
            List of argument strings
        """
        args = []
        
        for child in args_tree.children:
            if isinstance(child, Tree) and child.data == "function_arg":
                for arg_child in child.children:
                    if isinstance(arg_child, Tree) and arg_child.data == "function_call":
                        # Nested function call
                        nested_func = self._extract_function_call(arg_child)
                        args.append(nested_func)
                    elif isinstance(arg_child, Token):
                        if arg_child.type == "STRING":
                            # Remove quotes from string arguments
                            args.append(str(arg_child)[1:-1])
                        else:
                            args.append(str(arg_child))
        
        return args

    def _transform_reference_value(self, ref_tree: Tree) -> DTValue:
        """Transform reference value."""
        for child in ref_tree.children:
            if isinstance(child, Token) and child.type == "IDENTIFIER":
                ref_name = str(child)
                return DTValue(type=DTValueType.REFERENCE, value=ref_name)
            elif isinstance(child, Tree) and child.data == "path":
                path_val = self._extract_reference_path(child)
                return DTValue(type=DTValueType.REFERENCE, value=path_val)

        return DTValue(type=DTValueType.REFERENCE, value="")

    def _extract_reference_path(self, path_tree: Tree) -> str:
        """Extract path from reference path tree."""
        # Similar to _extract_node_path but for references
        path_parts = []
        for child in path_tree.children:
            if isinstance(child, Tree) and child.data == "path_segment":
                segment = self._extract_path_segment(child)
                if segment:
                    path_parts.append(segment)
            elif isinstance(child, Token):
                path_parts.append(str(child))

        return "/".join(path_parts)

    def _transform_boolean_value(self, bool_tree: Tree) -> DTValue:
        """Transform boolean value."""
        for child in bool_tree.children:
            if isinstance(child, Token):
                bool_val = str(child).lower() == "true"
                return DTValue(type=DTValueType.BOOLEAN, value=bool_val)

        return DTValue(type=DTValueType.BOOLEAN, value=False)

    def _transform_comment(self, comment_tree: Tree) -> DTComment | None:
        """Transform comment tree to DTComment."""
        for child in comment_tree.children:
            if isinstance(child, Token) and child.type in ("SINGLE_LINE_COMMENT", "MULTI_LINE_COMMENT"):
                text = str(child)
                return DTComment(
                    text=text,
                    line=getattr(comment_tree.meta, "line", 0),
                    column=getattr(comment_tree.meta, "column", 0),
                )
        return None


# Factory functions for compatibility
def create_lark_dt_parser() -> LarkDTParser:
    """Create Lark-based device tree parser instance.

    Returns:
        Configured LarkDTParser instance
    """
    return LarkDTParser()


def parse_dt_lark(content: str) -> list[DTNode]:
    """Parse device tree content using Lark parser.

    Args:
        content: Device tree source content

    Returns:
        List of parsed root nodes

    Raises:
        Exception: If parsing fails
    """
    parser = create_lark_dt_parser()
    return parser.parse(content)


def parse_dt_lark_safe(content: str) -> tuple[list[DTNode], list[str]]:
    """Parse device tree content using Lark parser with error collection.

    Args:
        content: Device tree source content

    Returns:
        Tuple of (parsed nodes, error messages)
    """
    parser = create_lark_dt_parser()
    return parser.parse_safe(content)
