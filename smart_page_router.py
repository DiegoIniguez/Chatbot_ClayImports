from page_scraper import find_best_shopify_pages, get_full_page_text, summarize_page_content
import os
from utils import get_shopify_pages
from difflib import SequenceMatcher

# For intents with a specific page
DIRECT_PAGE_HANDLES = {
    "contact": "contact-book",
    "studio": "clay-sma-info-contact",
    "book": "book-design-consultation",
    "returns_info": "return-and-cancellation-policy",
    "shipping": "shipping-policy",
    "trade": "trade",
    "our_story": "who-we-are",
}

irrelevant_handles = {
    "wishlist",
    "accessibility-disclaimer",
    "cart",
    "order-status",
    "search",
    "404",
    "gift-card",
    "account",
    "login",
    "register",
}


shopify_store_url = "https://clayimports.myshopify.com"  # public version

TOP_SCORE_MARGIN = 0.025

def search_shopify_pages(query, intent=None):
    pages = get_shopify_pages()
    print(f"📄 Total Shopify pages loaded: {len(pages)}")
    query = query.lower().strip()

    # For intent-specific pages (contact, shipping, etc.)
    if intent in DIRECT_PAGE_HANDLES:
        forced_handle = DIRECT_PAGE_HANDLES[intent]
        forced_page = next((p for p in pages if p["handle"] == forced_handle), None)
        if forced_page:
            print(f"🎯 Forced match by intent: {intent} → {forced_handle}")
            summary = summarize_page_content(get_full_page_text(forced_page), title=forced_page["title"])
            url = f"{shopify_store_url}/pages/{forced_handle}"
            return f"{summary}<br><br><a href='{url}' target='_blank'>Read more</a>"

    # General semantic search (basic string similarity for now)
    best_page = None
    best_score = 0.0

    for page in pages:
        handle = page.get("handle", "")
        if handle in irrelevant_handles:
            continue
        text = f"{page.get('title', '')} {page.get('body_html', '')}".lower()
        score = SequenceMatcher(None, query, text).ratio()
        if score > best_score:
            best_score = score
            best_page = page

    if best_page:
        summary = summarize_page_content(get_full_page_text(best_page), title=best_page["title"])
        url = f"{shopify_store_url}/pages/{best_page['handle']}"
        return f"{summary}<br><br><a href='{url}' target='_blank'>Read more</a>"
    else:
        return "Sorry, I couldn’t find any relevant page for your question."
