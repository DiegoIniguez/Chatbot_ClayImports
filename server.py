from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import requests
import os
import random
import gspread
import joblib
import re
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from difflib import SequenceMatcher
from cachetools import TTLCache
from page_scraper import find_best_shopify_pages, get_full_page_text, summarize_page_content
from smart_page_router import search_shopify_pages
from utils import get_shopify_pages
from faq_support.faq_search import search_faq_semantic

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Hello! The server is running correctly."

api_key = os.getenv("OPENAI_API_KEY")
shopify_access_token = os.getenv("SHOPIFY_API_KEY")
shopify_store_url = os.getenv("SHOPIFY_STORE_URL")
headers = {"X-Shopify-Access-Token": shopify_access_token}

client = openai.OpenAI(api_key=api_key)

COLLECTIONS_CACHE_FILE = "cached_collections.joblib"

def get_cached_collections(force_refresh=False):
    if not force_refresh:
        try:
            return joblib.load(COLLECTIONS_CACHE_FILE)
        except:
            pass

    print("💾 Cache no encontrada o forzada. Cargando colecciones desde Shopify...")
    collections = []
    endpoints = ["custom_collections", "smart_collections"]

    for endpoint in endpoints:
        url = f"{shopify_store_url}/admin/api/2024-01/{endpoint}.json?limit=250"
        while url:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json().get(endpoint, [])
                collections.extend(data)

                link_header = response.headers.get("Link", "")
                if 'rel="next"' in link_header:
                    parts = link_header.split(",")
                    next_link = [p.split(";")[0].strip("<> ") for p in parts if 'rel="next"' in p]
                    url = next_link[0] if next_link else None
                else:
                    url = None
            else:
                print(f"❌ Error fetching {endpoint}: {response.status_code}")
                break

    print(f"✅ Total collections fetched: {len(collections)}")
    joblib.dump(collections, COLLECTIONS_CACHE_FILE)
    return collections


def should_refresh_collections():
    try:
        file_path = "cached_collections.joblib"
        if not os.path.exists(file_path):
            print("🆕 No cached collections found. Will refresh.")
            return True
        file_age_seconds = time.time() - os.path.getmtime(file_path)
        file_age_days = file_age_seconds / (60 * 60 * 24)
        if file_age_days > 7:
            print(f"🔁 Cached collections are {file_age_days:.1f} days old. Refreshing...")
            return True
        else:
            print(f"🗂️ Cached collections are fresh ({file_age_days:.1f} days old). No refresh needed.")
            return False
    except Exception as e:
        print(f"❌ Error checking cache age: {e}")
        return True

# Memoria por sesión con duración limitada (1 hora)
session_memory = TTLCache(maxsize=1000, ttl=3600)  # 1000 sesiones, expiran a la hora


# 🔤 Dataset de entrenamiento para clasificación de intención
MODEL_FILE = "intent_model.joblib"

try:
    intent_model = joblib.load(MODEL_FILE)
    print("✅ Modelo de intención cargado exitosamente.")
except Exception as e:
    print(f"❌ No se pudo cargar el modelo entrenado: {e}")
    # Fallback a modelo simple vacío
    from sklearn.pipeline import make_pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    intent_model = make_pipeline(TfidfVectorizer(), MultinomialNB())


try:
    with open("articles.json", "r") as f:
        blog_articles = json.load(f)
    print(f"✅ Blog articles loaded: {len(blog_articles)}")
except Exception as e:
    print(f"❌ Error loading articles.json: {e}")
    blog_articles = []

# 🔍 Función para detectar intención
def classify_intent(message):
    if is_irrelevant_question(message):
        return "not_supported"
    return intent_model.predict([message])[0]

def is_close_match(title, message, threshold=0.85):
    return SequenceMatcher(None, title.lower(), message.lower()).ratio() > threshold

def log_user_interaction(user_message, bot_response, intent=""):
    try:
        # Autenticación con la hoja de Google
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
        client = gspread.authorize(creds)

        # Acceder a la hoja
        sheet = client.open("Chatbot logs").sheet1  # Usamos la primer hoja

        # Agregar la conversación como nueva fila
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_message,
            intent,
            bot_response
        ])

        print("✅ Conversación registrada en Google Sheets.")
    except Exception as e:
        print(f"❌ Error al guardar en Google Sheets: {e}")

def get_shop_info():
    url = f"{shopify_store_url}/admin/api/2024-01/shop.json"
    headers = {"X-Shopify-Access-Token": shopify_access_token}
    response = requests.get(url, headers=headers)
    return response.json().get("shop", {}) if response.status_code == 200 else {}


