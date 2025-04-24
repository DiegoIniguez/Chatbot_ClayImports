# 🧠 ClayBot — AI Chatbot for ClayImports

**ClayBot** is an intelligent assistant designed to help ClayImports customers discover products, find answers, navigate store policies, blogs, and more. It combines scraping, machine learning, session memory, and OpenAI to deliver smart, human-like support.

---

## 🚀 Features

- 🔍 Product search by intent, tags, context, and semantic similarity
- 🧠 Intent classification using Naive Bayes (`sklearn`)
- 📄 Page and product scraping (including rich USAGE info)
- ✨ Auto summaries with OpenAI (`gpt-4o-mini`)
- 📊 Weekly learning pipeline from Google Sheets logs
- 🧩 Visual product carousels with emojis
- 🧠 Lightweight session memory (no repetitions)
- 📝 Logs all interactions and unanswered questions

---

## 📁 Project Structure

```bash
├── server.py                 # Flask API with main response logic
├── weekly_learning.py        # Weekly model trainer from logs
├── smart_page_router.py      # Smart router for help pages
├── utils.py                  # Shopify helper functions
├── page_scraper.py           # Scraper + embeddings + summarizer
├── scrape_clay_product.py    # Scraper for product + usage section
├── export_products.py        # Export all active products from Shopify
├── build_articles.py         # Export blog articles to articles.json
├── .gitignore                # Ignored files and folders
└── README.md                 # This file 📄
```

---

## 🛠️ How to Run

### 🧪 Local Testing

```bash
cd /opt/chatbot
python3 server.py
```

### 🚀 Production with Gunicorn

```bash
gunicorn server:app --bind 0.0.0.0:5000
```

---

## 🔐 Required Environment Variables

Create a `.env` file (not included in the repo):

```env
SHOPIFY_API_KEY=your_shopify_token
SHOPIFY_STORE_URL=https://clayimports.myshopify.com
OPENAI_API_KEY=sk-...
```

---

## 📦 Dependencies

- Python 3.10+
- Flask, Flask-CORS
- requests, joblib, sklearn, gspread
- OpenAI SDK
- BeautifulSoup4
- cachetools
- python-dotenv

### Install all with:

```bash
pip install -r requirements.txt
```

---

## 🧠 Machine Learning

- Classifier: `intent_model.joblib`
- Dataset: `training_data.json`
- Training script: `weekly_learning.py`
- Powered by: `TfidfVectorizer + MultinomialNB`

---

## 👤 Author

Built with 💛 by [@DiegoIniguez](https://github.com/DiegoIniguez) for ClayImports.
