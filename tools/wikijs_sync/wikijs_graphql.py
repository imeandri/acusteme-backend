"""Small, defensive Wiki.js 2 GraphQL adapter for ACUSTEME synchronization.

Mutations deliberately request only ``responseResult``.  Wiki.js can commit a
write and then fail while resolving fields of the returned page; every write
is therefore followed by an independent read and exact verification.  The
adapter never retries a mutation automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


Transport = Callable[[str, Mapping[str, object]], Mapping[str, object]]


class WikiJsError(RuntimeError):
    pass


class WikiJsTransportError(WikiJsError):
    pass


class WikiJsGraphQLError(WikiJsError):
    def __init__(self, messages: Sequence[str]):
        self.messages = tuple(messages)
        super().__init__("; ".join(self.messages))


class WikiJsMutationError(WikiJsError):
    pass


class WikiJsVerificationError(WikiJsError):
    def __init__(self, message: str, mismatches: Sequence[str] = ()):
        self.mismatches = tuple(mismatches)
        suffix = f" ({'; '.join(self.mismatches)})" if self.mismatches else ""
        super().__init__(message + suffix)


@dataclass(frozen=True)
class WikiPageDraft:
    path: str
    title: str
    content: str
    locale: str
    description: str = ""
    editor: str = "code"
    is_private: bool = False
    is_published: bool = True
    publish_start_date: str | None = None
    publish_end_date: str | None = None
    tags: tuple[str, ...] = ()
    script_css: str = ""
    script_js: str = ""


@dataclass(frozen=True)
class WikiPage(WikiPageDraft):
    id: int = 0
    content_type: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class MutationOutcome:
    page: WikiPage
    response_result: Mapping[str, object] | None
    response_anomalies: tuple[str, ...] = ()


PAGE_FIELDS = """
id
path
title
description
isPrivate
isPublished
tags { tag }
content
editor
locale
scriptCss
scriptJs
contentType
updatedAt
"""


READ_PAGE_QUERY = f"""
query AcustemeReadPage($path: String!, $locale: String!) {{
  pages {{
    singleByPath(path: $path, locale: $locale) {{
      {PAGE_FIELDS}
    }}
  }}
}}
"""


# Wiki.js 2 declares both publication dates as non-null even though unscheduled
# pages store empty values.  Keeping them in the main query can null the whole
# page.  Two aliases isolate each field so a broken empty date cannot hide the
# other date or any of the core page data.
READ_PAGE_DATES_QUERY = """
query AcustemeReadPageDates($path: String!, $locale: String!) {
  pages {
    start: singleByPath(path: $path, locale: $locale) { publishStartDate }
    end: singleByPath(path: $path, locale: $locale) { publishEndDate }
  }
}
"""


SYSTEM_VERSION_QUERY = """
query AcustemeSystemVersion {
  system { info { currentVersion latestVersion } }
}
"""


CREATE_PAGE_MUTATION = """
mutation AcustemeCreatePage(
  $content: String!, $description: String!, $editor: String!,
  $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!,
  $path: String!, $publishEndDate: Date, $publishStartDate: Date,
  $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!
) {
  pages {
    create(
      content: $content, description: $description, editor: $editor,
      isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale,
      path: $path, publishEndDate: $publishEndDate,
      publishStartDate: $publishStartDate, scriptCss: $scriptCss,
      scriptJs: $scriptJs, tags: $tags, title: $title
    ) {
      responseResult { succeeded message }
    }
  }
}
"""


UPDATE_PAGE_MUTATION = """
mutation AcustemeUpdatePage(
  $id: Int!, $content: String!, $description: String!, $editor: String!,
  $isPrivate: Boolean!, $isPublished: Boolean!, $locale: String!,
  $path: String!, $publishEndDate: Date, $publishStartDate: Date,
  $scriptCss: String, $scriptJs: String, $tags: [String]!, $title: String!
) {
  pages {
    update(
      id: $id, content: $content, description: $description, editor: $editor,
      isPrivate: $isPrivate, isPublished: $isPublished, locale: $locale,
      path: $path, publishEndDate: $publishEndDate,
      publishStartDate: $publishStartDate, scriptCss: $scriptCss,
      scriptJs: $scriptJs, tags: $tags, title: $title
    ) {
      responseResult { succeeded message }
    }
  }
}
"""


def _error_messages(payload: Mapping[str, object]) -> tuple[str, ...]:
    messages = []
    for error in payload.get("errors", []) or []:
        if isinstance(error, Mapping):
            messages.append(str(error.get("message", "Unknown GraphQL error")))
        else:
            messages.append(str(error))
    return tuple(messages)


def _page_variables(page: WikiPageDraft) -> dict[str, object]:
    return {
        "content": page.content,
        "description": page.description,
        "editor": page.editor,
        "isPrivate": page.is_private,
        "isPublished": page.is_published,
        "locale": page.locale,
        "path": page.path,
        "publishEndDate": page.publish_end_date,
        "publishStartDate": page.publish_start_date,
        "scriptCss": page.script_css,
        "scriptJs": page.script_js,
        "tags": list(page.tags),
        "title": page.title,
    }


def _parse_page(raw: Mapping[str, object]) -> WikiPage:
    raw_tags = raw.get("tags") or ()
    tags = tuple(
        str(tag.get("tag")) if isinstance(tag, Mapping) else str(tag)
        for tag in raw_tags
    )
    return WikiPage(
        id=int(raw["id"]),
        path=str(raw["path"]),
        title=str(raw["title"]),
        content=str(raw["content"]),
        locale=str(raw["locale"]),
        description=str(raw.get("description") or ""),
        editor=str(raw.get("editor") or ""),
        is_private=bool(raw.get("isPrivate")),
        is_published=bool(raw.get("isPublished")),
        publish_start_date=raw.get("publishStartDate"),
        publish_end_date=raw.get("publishEndDate"),
        tags=tags,
        script_css=str(raw.get("scriptCss") or ""),
        script_js=str(raw.get("scriptJs") or ""),
        content_type=raw.get("contentType"),
        updated_at=raw.get("updatedAt"),
    )


def verification_mismatches(
    expected: WikiPageDraft,
    actual: WikiPage,
) -> tuple[str, ...]:
    fields = (
        "path",
        "title",
        "content",
        "locale",
        "description",
        "editor",
        "is_private",
        "is_published",
        "publish_start_date",
        "publish_end_date",
        "tags",
        "script_css",
        "script_js",
    )
    mismatches = []
    for field in fields:
        expected_value = getattr(expected, field)
        actual_value = getattr(actual, field)
        if field in {"publish_start_date", "publish_end_date"}:
            # Wiki.js stores an omitted scheduling date as an empty string and
            # returns it that way even when GraphQL received null.
            expected_value = expected_value or ""
            actual_value = actual_value or ""
        if expected_value != actual_value:
            mismatches.append(field)
    return tuple(mismatches)


class WikiJsClient:
    def __init__(
        self,
        endpoint: str,
        token: str,
        timeout: float = 30,
        transport: Transport | None = None,
    ):
        if not endpoint.startswith(("https://", "http://")):
            raise ValueError("Wiki.js endpoint must be an HTTP(S) URL.")
        if not token:
            raise ValueError("Wiki.js API token is required.")
        normalized_endpoint = endpoint.rstrip("/")
        self.endpoint = (
            normalized_endpoint
            if normalized_endpoint.endswith("/graphql")
            else normalized_endpoint + "/graphql"
        )
        self._token = token
        self.timeout = timeout
        self._transport = transport or self._http_transport

    def _http_transport(
        self,
        query: str,
        variables: Mapping[str, object],
    ) -> Mapping[str, object]:
        body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
        request = Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "ACUSTEME-WikiJS-Synchronizer/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            raise WikiJsTransportError(f"Wiki.js returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise WikiJsTransportError(f"Cannot reach Wiki.js: {exc.reason}.") from exc

        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WikiJsTransportError("Wiki.js returned invalid JSON.") from exc
        if not isinstance(payload, Mapping):
            raise WikiJsTransportError("Wiki.js returned an unexpected JSON value.")
        return payload

    def _request(
        self,
        query: str,
        variables: Mapping[str, object] | None = None,
        *,
        allow_graphql_errors: bool = False,
    ) -> Mapping[str, object]:
        try:
            payload = self._transport(query, variables or {})
        except WikiJsError:
            raise
        except Exception as exc:
            raise WikiJsTransportError("Wiki.js transport failed.") from exc
        if not isinstance(payload, Mapping):
            raise WikiJsTransportError("Wiki.js transport returned an invalid payload.")
        errors = _error_messages(payload)
        if errors and not allow_graphql_errors:
            raise WikiJsGraphQLError(errors)
        return payload

    def get_system_version(self) -> Mapping[str, object]:
        payload = self._request(SYSTEM_VERSION_QUERY)
        try:
            return payload["data"]["system"]["info"]
        except (KeyError, TypeError) as exc:
            raise WikiJsTransportError("Wiki.js version response is incomplete.") from exc

    def get_page(self, path: str, locale: str) -> WikiPage | None:
        payload = self._request(
            READ_PAGE_QUERY,
            {"path": path, "locale": locale},
            allow_graphql_errors=True,
        )
        errors = _error_messages(payload)
        try:
            raw_page = payload.get("data", {}).get("pages", {}).get("singleByPath")
        except AttributeError as exc:
            raise WikiJsTransportError("Wiki.js page response is incomplete.") from exc

        if raw_page is None and (
            not errors
            or all(
                "does not exist" in message.lower() or "not found" in message.lower()
                for message in errors
            )
        ):
            return None
        if errors:
            raise WikiJsGraphQLError(errors)
        if not isinstance(raw_page, Mapping):
            raise WikiJsTransportError("Wiki.js page response is incomplete.")
        try:
            page = _parse_page(raw_page)
        except (KeyError, TypeError, ValueError) as exc:
            raise WikiJsTransportError("Wiki.js page fields are incomplete.") from exc
        publish_start_date, publish_end_date = self._get_publish_dates(path, locale)
        return replace(
            page,
            publish_start_date=publish_start_date,
            publish_end_date=publish_end_date,
        )

    def _get_publish_dates(
        self,
        path: str,
        locale: str,
    ) -> tuple[str | None, str | None]:
        payload = self._request(
            READ_PAGE_DATES_QUERY,
            {"path": path, "locale": locale},
            allow_graphql_errors=True,
        )
        unexpected = []
        for error in payload.get("errors", []) or []:
            if not isinstance(error, Mapping):
                unexpected.append(str(error))
                continue
            error_path = error.get("path") or ()
            if not error_path or error_path[-1] not in {
                "publishStartDate",
                "publishEndDate",
            }:
                unexpected.append(str(error.get("message", "Unknown GraphQL error")))
        if unexpected:
            raise WikiJsGraphQLError(unexpected)

        try:
            pages = payload.get("data", {}).get("pages", {})
            start_page = pages.get("start")
            end_page = pages.get("end")
        except AttributeError as exc:
            raise WikiJsTransportError("Wiki.js publication-date response is incomplete.") from exc
        start = start_page.get("publishStartDate") if isinstance(start_page, Mapping) else None
        end = end_page.get("publishEndDate") if isinstance(end_page, Mapping) else None
        return start, end

    def create_page(self, draft: WikiPageDraft) -> MutationOutcome:
        if self.get_page(draft.path, draft.locale) is not None:
            raise WikiJsMutationError(
                f"Refusing to create existing page {draft.locale}:{draft.path}."
            )
        return self._mutate_and_verify(
            CREATE_PAGE_MUTATION,
            _page_variables(draft),
            "create",
            draft,
        )

    def update_page(self, expected: WikiPage) -> MutationOutcome:
        variables = _page_variables(expected)
        variables["id"] = expected.id
        return self._mutate_and_verify(
            UPDATE_PAGE_MUTATION,
            variables,
            "update",
            expected,
        )

    def _mutate_and_verify(
        self,
        mutation: str,
        variables: Mapping[str, object],
        operation: str,
        expected: WikiPageDraft,
    ) -> MutationOutcome:
        payload = self._request(mutation, variables, allow_graphql_errors=True)
        anomalies = list(_error_messages(payload))
        response_result = None
        try:
            candidate = payload.get("data", {}).get("pages", {}).get(operation, {})
            if isinstance(candidate, Mapping):
                response_result = candidate.get("responseResult")
        except AttributeError:
            anomalies.append("Mutation response data is incomplete.")

        if isinstance(response_result, Mapping) and not response_result.get("succeeded", False):
            anomalies.append(
                "Mutation response reported failure: "
                + str(response_result.get("message") or response_result.get("errorCode") or "unknown")
            )
        elif response_result is None:
            anomalies.append("Mutation responseResult is missing.")

        actual = self.get_page(expected.path, expected.locale)
        if actual is None:
            raise WikiJsVerificationError(
                f"Wiki.js {operation} could not be verified: page is absent.",
                anomalies,
            )
        mismatches = verification_mismatches(expected, actual)
        if mismatches:
            raise WikiJsVerificationError(
                f"Wiki.js {operation} read-back differs from the requested page.",
                tuple(anomalies) + mismatches,
            )
        return MutationOutcome(
            page=actual,
            response_result=response_result,
            response_anomalies=tuple(anomalies),
        )
