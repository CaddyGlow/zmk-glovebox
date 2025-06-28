"""Recursive descent parser for device tree source files."""

import logging
from typing import Any

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
        self.pos = 0
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

    def _parse_root_node(self) -> DTNode:
        """Parse the root device tree node.

        Returns:
            Root DTNode
        """
        root = DTNode("", line=self._current_line(), column=self._current_column())

        # Handle preprocessor directives and comments at top level
        root.comments.extend(self.comments)
        self.comments = []

        # Expect root node structure: / { ... };
        if self._match(TokenType.SLASH):
            self._advance()  # consume /
            if self._match(TokenType.LBRACE):
                self._advance()  # consume {
                self._parse_node_body(root)
                self._expect(TokenType.RBRACE)
                self._expect(TokenType.SEMICOLON)
            else:
                self._error("Expected '{' after '/'")
        else:
            # Handle nodes without explicit root
            self._parse_node_body(root)

        return root

    def _parse_node_body(self, node: DTNode) -> None:
        """Parse the body of a device tree node.

        Args:
            node: Node to populate with properties and children
        """
        while not self._match(TokenType.RBRACE) and not self._is_at_end():
            # Skip comments and preprocessor directives
            if self._consume_comments_and_preprocessor():
                continue

            # Try to parse property or child node
            try:
                if self._is_property():
                    prop = self._parse_property()
                    if prop:
                        node.add_property(prop)
                else:
                    child = self._parse_child_node()
                    if child:
                        node.add_child(child)
            except Exception as e:
                self._error(f"Failed to parse node body: {e}")
                self._synchronize()

    def _parse_property(self) -> DTProperty | None:
        """Parse a device tree property.

        Returns:
            Parsed DTProperty or None if parsing fails
        """
        if not self._match(TokenType.IDENTIFIER):
            return None

        prop_name = self.current_token.value
        line = self._current_line()
        column = self._current_column()
        self._advance()

        # Handle boolean properties (no value)
        if self._match(TokenType.SEMICOLON):
            self._advance()
            return DTProperty(prop_name, DTValue.boolean(True), line, column)

        # Handle properties with values
        if self._match(TokenType.EQUALS):
            self._advance()
            value = self._parse_property_value()
            self._expect(TokenType.SEMICOLON)
            return DTProperty(prop_name, value, line, column)

        self._error("Expected '=' or ';' after property name")
        return None

    def _parse_property_value(self) -> DTValue:
        """Parse a property value.

        Returns:
            Parsed DTValue
        """
        if self._match(TokenType.STRING):
            value = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            return DTValue.string(value, raw)

        elif self._match(TokenType.NUMBER):
            value_str = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            try:
                # Handle hex numbers
                if value_str.startswith("0x"):
                    value = int(value_str, 16)
                else:
                    value = int(value_str)
                return DTValue.integer(value, raw)
            except ValueError:
                self._error(f"Invalid number: {value_str}")
                return DTValue.string(value_str, raw)

        elif self._match(TokenType.REFERENCE):
            ref = self.current_token.value
            raw = self.current_token.raw
            self._advance()
            return DTValue.reference(ref, raw)

        elif self._match(TokenType.ANGLE_OPEN):
            return self._parse_array_value()

        elif self._match(TokenType.IDENTIFIER):
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

        values = []
        raw_parts = ["<"]

        while not self._match(TokenType.ANGLE_CLOSE) and not self._is_at_end():
            if self._match(TokenType.NUMBER):
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
                ref = self.current_token.raw
                raw_parts.append(ref)
                values.append(ref)
                self._advance()

            elif self._match(TokenType.IDENTIFIER):
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

        # Check for label (identifier followed by colon)
        if self._match(TokenType.IDENTIFIER):
            first_ident = self.current_token.value
            self._advance()

            if self._match(TokenType.COLON):
                # This is a label
                label = first_ident
                self._advance()  # consume :

                # Parse the actual node name
                if self._match(TokenType.IDENTIFIER):
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
                if self._match(TokenType.IDENTIFIER) or self._match(TokenType.NUMBER):
                    unit_address = self.current_token.value
                    self._advance()
                else:
                    self._error("Expected unit address after '@'")

        else:
            self._error("Expected node name")
            return None

        # Parse node body
        if self._match(TokenType.LBRACE):
            self._advance()  # consume {
            node = DTNode(name, label, unit_address, line, column)
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
        if not self._match(TokenType.IDENTIFIER):
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

        while self._match(TokenType.COMMENT) or self._match(TokenType.PREPROCESSOR):
            if self._match(TokenType.COMMENT):
                comment_text = self.current_token.value
                line = self._current_line()
                column = self._current_column()
                is_block = comment_text.startswith("/*")
                comment = DTComment(comment_text, line, column, is_block)
                self.comments.append(comment)
                consumed = True
                self._advance()

            elif self._match(TokenType.PREPROCESSOR):
                directive_text = self.current_token.value
                line = self._current_line()
                column = self._current_column()

                # Parse preprocessor directive
                parts = directive_text.split(None, 1)
                directive = parts[0][1:]  # Remove #
                condition = parts[1] if len(parts) > 1 else ""

                conditional = DTConditional(directive, condition, line, column)
                # Store in current comments for now
                # TODO: Properly handle conditional compilation
                consumed = True
                self._advance()

        return consumed

    def _match(self, token_type: TokenType) -> bool:
        """Check if current token matches given type.

        Args:
            token_type: Type to match

        Returns:
            True if current token matches
        """
        return not self._is_at_end() and self.current_token.type == token_type

    def _advance(self) -> Token | None:
        """Advance to next token.

        Returns:
            Previous token
        """
        previous = self.current_token
        if not self._is_at_end():
            self.pos += 1
            self.current_token = (
                self.tokens[self.pos] if self.pos < len(self.tokens) else None
            )
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
            if self.current_token.type in (TokenType.SEMICOLON, TokenType.RBRACE):
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
