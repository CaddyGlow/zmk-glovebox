"""Recursive descent parser for device tree source files."""

import logging

from glovebox.layout.parsers.ast_nodes import (
    DTComment,
    DTConditional,
    DTNode,
    DTParseError,
    DTProperty,
    DTValue,
    DTValueType,
)
from glovebox.layout.parsers.tokenizer import Token, TokenType, tokenize_dt


logger = logging.getLogger(__name__)


class DTParser:
    """Recursive descent parser for device tree source."""

    def __init__(self, tokens: list[Token]) -> None:
        """Initialize parser.

        Args:
            tokens: List of tokens from tokenizer
        """
        self.tokens = tokens
        self.pos = -1  # Start at -1 so first _advance() goes to 0
        self.current_token: Token | None = None
        self.errors: list[DTParseError] = []
        self.comments: list[DTComment] = []
        self._advance()

    def parse(self) -> DTNode:
        """Parse tokens into device tree AST.

        Returns:
            Root device tree node

        Raises:
            DTParseError: If parsing fails
        """
        try:
            # Process any leading comments or preprocessor directives
            self._consume_comments_and_preprocessor()

            # Parse root node structure
            root = self._parse_root_node()

            # If no root node was parsed, create an empty one
            if root is None:
                root = DTNode(
                    "", line=self._current_line(), column=self._current_column()
                )

            if self.errors:
                # Return partial result with errors
                logger.warning("Parsing completed with %d errors", len(self.errors))
                for error in self.errors:
                    logger.warning(str(error))

            return root

        except Exception as e:
            error = DTParseError(
                f"Fatal parsing error: {e}",
                self._current_line(),
                self._current_column(),
            )
            self.errors.append(error)
            raise error from e

    def parse_multiple(self) -> list[DTNode]:
        """Parse tokens into multiple device tree ASTs.

        Returns:
            List of root device tree nodes

        Raises:
            DTParseError: If parsing fails
        """
        try:
            roots = []

            # Process any leading comments or preprocessor directives
            self._consume_comments_and_preprocessor()

            # Parse multiple root nodes
            while not self._is_at_end():
                # Skip any comments between root nodes
                if self._consume_comments_and_preprocessor():
                    continue

                # Parse next root node
                root = self._parse_root_node()
                if root:
                    roots.append(root)

                # Skip any trailing comments
                self._consume_comments_and_preprocessor()

            if self.errors:
                # Return partial result with errors
                logger.warning("Parsing completed with %d errors", len(self.errors))
                for error in self.errors:
                    logger.warning(str(error))

            return roots

        except Exception as e:
            error = DTParseError(
                f"Fatal parsing error: {e}",
                self._current_line(),
                self._current_column(),
            )
            self.errors.append(error)
            raise error from e

    def _parse_root_node(self) -> DTNode | None:
        """Parse the root device tree node.

        Returns:
            Root DTNode or None if no content found
        """
        # Check if we're at the end or no tokens to parse
        if self._is_at_end():
            return None

        root = DTNode("", line=self._current_line(), column=self._current_column())

        # Expect root node structure: / { ... };
        if self._match(TokenType.SLASH):
            # Handle preprocessor directives and comments for explicit root
            root.comments.extend(self.comments)
            self.comments = []

            self._advance()  # consume /

            # Skip any comments or preprocessor directives after /
            self._consume_comments_and_preprocessor()

            if self._match(TokenType.LBRACE):
                self._advance()  # consume {
                self._parse_node_body(root)
                self._expect(TokenType.RBRACE)
                self._expect(TokenType.SEMICOLON)
            else:
                self._error("Expected '{' after '/'")
        else:
            # Check if we have a standalone node (not inside a root)
            if self._match(TokenType.IDENTIFIER) or self._match(TokenType.REFERENCE):
                # This looks like a standalone node, parse it as a child of empty root
                # Keep comments available for association with the standalone node
                child = self._parse_child_node()
                if child:
                    root.add_child(child)
                # Only attach remaining comments to root after parsing standalone nodes
                root.comments.extend(self.comments)
                self.comments = []
            else:
                # Handle other nodes without explicit root
                # For other cases, attach comments to root
                root.comments.extend(self.comments)
                self.comments = []
                self._parse_node_body(root)

        # Return None if no meaningful content was parsed
        if not root.properties and not root.children and not root.comments:
            return None

        return root

    def _parse_node_body(self, node: DTNode) -> None:
        """Parse the body of a device tree node.

        Args:
            node: Node to populate with properties and children
        """
        pending_comments: list[DTComment] = []

        while not self._match(TokenType.RBRACE) and not self._is_at_end():
            # Collect comments and preprocessor directives
            if self._consume_comments_and_preprocessor():
                # Store comments as pending instead of immediately attaching
                pending_comments.extend(self.comments)
                self.comments = []
                continue

            # Try to parse property or child node
            try:
                if self._is_property():
                    # For properties, attach pending comments to current node
                    if pending_comments:
                        node.comments.extend(pending_comments)
                        pending_comments = []

                    prop = self._parse_property()
                    if prop:
                        node.add_property(prop)
                else:
                    # For child nodes, let the child node take the pending comments
                    if pending_comments:
                        self.comments.extend(pending_comments)
                        pending_comments = []

                    child = self._parse_child_node()
                    if child:
                        node.add_child(child)
                    else:
                        # Safety: if we can't parse anything, advance to avoid infinite loop
                        self._error(f"Unexpected token: {self.current_token}")
                        self._advance()
            except Exception as e:
                self._error(f"Failed to parse node body: {e}")
                self._synchronize()

        # Attach any remaining pending comments to the current node
        if pending_comments:
            node.comments.extend(pending_comments)

    def _parse_property(self) -> DTProperty | None:
        """Parse a device tree property.

        Returns:
            Parsed DTProperty or None if parsing fails
        """
        if not (self._match(TokenType.IDENTIFIER) or self._match(TokenType.COMPATIBLE)):
            return None

        if self.current_token is None:
            return None

        prop_name = self.current_token.value
        line = self._current_line()
        column = self._current_column()
        self._advance()

        # Create property object
        prop = None

        # Handle boolean properties (no value)
        if self._match(TokenType.SEMICOLON):
            self._advance()
            prop = DTProperty(prop_name, DTValue.boolean(True), line, column)
        # Handle properties with values
        elif self._match(TokenType.EQUALS):
            self._advance()
            value = self._parse_property_values()
            self._expect(TokenType.SEMICOLON)
            prop = DTProperty(prop_name, value, line, column)
        else:
            self._error("Expected '=' or ';' after property name")
            return None

        # Associate any pending comments with this property
        if prop:
            self._associate_pending_comments_with_property(prop, line)

        return prop

    def _parse_property_values(self) -> DTValue:
        """Parse property values, handling multiple comma-separated values.

        Returns:
            Single DTValue or array of values
        """
        values = []
        raw_parts = []

        # Parse first value
        first_value = self._parse_property_value()
        values.append(first_value)
        raw_parts.append(first_value.raw)

        # Check for additional comma-separated values
        while self._match(TokenType.COMMA):
            raw_parts.append(", ")
            self._advance()  # consume comma

            # Skip whitespace/comments after comma
            self._consume_comments_and_preprocessor()

            next_value = self._parse_property_value()
            values.append(next_value)
            raw_parts.append(next_value.raw)

        # If only one value, return it directly
        if len(values) == 1:
            return values[0]

        # Otherwise return as array of values
        # For device tree, multiple comma-separated values form an array
        raw = "".join(raw_parts)
        # Extract the actual values from DTValue objects
        actual_values: list[int | str] = []
        for v in values:
            if v.type == DTValueType.ARRAY:
                # If it's an array, extend with its values
                actual_values.extend(v.value)
            else:
                # Otherwise append the value itself
                actual_values.append(
                    v.value if v.type != DTValueType.REFERENCE else f"&{v.value}"
                )

        return DTValue.array(actual_values, raw)

    def _parse_property_value(self) -> DTValue:
        """Parse a property value.

        Returns:
            Parsed DTValue
        """
        if self._match(TokenType.STRING):
            if self.current_token is None:
                return DTValue.string("", "")
            value = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            return DTValue.string(value, raw)

        elif self._match(TokenType.NUMBER):
            if self.current_token is None:
                return DTValue.string("", "")
            value_str = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            try:
                # Handle hex numbers
                if value_str.startswith("0x"):
                    int_value = int(value_str, 16)
                else:
                    int_value = int(value_str)
                return DTValue.integer(int_value, raw)
            except ValueError:
                self._error(f"Invalid number: {value_str}")
                return DTValue.string(value_str, raw)

        elif self._match(TokenType.REFERENCE):
            if self.current_token is None:
                return DTValue.string("", "")
            ref = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            return DTValue.reference(ref, raw)

        elif self._match(TokenType.ANGLE_OPEN):
            return self._parse_array_value()

        elif self._match(TokenType.IDENTIFIER):
            if self.current_token is None:
                return DTValue.string("", "")
            # Handle identifiers as string values
            value = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            return DTValue.string(value, raw)

        else:
            self._error("Expected property value")
            return DTValue.string("", "")

    def _parse_array_value(self) -> DTValue:
        """Parse an array value in angle brackets.

        Returns:
            DTValue with array type
        """
        if not self._match(TokenType.ANGLE_OPEN):
            self._error("Expected '<' for array value")
            return DTValue.array([])

        start_pos = self.pos
        self._advance()  # consume <

        values: list[int | str] = []
        raw_parts = ["<"]

        while not self._match(TokenType.ANGLE_CLOSE) and not self._is_at_end():
            if self._match(TokenType.NUMBER):
                if self.current_token is None:
                    break
                value_str = self.current_token.value
                raw_parts.append(value_str)
                try:
                    if value_str.startswith("0x"):
                        values.append(int(value_str, 16))
                    else:
                        values.append(int(value_str))
                except ValueError:
                    values.append(value_str)
                self._advance()

            elif self._match(TokenType.REFERENCE):
                if self.current_token is None:
                    break
                ref = self.current_token.raw
                raw_parts.append(ref)
                values.append(ref)
                self._advance()

            elif self._match(TokenType.IDENTIFIER):
                if self.current_token is None:
                    break
                ident = self.current_token.value
                raw_parts.append(ident)
                values.append(ident)
                self._advance()

            elif self._match(TokenType.COMMA):
                raw_parts.append(",")
                self._advance()

            else:
                # Skip unknown tokens within array
                raw_parts.append(self.current_token.raw if self.current_token else "")
                self._advance()

        if self._match(TokenType.ANGLE_CLOSE):
            raw_parts.append(">")
            self._advance()
        else:
            self._error("Expected '>' to close array value")

        raw = " ".join(raw_parts)
        return DTValue.array(values, raw)

    def _parse_child_node(self) -> DTNode | None:
        """Parse a child device tree node.

        Returns:
            Parsed DTNode or None if parsing fails
        """
        line = self._current_line()
        column = self._current_column()

        # Parse node name, which can be:
        # - simple: node_name
        # - with label: label: node_name
        # - with unit address: node_name@address
        # - complex: label: node_name@address

        label = ""
        name = ""
        unit_address = ""

        # Check for node name - can be identifier or reference
        if self._match(TokenType.IDENTIFIER):
            if self.current_token is None:
                self._error("Expected node name")
                return None
            first_ident = self.current_token.value
            self._advance()

            if self._match(TokenType.COLON):
                # This is a label
                label = first_ident
                self._advance()  # consume :

                # Parse the actual node name
                if self._match(TokenType.IDENTIFIER) and self.current_token is not None:
                    name = self.current_token.value
                    self._advance()
                else:
                    self._error("Expected node name after label")
                    return None
            else:
                # This is just the node name
                name = first_ident

            # Check for unit address
            if self._match(TokenType.AT):
                self._advance()  # consume @
                if (
                    self._match(TokenType.IDENTIFIER) or self._match(TokenType.NUMBER)
                ) and self.current_token is not None:
                    unit_address = self.current_token.value
                    self._advance()
                else:
                    self._error("Expected unit address after '@'")

        elif self._match(TokenType.REFERENCE):
            # Handle reference nodes like &node_reference { ... }
            if self.current_token is None:
                self._error("Expected reference name")
                return None
            name = self.current_token.value  # This will be the reference name without &
            self._advance()

        else:
            self._error("Expected node name")
            return None

        # Parse node body
        if self._match(TokenType.LBRACE):
            self._advance()  # consume {
            node = DTNode(name, label, unit_address, line, column)

            # Associate pending comments with this node based on line proximity
            self._associate_pending_comments_with_node(node, line)

            self._parse_node_body(node)
            self._expect(TokenType.RBRACE)
            self._expect(TokenType.SEMICOLON)
            return node
        else:
            self._error("Expected '{' after node name")
            return None

    def _is_property(self) -> bool:
        """Check if current position is start of a property.

        Returns:
            True if current position looks like a property
        """
        # Properties can be identifiers or special keywords
        if not (self._match(TokenType.IDENTIFIER) or self._match(TokenType.COMPATIBLE)):
            return False

        # Look ahead to see if this is property (= or ;) or node ({)
        if self.pos + 1 < len(self.tokens):
            next_token = self.tokens[self.pos + 1]
            return next_token.type in (TokenType.EQUALS, TokenType.SEMICOLON)

        return False

    def _consume_comments_and_preprocessor(self) -> bool:
        """Consume any comments or preprocessor directives.

        Returns:
            True if any were consumed
        """
        consumed = False
        initial_comment_count = len(self.comments)

        while self._match(TokenType.COMMENT) or self._match(TokenType.PREPROCESSOR):
            if self._match(TokenType.COMMENT):
                if self.current_token is None:
                    break
                comment_text = self.current_token.value
                line = self._current_line()
                column = self._current_column()
                is_block = comment_text.startswith("/*")
                comment = DTComment(comment_text, line, column, is_block)
                self.comments.append(comment)
                consumed = True
                self._advance()

            elif self._match(TokenType.PREPROCESSOR):
                if self.current_token is None:
                    break
                directive_text = self.current_token.value
                line = self._current_line()
                column = self._current_column()

                # Parse preprocessor directive
                parts = directive_text.split(None, 1)
                directive = parts[0][1:]  # Remove #
                condition = parts[1] if len(parts) > 1 else ""

                conditional = DTConditional(directive, condition, line, column)
                # Convert conditional to comment for consistent handling
                comment_text = f"#{directive} {condition}".strip()
                comment = DTComment(comment_text, line, column, False)
                self.comments.append(comment)
                consumed = True
                self._advance()

        if consumed:
            final_comment_count = len(self.comments)

        return consumed

    def _associate_pending_comments_with_node(
        self, node: DTNode, node_line: int
    ) -> None:
        """Associate pending comments with a node based on line proximity.

        Comments are associated if they appear immediately before the node
        (within a few lines and with no other content in between).

        Args:
            node: Node to associate comments with
            node_line: Line number where the node starts
        """
        if not self.comments:
            return

        # Find comments that should be associated with this node
        # Comments are eligible if they're close to the node line (within 3-5 lines based on type)
        # and there's no significant content between the comment and the node
        associated_comments = []

        for comment in self.comments:
            line_distance = node_line - comment.line

            # Determine proximity limit based on comment type
            # Block comments can be further away than line comments
            max_distance = 5 if comment.is_block else 3

            # Comment must be before the node and within reasonable proximity
            if 0 < line_distance <= max_distance:
                # Check if this comment is the closest preceding comment
                # (no other comments between this one and the node)
                is_closest = True
                for other_comment in self.comments:
                    if (
                        comment.line < other_comment.line < node_line
                        and other_comment not in associated_comments
                    ):
                        is_closest = False
                        break

                if is_closest:
                    associated_comments.append(comment)

        # Associate the most relevant comments (usually the ones closest to the node)
        if associated_comments:
            # Sort by line number (closest first) and take up to 2 comments
            associated_comments.sort(key=lambda c: c.line, reverse=True)
            node.comments.extend(associated_comments[:2])

            # Remove associated comments from pending list
            for comment in associated_comments:
                if comment in self.comments:
                    self.comments.remove(comment)

    def _associate_pending_comments_with_property(
        self, prop: DTProperty, prop_line: int
    ) -> None:
        """Associate pending comments with a property based on line proximity.

        Args:
            prop: Property to associate comments with
            prop_line: Line number where the property starts
        """
        if not self.comments:
            return

        # For properties, we're more restrictive - only associate comments
        # that are immediately preceding (within 1-2 lines)
        associated_comments = []

        for comment in self.comments:
            line_distance = prop_line - comment.line

            # Property comments should be very close (within 2 lines)
            if 0 < line_distance <= 2:
                associated_comments.append(comment)

        # Associate the closest comment to the property
        if associated_comments:
            # Sort by line number (closest first) and take only the closest one
            associated_comments.sort(key=lambda c: c.line, reverse=True)
            prop.comments.append(associated_comments[0].text)

            # Remove associated comment from pending list
            if associated_comments[0] in self.comments:
                self.comments.remove(associated_comments[0])

    def _match(self, token_type: TokenType) -> bool:
        """Check if current token matches given type.

        Args:
            token_type: Type to match

        Returns:
            True if current token matches
        """
        return (
            not self._is_at_end()
            and self.current_token is not None
            and self.current_token.type == token_type
        )

    def _advance(self) -> Token | None:
        """Advance to next token.

        Returns:
            Previous token
        """
        previous = self.current_token
        self.pos += 1
        if self.pos < len(self.tokens):
            self.current_token = self.tokens[self.pos]
        else:
            self.current_token = None
        return previous

    def _is_at_end(self) -> bool:
        """Check if we've reached end of tokens.

        Returns:
            True if at end
        """
        return self.current_token is None or self.current_token.type == TokenType.EOF

    def _expect(self, token_type: TokenType) -> Token | None:
        """Expect and consume a specific token type.

        Args:
            token_type: Expected token type

        Returns:
            Consumed token or None if not found

        Raises:
            DTParseError: If token not found
        """
        if self._match(token_type):
            return self._advance()
        else:
            current = self.current_token.type.value if self.current_token else "EOF"
            self._error(f"Expected {token_type.value}, got {current}")
            return None

    def _error(self, message: str) -> None:
        """Record a parsing error.

        Args:
            message: Error message
        """
        line = self._current_line()
        column = self._current_column()
        context = self._get_context()
        error = DTParseError(message, line, column, context)
        self.errors.append(error)
        logger.warning(str(error))

    def _synchronize(self) -> None:
        """Synchronize parser after error by advancing to next statement."""
        while not self._is_at_end():
            if self.current_token is not None and self.current_token.type in (
                TokenType.SEMICOLON,
                TokenType.RBRACE,
            ):
                self._advance()
                return
            self._advance()

    def _current_line(self) -> int:
        """Get current line number.

        Returns:
            Line number
        """
        return self.current_token.line if self.current_token else 0

    def _current_column(self) -> int:
        """Get current column number.

        Returns:
            Column number
        """
        return self.current_token.column if self.current_token else 0

    def _get_context(self, window: int = 3) -> str:
        """Get context around current position for error reporting.

        Args:
            window: Number of tokens before/after to include

        Returns:
            Context string
        """
        start = max(0, self.pos - window)
        end = min(len(self.tokens), self.pos + window + 1)
        tokens = self.tokens[start:end]

        context_parts = []
        for i, token in enumerate(tokens):
            if start + i == self.pos:
                context_parts.append(f">>> {token.raw} <<<")
            else:
                context_parts.append(token.raw)

        return " ".join(context_parts)


