import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from openai import OpenAI
import hashlib
import os
import json
import numpy as np
import re

# Shopify store URL
shopify_store_url = "https://clayimports.com"

# --- EMBEDDING SETUP ---
EMBEDDING_CACHE_PATH = "embedding_cache.json"
embedding_cache = {}

if os.path.exists(EMBEDDING_CACHE_PATH):
    with open(EMBEDDING_CACHE_PATH, "r") as f:
        embedding_cache = json.load(f)

def save_embedding_cache():
    with open(EMBEDDING_CACHE_PATH, "w") as f:
        json.dump(embedding_cache, f)

def get_embedding(text):
    text = text.strip().replace("\n", " ")[:2000]
    text_hash = hashlib.md5(text.encode()).hexdigest()

    if text_hash in embedding_cache:
        return embedding_cache[text_hash]

    client = OpenAI()
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    embedding = response.data[0].embedding
    embedding_cache[text_hash] = embedding
    save_embedding_cache()
    return embedding

def cosine_similarity(vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# --- SCRAPING FUNCTION ---
def scrape_shopify_page(url):
    try:
        print(f"🕸️ Scraping content from: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"❌ Failed to fetch page. Status code: {response.status_code}")
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # 🔥 Elimina secciones irrelevantes por etiqueta
        for tag in soup(["script", "style", "noscript", "header", "footer", "svg", "nav", "form", "button"]):
            tag.decompose()

        # 🔥 Elimina secciones irrelevantes por clases sospechosas
        blacklist = ["footer", "header", "menu", "wishlist", "share", "newsletter", "toolbar", "account", "breadcrumb"]
        for div in soup.find_all(True, {"class": lambda c: c and any(x in c.lower() for x in blacklist)}):
            div.decompose()

        # ✅ Extraer texto visible
        visible_text = soup.get_text(separator=" ", strip=True)

        # 🧼 Limpieza básica
        visible_text = re.sub(r"\s{2,}", " ", visible_text)

        return visible_text

    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        return ""


# --- UNIFIED CONTENT FETCH ---
def get_full_page_text(page):
    body_html = (page.get("body_html") or "").strip()
    handle = page.get("handle")
    scraped_text = scrape_shopify_page(f"{shopify_store_url}/pages/{handle}")
    combined_text = f"{body_html}\n\n{scraped_text}".strip()
    return combined_text[:3000]

# --- FIND BEST MATCH WITH EMBEDDINGS ---
def find_best_shopify_pages(query, pages):
    scored_pages = []

    for page in pages:
        handle = page.get("handle")
        title = page.get("title", "").lower()
        full_text = get_full_page_text(page).lower()

        query_embedding = get_embedding(query)
        page_embedding = get_embedding(full_text[:1000])

        score = cosine_similarity(query_embedding, page_embedding)
        scored_pages.append((page, score))

        print(f"🔍 {title} — Similarity: {score:.4f}")

    # Ordenar por mayor puntuación
    scored_pages.sort(key=lambda x: x[1], reverse=True)

    best_page = scored_pages[0][0]
    second_best_page = scored_pages[1][0]
    best_score = scored_pages[0][1]
    second_score = scored_pages[1][1]

    return (best_page, best_score), (second_page, second_score)


# --- SUMMARIZE PAGE CONTENT ---
def summarize_page_content(content, title=""):
    try:
        if not content or len(content) < 20:
            return "This page contains details about your request."

        full_prompt = (
            f"The customer is asking about: {title}.\n\n"
            f"Page content:\n{content}"
        )

        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful, friendly assistant. Summarize the page below in 1-2 friendly sentences. "
                        "Avoid repeating the title, and highlight any useful or unique details customers may appreciate."
                    )
                },
                {"role": "user", "content": full_prompt}
            ],
            max_tokens=180,
            temperature=0.6
        )

        summary = response.choices[0].message.content.strip()
        if not summary or len(summary) < 10:
            print("⚠️ OpenAI returned a bad summary. Using fallback.")
            return content[:200] + "..."

        return summary

    except Exception as e:
        print(f"❌ OpenAI summarization failed: {e}")
        return "This page contains useful information about your request."
