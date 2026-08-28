import unittest

from sparql_query_tools import neutralize_placeholder_regexes


class NeutralizePlaceholderRegexesTests(unittest.TestCase):
    def test_preserves_closing_brace_on_same_line(self):
        query = 'OPTIONAL { FILTER(REGEX(?value, "***PLACEHOLDER***", "i"))}'

        self.assertEqual(
            neutralize_placeholder_regexes(query),
            "OPTIONAL { FILTER(true)}",
        )

    def test_preserves_multiline_filter_structure(self):
        query = """FILTER (
  REGEX(?hs, "***PLACEHOLDER***", "i") ||
  REGEX(?label, "***PLACEHOLDER***")
)"""

        self.assertEqual(
            neutralize_placeholder_regexes(query),
            """FILTER (
  true ||
  true
)""",
        )

    def test_handles_nested_parentheses_and_hash_in_string(self):
        query = (
            'FILTER(REGEX(CONCAT(?value, "ter#", STR(?other)), '
            '"^(***PLACEHOLDER***)", "i")) }'
        )

        self.assertEqual(neutralize_placeholder_regexes(query), "FILTER(true) }")

    def test_is_case_insensitive_for_regex_keyword(self):
        query = 'FILTER(regex(?value, "***PLACEHOLDER***", "i"))'

        self.assertEqual(neutralize_placeholder_regexes(query), "FILTER(true)")

    def test_leaves_comments_and_string_literals_untouched(self):
        query = """# FILTER(REGEX(?value, "***PLACEHOLDER***"))
BIND("REGEX(?value, ***PLACEHOLDER***)" AS ?display)
FILTER(REGEX(?value, "fixed", "i"))"""

        self.assertEqual(neutralize_placeholder_regexes(query), query)

    def test_leaves_other_placeholder_constructs_untouched(self):
        query = 'FILTER(CONTAINS(LCASE(?value), "***PLACEHOLDER***"))'

        self.assertEqual(neutralize_placeholder_regexes(query), query)

    def test_leaves_unbalanced_regex_untouched(self):
        query = 'FILTER(REGEX(?value, "***PLACEHOLDER***"'

        self.assertEqual(neutralize_placeholder_regexes(query), query)

    def test_does_not_treat_less_than_as_an_iri(self):
        query = (
            'FILTER(?low<5&&REGEX(?value, "***PLACEHOLDER***", "i")'
            '&&?high>2)'
        )

        self.assertEqual(
            neutralize_placeholder_regexes(query),
            "FILTER(?low<5&&true&&?high>2)",
        )


if __name__ == "__main__":
    unittest.main()
