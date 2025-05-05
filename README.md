
# 🧱 ClayBot - AI and ML Project for Shopify Support

Welcome to **ClayBot**, a smart, evolving chatbot built for **Clay Imports**. It boosts customer service in Shopify with semantic search, weekly training, real-time scraping, and OpenAI integration.  
> 🧪 Currently under development – **not live in production**.

---

## 📦 General Project Structure

| Category | Files | Description |
|----------|----------|-------------|
| 🤖 Core Bot | `server.py`, `bot.py` | Main backend of the chatbot |
| 🧠 Intent ML | `weekly_learning.py`, `check_duplicates.py`, `intent_model.joblib`, `training_data.json` | Intent classifier with weekly learning |
| 🧱 Collections/Products | `export_collections_and_products.py`, `generate_collection_descriptions.py`, `regenerate_cache.py`, `products.json`, `collections_described.json`, `cached_collections.joblib` | Extraction and enrichment of collections with OpenAI |
| 📄 Informational Pages | `utils.py`, `pages.json` | Downloading and caching help pages from Shopify |
| 📄 FAQS | `faq_search.py`, `faq_embeddings.pt`, `generate_faq_embeddings.py` | Uses FAQS.json, semantic search and GPT 3.5 turbo to deliver best responses  |
| 📰 Blog | `build_articles.py`, `articles.json` | Downloading and caching Shopify blog posts |
| 🔎 Page Matching | `page_scraper.py`, `smart_page_router.py` | Search, scrape, and summarize help pages by intent |
| ⚙️ Automation | `run_pipeline.py` |Runs the entire training, export, and update flow |
| 🔐 Access | `google_credentials.json` | Logging in Google Sheets |
| 🧹 Utilities | `.gitignore`, `cleanup_vscode.sh` | Environment tools (optional) |

---

## ✅ Recommended Flow (Manual or Automated)

### 🔁 Option A: Automated
```bash
python3 run_pipeline.py
```
This command runs in order:
1. 🧠 Retrain intention (`weekly_learning.py`)
2. 🔍 Verifies duplicates (`check_duplicates.py`)
3. 🧱 Exports data (`export_collections_and_products.py`)
4. 🧠 Generates AI descriptions (`generate_collection_descriptions.py`)
5. 💾 Regenerate bot cache (`regenerate_cache.py`)
6. 📰 Updates blog articles (`build_articles.py`)

---

### 🧪 Option B: Manual

```bash
python3 weekly_learning.py
python3 check_duplicates.py
python3 export_collections_and_products.py
python3 generate_collection_descriptions.py
python3 regenerate_cache.py
python3 build_articles.py
```

---

## 🧠 Page matching and scraping

ClayBot uses `page_scraper.py` and `smart_page_router.py` as internal modules to:

- Scrape real content from Shopify pages (`/pages/...`).
- Clean up HTML and irrelevant content.
- Summarizing content with OpenAI using `text-embedding-3-small` and `gpt-4o-mini`.
- Display the summary to the user with a link.

This happens automatically when an intent like `contact`, `shipping`, `our_story` or `search_pages` is detected.

🔒 You don't need to run these scripts manually. They're already integrated into the workflow `server.py`.

---

## 📁 Generated Key Files

- `collections.json` → export from Shopify
- `products.json` → active products
- `collections_described.json` → enriched collections
- `cached_collections.joblib` → bot cache
- `intent_model.joblib` → updated classifier
- `articles.json`, `pages.json` → useful cached content

---

## ⚠️ IMPORTANT NOTES

- **Do not delete `cached_collections.joblib`** unless you regenerate it.
- **Check `google_credentials.json` and your environment variables before running.**
- `utils.py` updates `pages.json` automatically from `server.py`.
- No need to run `page_scraper.py` manually. It is connected to `search_shopify_pages()`.

---

## 🧠 What's next?

- Improve `collection_embeddings.json` for semantic matching.
- Improve `run_pipeline.py` with conditional logic.

---

Made with ❤️ for Clay Imports.
