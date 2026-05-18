"""Anthropic direct response citation extraction."""

from citationpulse.services.direct_llm import _extract_anthropic_message_citations


def test_extract_web_search_tool_result_urls():
    payload = {
        "content": [
            {
                "type": "web_search_tool_result",
                "content": [
                    {
                        "type": "web_search_result",
                        "url": "https://competitor.example/",
                        "title": "Competitor",
                    }
                ],
            },
            {"type": "text", "text": "See also https://brand.example/page"},
        ]
    }
    cites = _extract_anthropic_message_citations(payload, "")
    urls = {c.url for c in cites}
    assert "https://competitor.example/" in urls
    assert "https://brand.example/page" in urls
