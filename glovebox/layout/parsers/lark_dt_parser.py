"""Lark-based device tree parser for ZMK keymap files."""

import logging
from pathlib import Path

from lark import Lark, Token, Tree, UnexpectedCharacters, UnexpectedEOF, UnexpectedToken

from .ast_nodes import (
    DTComment,
    DTConditional,
    DTNode,
    DTProperty,
    DTValue,
    DTValueType,
)


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
            # Preprocess content to handle line continuations in preprocessor directives
            preprocessed_content = self._preprocess_line_continuations(content)
            # Parse preprocessed content into Lark tree
            tree = self.parser.parse(preprocessed_content)

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
        pending_comments: list[DTComment] = []

        # Process top-level items and associate comments with following nodes
        for item in tree.children:
            if isinstance(item, Tree):
                if item.data == "node":
                    node = self._transform_node(item)
                    if node:
                        # Associate any pending comments with this node
                        if pending_comments:
                            node.comments.extend(pending_comments)
                            pending_comments = []
                        roots.append(node)
                elif item.data == "reference_node_modification":
                    node = self._transform_reference_node_modification(item)
                    if node:
                        # Associate any pending comments with this node
                        if pending_comments:
                            node.comments.extend(pending_comments)
                            pending_comments = []
                        roots.append(node)
                elif item.data == "comment":
                    # Collect comments that appear before nodes
                    comment = self._transform_comment(item)
                    if comment:
                        pending_comments.append(comment)
                elif item.data == "preprocessor_directive":
                    # Store preprocessor directives as conditionals in the first root node
                    if not roots:
                        # Create a temporary root node for holding preprocessor directives
                        temp_root = DTNode("", line=0, column=0)
                        roots.append(temp_root)

                    conditional = self._transform_preprocessor_directive(item)
                    if conditional:
                        roots[0].conditionals.append(conditional)
                # Skip other top-level items like includes for now

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
                if isinstance(child, Tree) and child.data == "property_name":
                    # Extract property name (may include #)
                    name_parts = []
                    for name_child in child.children:
                        if isinstance(name_child, Token):
                            name_parts.append(str(name_child))
                        elif (
                            isinstance(name_child, Tree)
                            and name_child.data == "hash_property"
                        ):
                            # Handle hash-prefixed properties like #binding-cells
                            name_parts.append("#")
                            for hash_child in name_child.children:
                                if isinstance(hash_child, Token):
                                    name_parts.append(str(hash_child))
                    name = "".join(name_parts)
                elif isinstance(child, Token) and child.type == "IDENTIFIER":
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
                if isinstance(child, Tree):
                    if child.data == "property_value_item":
                        # Handle property_value_item which can contain value or preprocessor_directive
                        for item_child in child.children:
                            if isinstance(item_child, Tree):
                                if item_child.data in [
                                    "string_value",
                                    "number_value",
                                    "array_value",
                                    "reference_value",
                                    "boolean_value",
                                    "identifier_value",
                                ]:
                                    value = self._transform_value(item_child)
                                    if value:
                                        values.append(value)
                                elif item_child.data == "preprocessor_directive":
                                    # Skip preprocessor directives in property values for now
                                    # They will be handled at the node level
                                    continue
                    elif child.data in [
                        "string_value",
                        "number_value",
                        "array_value",
                        "reference_value",
                        "boolean_value",
                        "identifier_value",
                    ]:
                        # Handle direct values (backwards compatibility)
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
            elif value_tree.data == "identifier_value":
                return self._transform_identifier_value(value_tree)
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
            if isinstance(child, Tree):
                if child.data == "array_item":
                    # Handle array_item which can contain array_token or preprocessor_directive
                    for item_child in child.children:
                        if isinstance(item_child, Tree):
                            if item_child.data == "array_token":
                                # Process the array token normally
                                current_behavior = self._process_array_token(
                                    item_child, tokens, current_behavior
                                )
                            elif item_child.data == "preprocessor_directive":
                                # Skip preprocessor directives in array content for now
                                # They will be handled at the node level
                                continue
                elif child.data == "array_token":
                    # Handle direct array_token (for backwards compatibility)
                    current_behavior = self._process_array_token(
                        child, tokens, current_behavior
                    )

        # Don't forget the last behavior
        if current_behavior is not None:
            tokens.append(current_behavior)

        return tokens

    def _process_array_token(
        self, token_tree: Tree, tokens: list[str], current_behavior: str | None
    ) -> str | None:
        """Process a single array token and update the tokens list.

        Args:
            token_tree: The array_token tree
            tokens: List to append completed tokens to
            current_behavior: Current behavior being built (if any)

        Returns:
            Updated current_behavior or None
        """
        for token_child in token_tree.children:
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

        return current_behavior

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
                    if (
                        isinstance(arg_child, Tree)
                        and arg_child.data == "function_call"
                    ):
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

    def _transform_identifier_value(self, identifier_tree: Tree) -> DTValue:
        """Transform identifier value (e.g., LEFT_PINKY_HOLDING_TYPE)."""
        for child in identifier_tree.children:
            if isinstance(child, Token) and child.type == "IDENTIFIER":
                identifier_val = str(child)
                return DTValue(type=DTValueType.STRING, value=identifier_val)

        return DTValue(type=DTValueType.STRING, value="")

    def _transform_comment(self, comment_tree: Tree) -> DTComment | None:
        """Transform comment tree to DTComment."""
        for child in comment_tree.children:
            if isinstance(child, Token) and child.type in (
                "SINGLE_LINE_COMMENT",
                "MULTI_LINE_COMMENT",
            ):
                text = str(child)
                return DTComment(
                    text=text,
                    line=getattr(comment_tree.meta, "line", 0),
                    column=getattr(comment_tree.meta, "column", 0),
                )
        return None

    def _transform_preprocessor_directive(
        self, preprocessor_tree: Tree
    ) -> DTConditional | None:
        """Transform preprocessor directive tree to DTConditional.

        Args:
            preprocessor_tree: Lark tree representing a preprocessor directive

        Returns:
            DTConditional object or None if transformation fails
        """

        for child in preprocessor_tree.children:
            if isinstance(child, Tree):
                directive_type = child.data
                line = getattr(child.meta, "line", 0)
                column = getattr(child.meta, "column", 0)

                if directive_type == "preprocessor_if":
                    condition = self._extract_preprocessor_expression(child)
                    return DTConditional("if", condition, line, column)

                elif directive_type == "preprocessor_ifdef":
                    condition = self._extract_identifier_from_tree(child)
                    return DTConditional("ifdef", condition, line, column)

                elif directive_type == "preprocessor_ifndef":
                    condition = self._extract_identifier_from_tree(child)
                    return DTConditional("ifndef", condition, line, column)

                elif directive_type == "preprocessor_define":
                    condition = self._extract_define_from_tree(child)
                    return DTConditional("define", condition, line, column)

                elif directive_type == "preprocessor_undef":
                    condition = self._extract_identifier_from_tree(child)
                    return DTConditional("undef", condition, line, column)

                elif directive_type == "preprocessor_else":
                    return DTConditional("else", "", line, column)

                elif directive_type == "preprocessor_elif":
                    condition = self._extract_preprocessor_expression(child)
                    return DTConditional("elif", condition, line, column)

                elif directive_type == "preprocessor_endif":
                    return DTConditional("endif", "", line, column)

                elif directive_type == "preprocessor_error":
                    condition = self._extract_error_message(child)
                    return DTConditional("error", condition, line, column)

        return None

    def _extract_preprocessor_expression(self, tree: Tree) -> str:
        """Extract preprocessor expression as string.

        Args:
            tree: Tree containing preprocessor expression

        Returns:
            String representation of the expression
        """
        expression_parts = []

        for child in tree.children:
            if isinstance(child, Tree) and child.data == "preprocessor_expression":
                expression_parts.append(self._build_expression_string(child))

        return " ".join(expression_parts)

    def _build_expression_string(self, expr_tree: Tree) -> str:
        """Build string representation of preprocessor expression.

        Args:
            expr_tree: Tree containing the expression

        Returns:
            String representation
        """
        parts = []

        for child in expr_tree.children:
            if isinstance(child, Tree):
                if child.data == "preprocessor_term":
                    parts.append(self._build_term_string(child))
                elif child.data == "logical_op":
                    for token in child.children:
                        if isinstance(token, Token):
                            parts.append(str(token))

        return " ".join(parts)

    def _build_term_string(self, term_tree: Tree) -> str:
        """Build string representation of preprocessor term.

        Args:
            term_tree: Tree containing the term

        Returns:
            String representation
        """
        for child in term_tree.children:
            if isinstance(child, Tree):
                if child.data == "defined_function":
                    identifier = self._extract_identifier_from_tree(child)
                    return f"defined({identifier})"
                elif child.data == "builtin_function":
                    function_name = ""
                    args = []
                    for func_child in child.children:
                        if (
                            isinstance(func_child, Token)
                            and func_child.type == "IDENTIFIER"
                        ):
                            function_name = str(func_child)
                        elif (
                            isinstance(func_child, Tree)
                            and func_child.data == "builtin_args"
                        ):
                            args = self._extract_builtin_args(func_child)
                    return f"{function_name}({', '.join(args)})"
                elif child.data == "negation_term":
                    sub_term = self._build_term_string(child)
                    return f"!{sub_term}"
                elif child.data == "paren_expression":
                    expr = self._build_expression_string(child)
                    return f"({expr})"
                elif child.data == "simple_term":
                    return self._extract_simple_term(child)
            elif isinstance(child, Token):
                return str(child)

        return ""

    def _extract_simple_term(self, term_tree: Tree) -> str:
        """Extract simple term (identifier, number, string).

        Args:
            term_tree: Tree containing simple term

        Returns:
            String representation
        """
        for child in term_tree.children:
            if isinstance(child, Token):
                return str(child)
        return ""

    def _extract_identifier_from_tree(self, tree: Tree) -> str:
        """Extract identifier from tree.

        Args:
            tree: Tree containing identifier

        Returns:
            Identifier string
        """
        for child in tree.children:
            if isinstance(child, Token) and child.type == "IDENTIFIER":
                return str(child)
        return ""

    def _extract_define_from_tree(self, tree: Tree) -> str:
        """Extract define directive content.

        Args:
            tree: Tree containing define directive

        Returns:
            Define content string
        """
        parts = []
        for child in tree.children:
            if isinstance(child, Token):
                parts.append(str(child))
            elif isinstance(child, Tree) and child.data == "define_value":
                # Extract the define value which may contain nested function calls
                value_str = self._extract_define_value(child)
                if value_str:
                    parts.append(value_str)
        return " ".join(parts)

    def _extract_define_value(self, value_tree: Tree) -> str:
        """Extract define value which may contain nested function calls.

        Args:
            value_tree: Tree containing define value tokens

        Returns:
            String representation of the define value
        """
        tokens = []
        for child in value_tree.children:
            if isinstance(child, Tree) and child.data == "define_token":
                token_str = self._extract_define_token(child)
                if token_str:
                    tokens.append(token_str)
            elif isinstance(child, Token):
                tokens.append(str(child))
        return " ".join(tokens)

    def _extract_define_token(self, token_tree: Tree) -> str:
        """Extract individual define token.

        Args:
            token_tree: Tree containing define token

        Returns:
            String representation of the token
        """
        for child in token_tree.children:
            if isinstance(child, Tree):
                if child.data == "function_call":
                    return self._extract_function_call(child)
                elif child.data == "arithmetic_expression":
                    return self._extract_arithmetic_expression(child)
                elif child.data == "preprocessor_value":
                    return self._extract_preprocessor_value(child)
            elif isinstance(child, Token):
                if child.type == "AMPERSAND":
                    # This should be followed by IDENTIFIER
                    continue
                elif child.type == "IDENTIFIER":
                    # Check if this is part of &IDENTIFIER pattern
                    return (
                        f"&{child}"
                        if any(
                            t.type == "AMPERSAND"
                            for t in token_tree.children
                            if isinstance(t, Token)
                        )
                        else str(child)
                    )
        return ""

    def _extract_arithmetic_expression(self, expr_tree: Tree) -> str:
        """Extract arithmetic expression like ((6 - DIFFICULTY_LEVEL) * 100).

        Args:
            expr_tree: Tree containing arithmetic expression

        Returns:
            String representation of the arithmetic expression
        """
        for child in expr_tree.children:
            if isinstance(child, Tree) and child.data == "arithmetic_expr":
                return f"({self._extract_arithmetic_expr(child)})"
        return ""

    def _extract_arithmetic_expr(self, expr_tree: Tree) -> str:
        """Extract arithmetic expression content.

        Args:
            expr_tree: Tree containing arithmetic expression content

        Returns:
            String representation
        """
        parts = []

        for child in expr_tree.children:
            if isinstance(child, Tree):
                if child.data == "arithmetic_term":
                    parts.append(self._extract_arithmetic_term(child))
                elif child.data == "arithmetic_op":
                    # Extract operator
                    for op_child in child.children:
                        if isinstance(op_child, Token):
                            parts.append(str(op_child))

        return " ".join(parts)

    def _extract_arithmetic_term(self, term_tree: Tree) -> str:
        """Extract arithmetic term.

        Args:
            term_tree: Tree containing arithmetic term

        Returns:
            String representation
        """
        for child in term_tree.children:
            if isinstance(child, Tree):
                if child.data == "arithmetic_expr":
                    return f"({self._extract_arithmetic_expr(child)})"
                elif child.data == "function_call":
                    return self._extract_function_call(child)
            elif isinstance(child, Token):
                return str(child)
        return ""

    def _extract_preprocessor_value(self, value_tree: Tree) -> str:
        """Extract preprocessor value (string, number, identifier, etc.).

        Args:
            value_tree: Tree containing preprocessor value

        Returns:
            String representation of the value
        """
        for child in value_tree.children:
            if isinstance(child, Token):
                if child.type == "STRING":
                    return str(child)  # Keep quotes for strings
                else:
                    return str(child)
        return ""

    def _extract_error_message(self, tree: Tree) -> str:
        """Extract error message from preprocessor error directive.

        Args:
            tree: Tree containing preprocessor error directive

        Returns:
            Error message string
        """
        for child in tree.children:
            if isinstance(child, Token) and child.type == "STRING":
                # Remove quotes from error message
                return str(child)[1:-1]
        return ""

    def _extract_builtin_args(self, args_tree: Tree) -> list[str]:
        """Extract builtin function arguments.

        Args:
            args_tree: Tree containing builtin function arguments

        Returns:
            List of argument strings
        """
        args = []
        for child in args_tree.children:
            if isinstance(child, Tree):
                if child.data == "builtin_arg":
                    # Process the builtin_arg
                    for arg_child in child.children:
                        if isinstance(arg_child, Tree):
                            if arg_child.data == "include_file_path":
                                # Handle angle-bracket include path
                                path_parts = []
                                for path_child in arg_child.children:
                                    if (
                                        isinstance(path_child, Tree)
                                        and path_child.data == "path_component"
                                    ):
                                        component_parts = []
                                        for component_child in path_child.children:
                                            if isinstance(component_child, Token):
                                                component_parts.append(
                                                    str(component_child)
                                                )
                                        path_parts.append("".join(component_parts))
                                    elif isinstance(path_child, Token):
                                        path_parts.append(str(path_child))
                                args.append(f"<{'/'.join(path_parts)}>")
                            else:
                                # Other tree structures, convert to string
                                args.append(str(arg_child))
                        elif isinstance(arg_child, Token):
                            if arg_child.type == "STRING":
                                # Keep quotes for string arguments in builtin functions
                                args.append(str(arg_child))
                            else:
                                args.append(str(arg_child))
                else:
                    # Handle direct values
                    args.append(str(child))
            elif isinstance(child, Token):
                if child.type == "STRING":
                    args.append(str(child)[1:-1])
                else:
                    args.append(str(child))
        return args

    def _extract_include_path(self, include_tree: Tree) -> str:
        """Extract include path from include_path tree.

        Args:
            include_tree: Tree containing include path

        Returns:
            Include path string
        """
        for child in include_tree.children:
            if isinstance(child, Token) and child.type == "STRING":
                # Quoted include path
                return str(child)
            elif isinstance(child, Tree) and child.data == "include_file_path":
                # Angle-bracket include path - reconstruct it
                path_parts = []
                for path_child in child.children:
                    if (
                        isinstance(path_child, Tree)
                        and path_child.data == "path_component"
                    ):
                        component_parts = []
                        for component_child in path_child.children:
                            if isinstance(component_child, Token):
                                component_parts.append(str(component_child))
                        path_parts.append("".join(component_parts))
                    elif isinstance(path_child, Token):
                        path_parts.append(str(path_child))
                return f"<{'/'.join(path_parts)}>"
        return ""

    def _preprocess_line_continuations(self, content: str) -> str:
        """Preprocess content to handle line continuations in preprocessor directives.

        Args:
            content: Original device tree content

        Returns:
            Preprocessed content with line continuations resolved
        """

        lines = content.split("\n")
        processed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if this is a preprocessor directive
            if line.strip().startswith("#"):
                # Collect the full preprocessor directive (including continuations)
                full_directive = line.rstrip()

                # Handle line continuations
                while full_directive.endswith("\\") and i + 1 < len(lines):
                    i += 1
                    # Remove the backslash and append next line
                    full_directive = full_directive[:-1] + " " + lines[i].strip()

                processed_lines.append(full_directive)
            else:
                processed_lines.append(line)

            i += 1

        # Apply additional preprocessing for macro expansion
        preprocessed_content = "\n".join(processed_lines)
        return self._preprocess_macro_expansion(preprocessed_content)

    def _preprocess_macro_expansion(self, content: str) -> str:
        """Preprocess content to handle simple macro expansion in array values.

        Args:
            content: Content with line continuations already resolved

        Returns:
            Content with basic macro expansion applied
        """
        import re

        # Extract common ZMK macro patterns for array expansion
        macro_definitions = {}

        # Find RIGHT_HAND_KEYS definition
        right_hand_match = re.search(
            r"#define\s+RIGHT_HAND_KEYS\s+(.*?)(?=\n\s*#define|\n\s*$|\n\s*/)",
            content,
            re.DOTALL,
        )
        if right_hand_match:
            # Extract all numbers from the definition
            numbers = re.findall(r"\b\d+\b", right_hand_match.group(1))
            if numbers:
                macro_definitions["RIGHT_HAND_KEYS"] = " ".join(numbers)

        # Find THUMB_KEYS definition
        thumb_match = re.search(
            r"#define\s+THUMB_KEYS\s+(.*?)(?=\n\s*#define|\n\s*$|\n\s*/)",
            content,
            re.DOTALL,
        )
        if thumb_match:
            # Extract all numbers from the definition
            numbers = re.findall(r"\b\d+\b", thumb_match.group(1))
            if numbers:
                macro_definitions["THUMB_KEYS"] = " ".join(numbers)

        # Find LEFT_HAND_KEYS definition (if present)
        left_hand_match = re.search(
            r"#define\s+LEFT_HAND_KEYS\s+(.*?)(?=\n\s*#define|\n\s*$|\n\s*/)",
            content,
            re.DOTALL,
        )
        if left_hand_match:
            numbers = re.findall(r"\b\d+\b", left_hand_match.group(1))
            if numbers:
                macro_definitions["LEFT_HAND_KEYS"] = " ".join(numbers)

        # Apply macro expansion in array contexts
        if macro_definitions:
            # Replace patterns like <RIGHT_HAND_KEYS THUMB_KEYS>
            def expand_array_macros(match):
                array_content = match.group(1).strip()
                expanded_parts = []

                for part in array_content.split():
                    if part in macro_definitions:
                        expanded_parts.append(macro_definitions[part])
                    else:
                        # Keep non-macro tokens as-is
                        expanded_parts.append(part)

                return f"<{' '.join(expanded_parts)}>"

            # Find and replace array expressions with macro references
            content = re.sub(
                r"<([^<>]*(?:RIGHT_HAND_KEYS|LEFT_HAND_KEYS|THUMB_KEYS)[^<>]*)>",
                expand_array_macros,
                content,
            )

            self.logger.debug(
                "Applied macro expansion for %d macros", len(macro_definitions)
            )

        return content


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
