"""Public web search and the initial search → fetch → store workflow."""
from ddgs import DDGS
from storage.bucket import store
from browser.automation import fetch_page


def web_search(query: str, max_results: int = 5) -> list[dict]:
    query = (query or "").strip()
    if not query:
        raise ValueError("query is required")
    count = max(1, min(int(max_results), 10))
    with DDGS() as ddgs:
        raw_results = list(ddgs.text(query, max_results=count))
    results = []
    for item in raw_results:
        url = item.get("href") or item.get("url")
        if not url:
            continue
        results.append({
            "title": item.get("title", ""),
            "url": url,
            "snippet": item.get("body", item.get("snippet", "")),
        })
    store.log_task("web_search", {"query": query, "max_results": count}, {
        "count": len(results), "urls": [item["url"] for item in results]
    })
    return results


def search_and_fetch(query: str, max_results: int = 5, fetch_top: int = 3) -> dict:
    try:
        results = web_search(query, max_results)
        saved, errors = [], []
        fetch_count = max(0, min(int(fetch_top), 5))
        for result in results[:fetch_count]:
            try:
                document = fetch_page(result["url"], save=True, source_query=query)
                saved.append({key: document.get(key) for key in (
                    "document_id", "title", "url", "final_url", "snippet", "content_length", "fetched_at"
                )})
            except Exception as exc:
                errors.append({"url": result["url"], "error": str(exc)[:500]})
        store.log_task("search_and_fetch", {
            "query": query, "max_results": max_results, "fetch_top": fetch_count
        }, {"saved_count": len(saved), "failed_count": len(errors)})
        return {
            "ok": True,
            "query": query,
            "search_results": results,
            "saved_documents": saved,
            "errors": errors,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:1000], "search_results": [], "saved_documents": [], "errors": []}
