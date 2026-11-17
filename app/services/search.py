from langchain_tavily import TavilySearch

_tool: TavilySearch | None = None


def _get_tool() -> TavilySearch:
    global _tool
    if _tool is None:
        _tool = TavilySearch(
            max_results=5,
            topic="news",
            search_depth="basic",
            include_answer=False,
            include_raw_content=False,
        )
    return _tool


def search(query: str, recency: str = "week", topic: str = "news") -> dict:
    raw = _get_tool().invoke({"query": query, "time_range": recency, "topic": topic})
    if isinstance(raw, str):
        return {"query": query, "results": [], "raw": raw[:1500]}
    if not isinstance(raw, dict):
        return {"query": query, "results": []}
    if raw.get("error"):
        return {"query": query, "results": [], "error": str(raw["error"])[:200]}

    results = []
    for r in (raw.get("results") or [])[:5]:
        results.append({
            "title": r.get("title"),
            "url": r.get("url"),
            "published": r.get("published_date"),
            "snippet": (r.get("content") or "")[:400],
        })
    return {"query": query, "recency": recency, "topic": topic, "count": len(results), "results": results}