def get_shopify_blogs():
    url = f"{shopify_store_url}/admin/api/2024-01/blogs.json"
    headers = {"X-Shopify-Access-Token": shopify_access_token}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    blogs = response.json().get("blogs", [])
    all_articles = []
    for blog in blogs:
        articles_url = f"{shopify_store_url}/admin/api/2024-01/blogs/{blog['id']}/articles.json"
        articles_response = requests.get(articles_url, headers=headers)
        if articles_response.status_code == 200:
            articles = articles_response.json().get("articles", [])
            for article in articles:
                if article.get("published_at"):
                    article["blog_handle"] = blog["handle"]
                    all_articles.append(article)
    return all_articles

def get_blog_pages():
    blogs = get_shopify_blogs()
    blog_pages = []

    for blog in blogs:
        # Ya filtraste published_at antes, así que aquí va directo
        blog_pages.append({
            "handle": blog["handle"],
            "title": blog["title"],
            "body_html": blog.get("summary_html") or blog.get("body_html") or "",
            "blog_handle": blog["blog_handle"],
            "is_blog": True
        })

    return blog_pages

def search_shopify_blogs(user_message, session_id="default", user_message_count=0):
    try:
        with open("articles.json", "r") as f:
            blogs = json.load(f)
            print(f"✅ Blog articles loaded: {len(blogs)}")
    except Exception as e:
        print(f"❌ Error loading articles.json: {e}")
        return "Sorry, no blog articles available right now."

    query = normalize(user_message)
    shown_handles = session_memory.get(session_id, {}).get("shown_blogs", set())
    scored_blogs = []

    for b in blogs:
        title = normalize(b.get("title", ""))
        body = normalize(b.get("content", ""))
        content = f"{title} {body}"

        # Puntuación personalizada
        match_score = 0
        keywords = query.split()
        strong_match_found = False

        for word in keywords:
            if word in title:
                match_score += 6
                strong_match_found = True
            if word in body:
                match_score += 2

        if all(word in title for word in keywords):
            match_score += 10
            strong_match_found = True
        if strong_match_found:
            match_score += 5

        similarity = SequenceMatcher(None, query, content).ratio()

        if b["url"] in shown_handles:
            continue

        b["match_score"] = match_score
        b["similarity"] = similarity
        scored_blogs.append(b)

    if not scored_blogs:
        return "No matching blog articles found at the moment."

    filtered_blogs = [
        b for b in scored_blogs
        if any(word in normalize(b.get("title", "")) for word in keywords)
    ]

    blogs_to_show = filtered_blogs if filtered_blogs else scored_blogs
    top_blogs = sorted(blogs_to_show, key=lambda x: (-x["match_score"], -x["similarity"]))[:3]

    session_data = session_memory.setdefault(session_id, {})
    shown_blogs = session_data.setdefault("shown_blogs", set())
    shown_blogs.update(b["url"] for b in top_blogs)

    # Intro con OpenAI
    try:
        print("🧠 Llamando a OpenAI para intro de blogs...")
        prompt = (
            "You are a helpful assistant. Generate a very short, friendly introduction to a list of blog articles.\n"
            "The customer asked:\n"
            f"{user_message}\n\n"
            "Your response must sound natural and be no more than 20 words total. Do not mention blog titles or products."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=50,
            temperature=0.7
        )
        intro_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ OpenAI intro failed: {e}")
        intro_text = "Here are some blog articles you might find helpful:"

   # 📰 Construir respuesta final
    response_text = f"{intro_text}<br><br>"
    for b in top_blogs:
        title = b["title"]
        text = b.get("content", "")
        summary = summarize_page_content(text, title=title)
        blog_url = b.get("url")

        response_text += f"📰 <b>{title}</b><br>{summary}<br>"
        response_text += f"<a href='{blog_url}' target='_blank' style='color: #007bff; text-decoration: underline;'>View article</a><br><br>"


    return response_text

def normalize(text):
    if not isinstance(text, str):
        text = ""
    text = re.sub(r'\s+', ' ', text)
    text = text.lower().strip()
    return text


def clean_title(title):
    title = title.lower()
    title = re.sub(r'\|.*$', '', title)  # corta todo después del "|"
    title = re.sub(r'(\d+)\s*["’]?\s*[x×]\s*(\d+)', r'\1x\2', title)  # 4" x 4" → 4x4
    title = re.sub(r'[^a-z0-9\s\.x]', '', title)  # remueve simbolitos
    title = re.sub(r'\s+', ' ', title)  # espacios dobles
    return title.strip()


