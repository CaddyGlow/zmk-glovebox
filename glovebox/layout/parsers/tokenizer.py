"""Tokenizer for device tree source files."""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class TokenType(Enum):
    """Device tree token types."""

    # Literals
    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"
    REFERENCE = "REFERENCE"  # &symbol

    # Symbols
    LBRACE = "LBRACE"  # {
    RBRACE = "RBRACE"  # }
    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    ANGLE_OPEN = "ANGLE_OPEN"  # <
    ANGLE_CLOSE = "ANGLE_CLOSE"  # >
    SEMICOLON = "SEMICOLON"  # ;
    COMMA = "COMMA"  # ,
    EQUALS = "EQUALS"  # =
    COLON = "COLON"  # :
    SLASH = "SLASH"  # /
    AT = "AT"  # @

    # Special
    COMMENT = "COMMENT"
    PREPROCESSOR = "PREPROCESSOR"  # #include, #define, #ifdef, etc.
    NEWLINE = "NEWLINE"
    WHITESPACE = "WHITESPACE"
    EOF = "EOF"

    # Keywords (for better parsing)
    COMPATIBLE = "COMPATIBLE"


@dataclass
class Token:
    """A single token from device tree source."""

    type: TokenType
    value: str
    line: int
    column: int
    raw: str = ""  # Original text including quotes, etc.

    def __post_init__(self) -> None:
        """Set raw to value if not provided."""
        if not self.raw:
            self.raw = self.value


class DTTokenizer:
    """Tokenizer for device tree source files."""

    # Token patterns
    PATTERNS = [
        # Comments (must come before other patterns)
        (TokenType.COMMENT, r"//.*?(?=\n|$)"),
        (TokenType.COMMENT, r"/\*.*?\*/"),
        # Preprocessor directives
        (TokenType.PREPROCESSOR, r"#\w+.*?(?=\n|$)"),
        # String literals
        (TokenType.STRING, r'"([^"\\]|\\.)*"'),
        # Numbers (hex, decimal)
        (TokenType.NUMBER, r"0x[0-9a-fA-F]+|[0-9]+"),
        # References
        (TokenType.REFERENCE, r"&[a-zA-Z_][a-zA-Z0-9_]*"),
        # Identifiers and keywords
        (TokenType.IDENTIFIER, r"[a-zA-Z_][a-zA-Z0-9_-]*"),
        # Symbols
        (TokenType.LBRACE, r"\{"),
        (TokenType.RBRACE, r"\}"),
        (TokenType.LPAREN, r"\("),
        (TokenType.RPAREN, r"\)"),
        (TokenType.ANGLE_OPEN, r"<"),
        (TokenType.ANGLE_CLOSE, r">"),
        (TokenType.SEMICOLON, r";"),
        (TokenType.COMMA, r","),
        (TokenType.EQUALS, r"="),
        (TokenType.COLON, r":"),
        (TokenType.SLASH, r"/"),
        (TokenType.AT, r"@"),
        # Whitespace and newlines
        (TokenType.NEWLINE, r"\n"),
        (TokenType.WHITESPACE, r"[ \t]+"),
    ]

    def __init__(self, text: str) -> None:
        """Initialize tokenizer.

        Args:
            text: Device tree source text
        """
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

        # Compile patterns for efficiency
        self.compiled_patterns = [
            (token_type, re.compile(pattern)) for token_type, pattern in self.PATTERNS
        ]

    def tokenize(self, preserve_whitespace: bool = False) -> list[Token]:
        """Tokenize the input text.

        Args:
            preserve_whitespace: Whether to preserve whitespace tokens

        Returns:
            List of tokens
        """
        self.tokens = []
        self.pos = 0
        self.line = 1
        self.column = 1

        while self.pos < len(self.text):
            if not self._match_token():
                # Skip unknown character
                char = self.text[self.pos]
                self._advance()
                self._add_token(TokenType.IDENTIFIER, char)

        # Filter out whitespace if not preserving
        if not preserve_whitespace:
            self.tokens = [
                token
                for token in self.tokens
                if token.type not in (TokenType.WHITESPACE, TokenType.NEWLINE)
            ]

        # Add EOF token
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))

        # Post-process for keywords
        self._post_process_keywords()

        return self.tokens

    def _match_token(self) -> bool:
        """Try to match a token at current position.

        Returns:
            True if a token was matched and added
        """
        for token_type, pattern in self.compiled_patterns:
            match = pattern.match(self.text, self.pos)
            if match:
                value = match.group(0)
                self._add_token(token_type, value)
                self._advance(len(value))
                return True
        return False

    def _add_token(self, token_type: TokenType, value: str) -> None:
        """Add a token to the list.

        Args:
            token_type: Type of token
            value: Token value
        """
        token = Token(token_type, value, self.line, self.column, value)

        # Process token value for specific types
        if token_type == TokenType.STRING:
            # Remove quotes and handle escape sequences
            token.value = self._process_string_literal(value)
        elif token_type == TokenType.REFERENCE:
            # Remove & prefix
            token.value = value[1:]
        elif token_type == TokenType.NUMBER:
            # Keep as string for now, will be converted during parsing
            pass

        self.tokens.append(token)

    def _advance(self, count: int = 1) -> None:
        """Advance position and update line/column.

        Args:
            count: Number of characters to advance
        """
        for _ in range(count):
            if self.pos < len(self.text):
                if self.text[self.pos] == "\n":
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1

    def _process_string_literal(self, value: str) -> str:
        """Process string literal, removing quotes and handling escapes.

        Args:
            value: Raw string literal with quotes

        Returns:
            Processed string value
        """
        # Remove surrounding quotes
        content = value[1:-1]

        # Handle escape sequences
        escapes = {
            "\\n": "\n",
            "\\t": "\t",
            "\\r": "\r",
            "\\\\": "\\",
            '\\"': '"',
        }

        for escape, replacement in escapes.items():
            content = content.replace(escape, replacement)

        return content

    def _post_process_keywords(self) -> None:
        """Post-process tokens to identify keywords."""
        keywords = {"compatible": TokenType.COMPATIBLE}

        for token in self.tokens:
            if token.type == TokenType.IDENTIFIER and token.value in keywords:
                token.type = keywords[token.value]


def tokenize_dt(text: str, preserve_whitespace: bool = False) -> list[Token]:
    """Tokenize device tree source text.

    Args:
        text: Device tree source
        preserve_whitespace: Whether to preserve whitespace tokens

    Returns:
        List of tokens
    """
    tokenizer = DTTokenizer(text)
    return tokenizer.tokenize(preserve_whitespace)


def tokens_to_string(tokens: list[Token]) -> str:
    """Convert tokens back to string representation.

    Args:
        tokens: List of tokens

    Returns:
        String representation
    """
    return "".join(token.raw for token in tokens if token.type != TokenType.EOF)
