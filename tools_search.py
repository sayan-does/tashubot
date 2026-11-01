from ddgs import DDGS


def web_search(query: str, max_results: int = 5):
    """Search the web using DuckDuckGo. Free, no API key needed."""
    try:
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return []
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except Exception as e:
        return [{"snippet": f"No web search results or search unavailable: {e}"}]