def get_collection_recommendations(user_message, session_id="default", user_message_count=0):
    collections = get_cached_collections()
    if not collections:
        return "Sorry, no collections available."

    user_keywords = normalize(user_message).split()
    shown_handles = session_memory.get(session_id, {}).get("shown_collections", set())
    scored_collections = []

    for coll in collections:
        title = normalize(coll.get("title", ""))
        body = normalize(coll.get("body_html", ""))
        tags = [tag.strip().lower() for tag in coll.get("tags", "").split(",")]
        handle = coll.get("handle")
        image_url = coll.get("image", {}).get("src", "")

        if not image_url:
            continue  # ❌ Saltar colecciones sin imagen

        if coll.get("product_count", 0) == 0:
            continue  # ❌ Saltar colecciones vacías

        if handle in shown_handles:
            continue

        match_score = 0
        for word in user_keywords:
            if word in title:
                match_score += 5
            if word in tags:
                match_score += 4
            if word in body:
                match_score += 2

        # NUEVO: matching por títulos de productos relacionados
        product_titles = [pt.lower() for pt in coll.get("product_titles", [])]
        for word in user_keywords:
            if any(word in pt for pt in product_titles):
                match_score += 3  # o el peso que tú creas justo

        similarity = SequenceMatcher(None, normalize(user_message), title).ratio()

        scored_collections.append({
            "collection": coll,
            "score": match_score,
            "similarity": similarity
        })

    top_collections = sorted(scored_collections, key=lambda x: (-x["score"], -x["similarity"]))[:3]

    if not top_collections:
        return "We couldn't find any matching collections. 😢"

    session_data = session_memory.setdefault(session_id, {})
    shown_collections = session_data.setdefault("shown_collections", set())
    shown_collections.update(c["collection"]["handle"] for c in top_collections)

    # 🔥 Generar introducción usando OpenAI
    try:
        prompt = (
            "You are a friendly tile store assistant. Based on the customer's message, "
            "generate a short intro (under 20 words) presenting tile collections "
            "without listing collection names. Mention style, color or usage if possible.\n\n"
            f"Customer message:\n{user_message}"
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": prompt}],
            max_tokens=50,
            temperature=0.7
        )
        intro_text = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ OpenAI intro failed: {e}")
        intro_text = "Here are some collections you might love!"

    # 🛠️ Construir respuesta visual
    response_text = f"{intro_text}<br><div class='product-carousel' style='display: flex; gap: 20px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 10px 0;'>"

    for item in top_collections:
        coll = item["collection"]
        title = coll.get("title", "Untitled Collection")
        handle = coll.get("handle", "#")
        raw_body = coll.get("body_html", "") or ""
        description = re.sub('<[^<]+?>', '', raw_body)  # Limpia etiquetas HTML
        description = description.strip()[:100] + "..." if description else "Explore this collection."
        image_url = coll.get("image", {}).get("src", "") or "https://via.placeholder.com/240x240.png?text=No+Image"
        collection_url = f"{shopify_store_url}/collections/{handle}"

        response_text += f"""
        <div class="product-card" style="flex: 0 0 240px; scroll-snap-align: start; border: 1px solid #ccc; border-radius: 12px; padding: 12px; text-align: center; background: #fff;">
            <img src="{image_url}" alt="{title}" style="max-width: 100%; height: auto; border-radius: 8px; margin-bottom: 10px;" />
            <h4 style="margin: 10px 0 4px; font-size: 1rem; color: #222;">{title}</h4>
            <p style="font-size: 0.85rem; color: #555; height: 48px; overflow: hidden;">{description}</p>
            <a href="{collection_url}" target="_blank" style="display: inline-block; margin-top: 10px; padding: 6px 12px; background-color: #007bff; color: #fff; border-radius: 6px; text-decoration: none; font-weight: bold;">View Collection</a>
        </div>
        """

    response_text += "</div>"

    return response_text

def detect_context(user_message):
    """Detecta si el usuario pregunta sobre un espacio específico (cocina, baño, restaurante, etc.)."""
    kitchen_keywords = ["kitchen", "cooking", "dining"]
    bathroom_keywords = ["bathroom", "shower", "sink"]
    restaurant_keywords = ["restaurant", "café", "bar", "dining area"]

    if any(word in user_message for word in kitchen_keywords):
        return "kitchen"
    elif any(word in user_message for word in bathroom_keywords):
        return "bathroom"
    elif any(word in user_message for word in restaurant_keywords):
        return "restaurant"
    return None

def is_irrelevant_question(query):
    irrelevant_keywords = [
        "capital", "president", "weather", "history", "who is", "define", "translate",
        "joke", "fun fact", "news", "sports", "movie", "music", "random fact", "science",
        "adopt", "dragon", "dog", "pet", "spaceship", "crypto", "rent", "flight", "food", "pizza"
    ]
    return any(word in query for word in irrelevant_keywords)

def ask_openai(question, context=""):
    try:
        if is_irrelevant_question(question):
            return "I'm here to help you with information about our store! 😊 Ask me about our collections, policies, blogs, or anything related to our store."
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for an online store. Answer questions in a simple and friendly way, like you are talking to a customer who may not be familiar with technical terms. Do not use Markdown in your responses, only HTML."},
                {"role": "user", "content": f"{context}\n\n{question}"}
            ],
            max_tokens=200,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error with OpenAI: {e}")
        return "I'm here to help! Let me know what you need assistance with. 😊"