def parse_dt(text: str) -> DTNode:
    """Parse device tree source text into AST.

    Args:
        text: Device tree source

    Returns:
        Root DTNode

    Raises:
        DTParseError: If parsing fails
    """
    tokens = tokenize_dt(text)
    parser = DTParser(tokens)
    return parser.parse()


def parse_dt_safe(text: str) -> tuple[DTNode | None, list[DTParseError]]:
    """Parse device tree source with error handling.

    Args:
        text: Device tree source

    Returns:
        Tuple of (root_node, errors)
    """
    try:
        tokens = tokenize_dt(text)
        parser = DTParser(tokens)
        root = parser.parse()
        return root, parser.errors
    except Exception as e:
        error = DTParseError(f"Parsing failed: {e}")
        return None, [error]


def parse_dt_multiple(text: str) -> list[DTNode]:
    """Parse device tree source text into multiple ASTs.

    Args:
        text: Device tree source

    Returns:
        List of root DTNodes

    Raises:
        DTParseError: If parsing fails
    """
    tokens = tokenize_dt(text)
    parser = DTParser(tokens)
    return parser.parse_multiple()


def parse_dt_multiple_safe(text: str) -> tuple[list[DTNode], list[DTParseError]]:
    """Parse device tree source into multiple ASTs with error handling.

    Args:
        text: Device tree source

    Returns:
        Tuple of (list of root_nodes, errors)
    """
    try:
        tokens = tokenize_dt(text)
        parser = DTParser(tokens)
        roots = parser.parse_multiple()
        return roots, parser.errors
    except Exception as e:
        error = DTParseError(f"Parsing failed: {e}")
        return [], [error]


# Lark-based parser integration
def parse_dt_lark(text: str) -> list[DTNode]:
    """Parse device tree source using Lark grammar-based parser.

    Args:
        text: Device tree source

    Returns:
        List of root DTNodes

    Raises:
        Exception: If parsing fails
    """
    from .lark_dt_parser import parse_dt_lark

    return parse_dt_lark(text)


def parse_dt_lark_safe(text: str) -> tuple[list[DTNode], list[str]]:
    """Parse device tree source using Lark parser with error handling.

    Args:
        text: Device tree source

    Returns:
        Tuple of (list of root_nodes, error_messages)
    """
    from .lark_dt_parser import parse_dt_lark_safe

    return parse_dt_lark_safe(text)
