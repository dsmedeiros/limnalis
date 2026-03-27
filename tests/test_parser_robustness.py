"""Parser robustness tests: verify graceful handling of malformed inputs.

T8: Parser robustness (no crashes, clean errors).
"""

from __future__ import annotations

import pytest

from lark import Tree, UnexpectedInput

from limnalis.parser import LimnalisParser


@pytest.fixture(scope="module")
def parser():
    return LimnalisParser()


class TestParserMalformedInputs:
    """Test that the parser handles malformed inputs gracefully."""

    def test_empty_string(self, parser) -> None:
        """Empty string should raise UnexpectedInput, not crash."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("")

    def test_random_garbage(self, parser) -> None:
        """Random garbage text should raise a clean error."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("!@#$%^&*() ~~~ ??? ///")

    def test_partial_truncated_syntax(self, parser) -> None:
        """Partial/truncated valid syntax should raise a clean error."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("bundle my_bundle {")

    def test_near_valid_syntax_with_typos(self, parser) -> None:
        """Near-valid syntax with typos should raise a clean error."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("bundel my_bundle { claimblock cb1 { } }")

    def test_extremely_deeply_nested_input(self, parser) -> None:
        """Deeply nested invalid input should raise UnexpectedInput, not crash."""
        # Build deeply nested structure using invalid syntax (missing semicolons
        # inside inner blocks makes this unparseable).
        depth = 50
        source = "bundle deep_nest {\n"
        source += "  claim_block cb1 {\n"
        for i in range(depth):
            source += f"    claim c{i} {{ predicate \"test{i}\" }}\n"
        source += "  }\n"
        source += "}\n"

        with pytest.raises(UnexpectedInput):
            parser.parse_text(source)

    def test_deeply_nested_valid_input(self, parser) -> None:
        """Deeply nested but valid input should parse successfully."""
        depth = 50
        source = "bundle deep_nest {\n"
        for i in range(depth):
            source += "  " * (i + 1) + f"level{i} {{\n"
        # Innermost statement
        source += "  " * (depth + 1) + 'leaf "value";\n'
        for i in range(depth - 1, -1, -1):
            source += "  " * (i + 1) + "}\n"
        source += "}\n"

        result = parser.parse_text(source)
        assert isinstance(result, Tree), f"Expected Tree, got {type(result)}"
        assert result.data == "start", f"Expected root node 'start', got '{result.data}'"
        assert len(result.children) > 0, "Parsed tree should have children"

    def test_very_long_input(self, parser) -> None:
        """Very long invalid input should raise UnexpectedInput, not crash."""
        # Generate a very long but syntactically invalid input (missing semicolons
        # inside inner blocks makes this unparseable).
        lines = ["bundle long_bundle {"]
        lines.append("  claim_block cb1 {")
        for i in range(500):
            lines.append(f'    claim c{i} {{ predicate "value_{i}" }}')
        lines.append("  }")
        lines.append("}")
        source = "\n".join(lines)

        with pytest.raises(UnexpectedInput):
            parser.parse_text(source)

    def test_very_long_valid_input(self, parser) -> None:
        """Very long but valid input should parse successfully."""
        lines = ["bundle long_bundle {"]
        lines.append("  section cb1 {")
        for i in range(500):
            lines.append(f'    entry{i} "value_{i}";')
        lines.append("  }")
        lines.append("}")
        source = "\n".join(lines)

        result = parser.parse_text(source)
        assert isinstance(result, Tree), f"Expected Tree, got {type(result)}"
        assert result.data == "start", f"Expected root node 'start', got '{result.data}'"
        assert len(result.children) > 0, "Parsed tree should have children"

    def test_unicode_input(self, parser) -> None:
        """Unicode characters should not crash the parser; must parse or raise UnexpectedInput."""
        unicode_text = "bundle \u00fc\u00f6\u00e4 { }"
        try:
            result = parser.parse_text(unicode_text)
            assert isinstance(result, Tree), f"Expected Tree, got {type(result)}"
            assert result.data == "start", f"Expected root node 'start', got '{result.data}'"
            assert len(result.children) > 0, "Parsed tree should have children"
        except UnexpectedInput:
            pass  # Clean parse error is acceptable

    def test_only_whitespace(self, parser) -> None:
        """Whitespace-only input should raise a clean error."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("   \n\n\t  ")

    def test_missing_closing_brace(self, parser) -> None:
        """Missing closing brace should raise a clean error."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("bundle test_bundle { claim_block cb1 { }")

    def test_extra_closing_brace(self, parser) -> None:
        """Extra closing brace should raise a clean error."""
        with pytest.raises(UnexpectedInput):
            parser.parse_text("bundle test_bundle { } }")