def log_unanswered_question(user_message, bot_response):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
        client = gspread.authorize(creds)

        # Segunda pestaña (sheet2)
        sheet = client.open("Chatbot logs").get_worksheet(1)

        # Nueva fila con timestamp, pregunta y respuesta generada
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            user_message,
            "unknown",  # Intento no detectado
            bot_response
        ])

        print("📄 Question without intention registered into Google Chatbot Sheet 2.")
    except Exception as e:
        print(f"❌ Error saving queestion without intention: {e}")


@app.route("/chat", methods=["POST"])
def chat():
    print("🚀 /chat endpoint called")  # Verificamos si el endpoint se activa

    try:
        data = request.json
        user_message_count = data.get("user_message_count", 0)
        print("📩 Raw request data:", data)

        user_message = data.get("message", "").strip().lower()
        user_message = re.sub(r'[\"“”]', '', user_message)  # elimina comillas
        user_message = re.sub(r'\s+', ' ', user_message)  # espacios dobles
        
        session_id = data.get("session_id", "default")
        
        print("🧠 User message:", user_message)

        if not user_message:
            return jsonify({"error": "Message is required"}), 400

        intent = classify_intent(user_message)

        print("🎯 Detected intent:", intent)

        context_tag = detect_context(user_message)
        print("🏠 Detected context:", context_tag)


        shop_context = f"Store name: {get_shop_info().get('name', 'Unknown')}, Currency: {get_shop_info().get('currency', 'N/A')}"


        # Lógica según la intención
        if intent in "search_collection":
            print(f"🪴 Intent: {intent}")
            session_memory.setdefault(session_id, {})["last_collection_query"] = user_message
            session_memory[session_id]["last_intent"] = "search_collection"
            response_text = get_collection_recommendations(
                user_message,
                session_id=session_id,
                user_message_count=user_message_count
            )

        elif intent == "search_blog":
            print("📰 Intent: search_blog (from articles.json)")
            response_text = search_shopify_blogs(user_message, session_id=session_id, user_message_count=user_message_count)
        
        elif intent == "faqs":
            try:
                faq = search_faq_semantic(user_message)
                print("📖 FAQ Match:", faq)

                if faq:
                    # ✅ Intros aleatorias integradas (sin OpenAI)
                    intros = [
                        "Here's a quick answer that might help 👇",
                        "Check this out, it might be just what you need.",
                        "Gotcha! This FAQ explains it:",
                        "Let’s clear that up real quick:",
                        "This one’s for you 👇",
                        "Quick guide to help you out:",
                        "This might be exactly what you were wondering.",
                        "Easy fix! Check this FAQ 👇",
                    ]
                    intro_text = random.choice(intros)

                    # 🧾 Estilo simple tipo blogs
                    response_text = f"{intro_text}<br><br>"
                    response_text += f"📌 <b>{faq['title']}</b><br>{faq['subtitle']}<br>"
                    response_text += f"<a href='{faq['url']}' target='_blank' style='color: #007bff; text-decoration: underline;'>View article</a><br><br>"

                    return jsonify({"answer": response_text, "intent": intent})

                else:
                    return jsonify({
                        "answer": "Hmm 🤔 I didn't find a precise answer in our FAQ. Can you rephrase?",
                        "intent": intent
                    })

            except Exception as e:
                print("❌ Error en search_faq_semantic:", e)
                return jsonify({
                    "answer": "Internal error while searching FAQs.",
                    "intent": intent
                })
        elif intent in ["contact", "studio", "book", "returns_info", "shipping", "trade", "our_story", "search_pages"]:
            print(f"📄 Intent: {intent}")
            session_memory.setdefault(session_id, {})["last_pages_query"] = user_message
            session_memory[session_id]["last_intent"] = "search_pages"
            response_text = search_shopify_pages(user_message, intent=intent)

        elif intent == "not_supported":
            response_text = "Sorry, we don’t offer that kind of product. We specialize in handcrafted tiles 🧱! Let me know if you need help with something else."

        else:
            print("🤖 Intent fallback: OpenAI")
            response_text = ask_openai(user_message, context=shop_context)
            log_unanswered_question(user_message, response_text)

        print("✅ Final response:", response_text)
        log_user_interaction(user_message, response_text, intent)
        return jsonify({"answer": response_text, "intent": intent})

    except Exception as e:
        import traceback
        print("❌ EXCEPCIÓN DETECTADA:")
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500



if __name__ == "__main__":
    print("🚦 Flask is starting... Debug mode is:", app.debug)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)