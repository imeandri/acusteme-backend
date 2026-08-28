import unittest

from wikijs_graphql import (
    WikiJsClient,
    WikiJsGraphQLError,
    WikiJsMutationError,
    WikiJsVerificationError,
    WikiPage,
    WikiPageDraft,
)


def page_data(**overrides):
    values = {
        "id": 507,
        "path": "docs/canary",
        "title": "Canary",
        "content": "<p>managed</p>",
        "locale": "it",
        "description": "Test",
        "editor": "code",
        "isPrivate": False,
        "isPublished": True,
        "publishStartDate": None,
        "publishEndDate": None,
        "tags": [{"tag": "sync"}, {"tag": "canary"}],
        "scriptCss": "",
        "scriptJs": "",
        "contentType": "html",
        "updatedAt": "2026-08-28T10:00:00.000Z",
    }
    values.update(overrides)
    return values


def read_response(**overrides):
    return {"data": {"pages": {"singleByPath": page_data(**overrides)}}}


def date_response(start=None, end=None, errors=None):
    response = {
        "data": {
            "pages": {
                "start": {"publishStartDate": start},
                "end": {"publishEndDate": end},
            }
        }
    }
    if errors:
        response["errors"] = errors
    return response


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, query, variables):
        self.calls.append((query, dict(variables)))
        if not self.responses:
            raise AssertionError("Unexpected GraphQL call")
        return self.responses.pop(0)


class WikiJsGraphQLTests(unittest.TestCase):
    def client(self, transport):
        return WikiJsClient("https://wiki.example/graphql", "secret", transport=transport)

    def test_reads_complete_page(self):
        transport = FakeTransport(
            read_response(),
            date_response(start="2026-08-28T10:00:00.000Z"),
        )
        page = self.client(transport).get_page("docs/canary", "it")

        self.assertEqual(page.id, 507)
        self.assertEqual(page.tags, ("sync", "canary"))
        self.assertEqual(page.content_type, "html")
        self.assertEqual(page.publish_start_date, "2026-08-28T10:00:00.000Z")
        self.assertIn("singleByPath", transport.calls[0][0])
        self.assertEqual(transport.calls[0][1], {"path": "docs/canary", "locale": "it"})

    def test_missing_page_is_none_but_other_errors_raise(self):
        missing = FakeTransport(
            {
                "data": {"pages": {"singleByPath": None}},
                "errors": [{"message": "This page does not exist."}],
            }
        )
        self.assertIsNone(self.client(missing).get_page("missing", "it"))

        denied = FakeTransport(
            {"data": {"pages": {"singleByPath": None}}, "errors": [{"message": "Forbidden"}]}
        )
        with self.assertRaises(WikiJsGraphQLError):
            self.client(denied).get_page("secret", "it")

    def test_create_preflights_and_verifies_readback(self):
        draft = WikiPageDraft(
            path="docs/canary",
            title="Canary",
            content="<p>managed</p>",
            locale="it",
            description="Test",
            tags=("sync", "canary"),
        )
        transport = FakeTransport(
            {"data": {"pages": {"singleByPath": None}}},
            {
                "data": {
                    "pages": {
                        "create": {
                            "responseResult": {"succeeded": True, "message": None}
                        }
                    }
                }
            },
            read_response(),
            date_response(start="", end=""),
        )

        outcome = self.client(transport).create_page(draft)

        self.assertEqual(outcome.page.id, 507)
        mutation, variables = transport.calls[1]
        self.assertIn("responseResult", mutation)
        self.assertNotIn("page {", mutation)
        self.assertEqual(variables["tags"], ["sync", "canary"])
        self.assertEqual(len(transport.calls), 4)

    def test_create_refuses_existing_page_without_mutation(self):
        transport = FakeTransport(read_response(), date_response())
        draft = WikiPageDraft(
            path="docs/canary",
            title="Canary",
            content="<p>managed</p>",
            locale="it",
        )

        with self.assertRaises(WikiJsMutationError):
            self.client(transport).create_page(draft)
        self.assertEqual(len(transport.calls), 2)

    def test_update_sends_full_metadata_and_verifies(self):
        expected = WikiPage(
            id=507,
            path="docs/canary",
            title="Canary",
            content="<p>managed</p>",
            locale="it",
            description="Test",
            tags=("sync", "canary"),
            content_type="html",
        )
        transport = FakeTransport(
            {
                "data": {
                    "pages": {
                        "update": {
                            "responseResult": {"succeeded": True, "message": None}
                        }
                    }
                }
            },
            read_response(),
            date_response(),
        )

        self.client(transport).update_page(expected)

        mutation, variables = transport.calls[0]
        self.assertIn("responseResult", mutation)
        self.assertNotIn("page {", mutation)
        self.assertEqual(variables["id"], 507)
        self.assertEqual(variables["tags"], ["sync", "canary"])
        self.assertIn("scriptCss", variables)
        self.assertIn("publishStartDate", variables)

    def test_committed_write_survives_mutation_response_anomaly(self):
        expected = WikiPage(
            id=507,
            path="docs/canary",
            title="Canary",
            content="<p>managed</p>",
            locale="it",
            description="Test",
            tags=("sync", "canary"),
        )
        transport = FakeTransport(
            {
                "data": {"pages": {"update": {"responseResult": None}}},
                "errors": [{"message": "Cannot return null for non-nullable field Page.locale."}],
            },
            read_response(),
            date_response(),
        )

        outcome = self.client(transport).update_page(expected)

        self.assertEqual(len(outcome.response_anomalies), 2)
        self.assertIn("non-nullable", outcome.response_anomalies[0])

    def test_readback_mismatch_fails_without_retry(self):
        expected = WikiPage(
            id=507,
            path="docs/canary",
            title="Canary",
            content="<p>new</p>",
            locale="it",
        )
        transport = FakeTransport(
            {
                "data": {
                    "pages": {
                        "update": {
                            "responseResult": {"succeeded": True, "message": None}
                        }
                    }
                }
            },
            read_response(content="<p>old</p>", description="", tags=[]),
            date_response(),
        )

        with self.assertRaises(WikiJsVerificationError) as raised:
            self.client(transport).update_page(expected)

        self.assertIn("content", raised.exception.mismatches)
        self.assertEqual(len(transport.calls), 3)

    def test_known_empty_date_serialization_error_is_isolated(self):
        transport = FakeTransport(
            read_response(),
            {
                "data": {
                    "pages": {
                        "start": None,
                        "end": {"publishEndDate": "2027-01-01T00:00:00.000Z"},
                    }
                },
                "errors": [
                    {
                        "message": "Cannot return null for non-nullable field Page.publishStartDate.",
                        "path": ["pages", "start", "publishStartDate"],
                    }
                ],
            },
        )

        page = self.client(transport).get_page("docs/canary", "it")

        self.assertIsNone(page.publish_start_date)
        self.assertEqual(page.publish_end_date, "2027-01-01T00:00:00.000Z")


if __name__ == "__main__":
    unittest.main()
