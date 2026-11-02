

import random
import requests

from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Query
from urllib.parse import urlparse, parse_qs, unquote

app = FastAPI(
    title="Google Search Scraper API",
    description="A simple Google search results scraper",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.6 Safari/605.1.15"
]


def extract_google_url(href):
    if not href:
        return None

    if href.startswith("/url?"):
        params = parse_qs(urlparse(href).query)
        href = params.get("q", params.get("url", [None]))[0]

    if not href:
        return None

    href = unquote(href)
    parsed = urlparse(href)

    if parsed.scheme not in ("http", "https"):
        return None

    if parsed.netloc.endswith("google.com"):
        return None

    return href


@app.get("/search")
def search(
    query: str = Query(..., min_length=1, max_length=300)
):
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        response = requests.get(
            "https://www.google.com/search",
            params={"q": query, "num": 10, "hl": "en"},
            headers=headers,
            timeout=15
        )

        print("GOOGLE STATUS:", response.status_code)

        if response.status_code in (403, 429):
            raise HTTPException(
                status_code=503,
                detail="Google temporarily restricted this request."
            )

        response.raise_for_status()

    except requests.RequestException:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to Google Search."
        )

    soup = BeautifulSoup(response.text, "html.parser")

    print("GOOGLE PAGE TITLE:", soup.title.get_text() if soup.title else "NO TITLE")
    print("GOOGLE HTML LENGTH:", len(response.text))
    print("GOOGLE CAPTCHA:", "captcha" in response.text.lower())

    page_text = soup.get_text(" ", strip=True).lower()

    if "unusual traffic" in page_text or "captcha" in page_text:
        raise HTTPException(
            status_code=503,
            detail="Google returned a CAPTCHA or anti-bot page."
        )

    results = []
    seen_urls = set()

    for heading in soup.select("h3"):
        title = heading.get_text(" ", strip=True)
        link = heading.find_parent("a")

        if not link:
            continue

        url = extract_google_url(link.get("href"))

        if not url or url in seen_urls:
            continue

        seen_urls.add(url)
        results.append({"title": title, "url": url})

        if len(results) == 10:
            break

    return {
        "success": True,
        "query": query,
        "total_results": len(results),
        "results": results
    }

