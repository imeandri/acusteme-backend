"""Utilities for building runnable SPARQL queries for the documentation."""


_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-"
)


def _is_name_char(character):
    return character in _NAME_CHARS


def _skip_whitespace_and_comments(text, start):
    position = start
    length = len(text)

    while position < length:
        if text[position].isspace():
            position += 1
            continue
        if text[position] == "#":
            newline = text.find("\n", position)
            if newline == -1:
                return length
            position = newline + 1
            continue
        break

    return position


def _quoted_string_end(text, start):
    quote = text[start]
    delimiter = quote * 3 if text.startswith(quote * 3, start) else quote
    position = start + len(delimiter)
    length = len(text)

    while position < length:
        if text[position] == "\\":
            position += 2
            continue
        if text.startswith(delimiter, position):
            return position + len(delimiter)
        position += 1

    return length


def _iri_end(text, start):
    position = start + 1
    length = len(text)

    if position >= length:
        return None
    if text[position] != ">" and text[position] in "?$0123456789+-=!&|*()":
        return None

    while position < length:
        if text[position] == ">":
            return position + 1
        if text[position].isspace():
            return None
        position += 1

    return None


def _placeholder_outside_comments(text):
    position = 0
    length = len(text)

    while position < length:
        if text[position] == "#":
            newline = text.find("\n", position)
            if newline == -1:
                return False
            position = newline + 1
            continue
        if text.startswith("PLACEHOLDER", position):
            return True
        if text[position] in {'"', "'"}:
            end = _quoted_string_end(text, position)
            if "PLACEHOLDER" in text[position:end]:
                return True
            position = end
            continue
        if text[position] == "<":
            end = _iri_end(text, position)
            if end is not None:
                if "PLACEHOLDER" in text[position:end]:
                    return True
                position = end
                continue
        position += 1

    return False


def _parenthesized_call_end(text, opening):
    depth = 0
    position = opening
    length = len(text)

    while position < length:
        character = text[position]
        if character == "#":
            newline = text.find("\n", position)
            if newline == -1:
                return None
            position = newline + 1
            continue
        if character in {'"', "'"}:
            position = _quoted_string_end(text, position)
            continue
        if character == "<":
            iri_end = _iri_end(text, position)
            if iri_end is not None:
                position = iri_end
                continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return position + 1
        position += 1

    return None


def neutralize_placeholder_regexes(query):
    """Replace complete REGEX calls containing PLACEHOLDER with ``true``.

    Replacing the boolean expression, rather than commenting its physical line,
    preserves surrounding FILTER expressions, operators, braces, and newlines.
    Text inside SPARQL comments, quoted strings, and IRI references is skipped
    while looking for REGEX function calls.
    """

    parts = []
    copied_until = 0
    position = 0
    length = len(query)

    while position < length:
        character = query[position]
        if character == "#":
            newline = query.find("\n", position)
            position = length if newline == -1 else newline + 1
            continue
        if character in {'"', "'"}:
            position = _quoted_string_end(query, position)
            continue
        if character == "<":
            iri_end = _iri_end(query, position)
            if iri_end is not None:
                position = iri_end
                continue

        if query[position : position + 5].upper() != "REGEX":
            position += 1
            continue

        before = query[position - 1] if position else ""
        after_position = position + 5
        after = query[after_position] if after_position < length else ""
        if (before and _is_name_char(before)) or (after and _is_name_char(after)):
            position += 1
            continue

        opening = _skip_whitespace_and_comments(query, after_position)
        if opening >= length or query[opening] != "(":
            position += 5
            continue

        call_end = _parenthesized_call_end(query, opening)
        if call_end is None:
            position += 5
            continue

        if _placeholder_outside_comments(query[position:call_end]):
            parts.append(query[copied_until:position])
            parts.append("true")
            copied_until = call_end

        position = call_end

    if not parts:
        return query

    parts.append(query[copied_until:])
    return "".join(parts)


def comment_regex_placeholders(query):
    """Backward-compatible alias for the former line-commenting helper."""

    return neutralize_placeholder_regexes(query)
