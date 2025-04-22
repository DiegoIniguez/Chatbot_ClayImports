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


app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "Hello! The server is running correctly."

api_key = os.getenv("OPENAI_API_KEY")
shopify_access_token = os.getenv("SHOPIFY_API_KEY")
shopify_store_url = os.getenv("SHOPIFY_STORE_URL")

client = openai.OpenAI(api_key=api_key)

PRODUCTS_CACHE_FILE = "cached_products.joblib"

def get_cached_products(force_refresh=False):
    if not force_refresh:
        try:
            return joblib.load(PRODUCTS_CACHE_FILE)
        except:
            pass

    print("💾 Cache no encontrada o forzada. Cargando productos desde Shopify...")
    products = get_shopify_products()
    joblib.dump(products, PRODUCTS_CACHE_FILE)
    return products


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
            "You are a helpful assistant. Generate a short, friendly introduction to a list of blog articles based on the following customer message:\n\n"
            f"{user_message}"
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
    response_text = f"{intro_text}<br>"
    for b in top_blogs:
        title = b["title"]
        text = b.get("content", "")
        summary = summarize_page_content(text, title=title)
        blog_url = b.get("url")

        response_text += f"📰 <b>{title}</b><br>{summary}<br>"
        response_text += f"<a href='{blog_url}' target='_blank' style='color: #007bff; text-decoration: underline;'>View article</a><br><br>"


    return response_text



def get_shopify_products():
    """Obtiene TODOS los productos activos de Shopify con paginación."""
    url = f"{shopify_store_url}/admin/api/2024-01/products.json?limit=250&status=active&fields=id,title,handle,body_html,tags,product_type,variants,image"
    headers = {"X-Shopify-Access-Token": shopify_access_token}

    all_products = []
    page_counter = 1

    while url:
        print(f"📦 Fetching page {page_counter} of products...")
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"⚠️ Shopify error: {response.status_code}")
            break

        products = response.json().get("products", [])
        print(f"🧩 Found {len(products)} products in this page.")
        all_products.extend(products)

        # Shopify paginación vía header Link
        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            parts = link_header.split(",")
            next_link = None
            for part in parts:
                if 'rel="next"' in part:
                    next_link = part.split(";")[0].strip("<> ")
            url = next_link
            page_counter += 1
        else:
            url = None

    print(f"✅ Total active products fetched: {len(all_products)}")

    # Filtrar solo productos con al menos una variante disponible (con inventario > 0)
    available_products = []
    for product in all_products:
        for variant in product["variants"]:
            if variant["inventory_quantity"] > 0:
                available_products.append(product)
                break

    print(f"✅ Total available products with inventory: {len(available_products)}")
    return available_products



def is_ask_for_more(message):
    phrases = [
        "more", "show me more", "give me more", "another one", "something else",
        "share more", "display more", "share me more"
    ]
    return any(p in message.lower() for p in phrases)


def normalize(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'(\d+)\s*["’]?\s*[x×]\s*(\d+)', r'\1x\2', text)
    return (
        text.lower()
            .replace('"', '')
            .replace("'", '')
            .replace("’", '')
            .replace("“", '')
            .replace("”", '')
            .replace("×", "x")
            .replace("  ", " ")
            .strip()
    )


def summarize_product_description(description):
    """Genera un resumen corto de la descripción del producto."""
    try:
        if not description or len(description) < 10:
            return "A great choice!"

        print("🧠 Llamando a OpenAI para generar resumen...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize the following product description in one short sentence:"},
                {"role": "user", "content": description}
            ],
            max_tokens=50,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error al resumir descripción: {e}")
        return "A great choice!"


def get_product_recommendations(user_message, context=None, session_id="default", user_message_count=0):
    products = get_cached_products()
    if not products:
        return "Sorry, we currently have no products available."


    # 🎨 Diccionario de emojis por tag
    tag_emojis = {
        # Uso
        "usage_kitchen": "🍽️",
        "usage_bathroom": "🚿",
        "usage_interior": "🏠",

        # Colores
        "color_terracotta": "🧱",
        "color_white": "⚪",
        "color_black": "⚫",
        "color_blue": "🔵",
        "color_green": "🟢",
        "color_navy": "🌊",
        "color_beige": "🟤",
        "color_brown": "🪵",
        "color_grey": "⬜",
        "color_pink": "🌸",
        "color_yellow": "🌞",

        # Acabados
        "finish_matte": "🪨",
        "finish-glossy": "💎",
        "finish-satin-sealed": "✨",
        "finish-raw": "🌿",
        "finish-natural": "🍃",

        # Formas
        "tileshape_hexagon": "⬡",
        "tileshape_circle": "⭕",
        "tileshape_square": "◼️",
        "tileshape_rectangle": "⬛",
        "tileshape_2x6": "➖",
        "tileshape_3x3": "〰️",

        # Estilo
        "style_modern": "🧊",
        "style_handmade": "🖐️",
        "style_natural": "🌿",
        "style_rustic": "🌾",

        # Materiales
        "material_clay": "🏺",
        "material_cement": "🧱",
        "breeze_blocks": "🧱",
        "material_concrete": "🏗️",
        "material_ceramic": "🔷",
        "material_terracotta": "🧡",

        # Default
        "default": "🧩"
    }


    user_message = user_message.lower().strip()

    # 🔗 Mapeo de palabras clave comunes a tags
    tag_filters = {
        # Uso
        "kitchen": "usage_kitchen",
        "bathroom": "usage_bathroom",
        "interior": "usage_interior",
        "shower": "usage_bathroom",
        "backsplash": "usage_kitchen",
        "restaurant": "usage_interior",

        # Colores comunes
        "terracotta": "color_terracotta",
        "burnt orange": "color_terracotta",
        "earthy": "color_terracotta",
        "white": "color_white",
        "black": "color_black",
        "blue": "color_blue",
        "green": "color_green",
        "navy": "color_navy",
        "beige": "color_beige",
        "brown": "color_brown",
        "grey": "color_grey",
        "pink": "color_pink",
        "yellow": "color_yellow",

        # Acabados
        "matte": "finish_matte",
        "glossy": "finish_glossy",
        "satin": "finish-satin-sealed",
        "sealed": "finish-satin-sealed",
        "natural finish": "finish-natural",
        "natural clay": "material_terracotta",
        "rough": "finish-raw",

        # Formas
        "hexagon": "tileshape_hexagon",
        "circle": "tileshape_circle",
        "square": "tileshape_square",
        "rectangle": "tileshape_rectangle",
        "2x6": "tileshape_2x6",
        "3x3": "tileshape_3x3",

        # Estilo
        "modern": "style_modern",
        "handmade": "style_handmade",
        "natural": "style_natural",
        "rustic": "style_rustic",
        "handcrafted": "style_handmade",

        # Material
        "clay": "material_clay",
        "cement": "material_cement",
        "concrete": "material_concrete",
        "ceramic": "material_ceramic",
        "terracotta material": "material_terracotta",
    }


    keywords = user_message.split()

    # 🎯 Detectar tags que deben estar presentes
    required_tags = set()
    for word in keywords:
        tag = tag_filters.get(word.strip())
        if tag:
            required_tags.add(tag)

    # 🔍 Añadir palabras clave según contexto detectado
    if context:
        context_keywords = {
            "kitchen": ["kitchen", "backsplash", "cook", "usage_kitchen"],
            "bathroom": ["bathroom", "shower", "sink", "usage_bathroom"],
            "restaurant": ["restaurant", "bar", "counter", "usage_interior"]
        }
        keywords += context_keywords.get(context, [])

    relevant_products = []
    shown_handles = session_memory.get(session_id, {}).get("shown_products", set())

    best_match_product = None
    best_similarity = 0.0

    normalized_user_message = normalize(user_message)
    print(f"🔍 Buscando: {normalized_user_message}")

    for product in products:
        raw_title = product.get('title') or ""
        normalized_title = normalize(raw_title)
        description = (product.get('body_html') or '').lower()
        if not description:
            description = "This is a beautiful product available in our store. Feel free to explore more details!"

        tags = [(tag or "").strip().lower() for tag in (product.get("tags") or "").split(",")]

        if "sample" in normalized_title or any("sample" in tag for tag in tags):
            continue

        if product['handle'] in shown_handles:
            continue  # 🚫 Ya mostrado en esta sesión

        # ⛔ Si no tiene todos los tags requeridos, lo ignoramos
        if required_tags:
            tag_matches = sum(1 for req in required_tags if req in tags)
            if tag_matches < max(1, len(required_tags) - 1):
                continue

        match_score = 0

        for kw in keywords:
            kw = kw.strip().lower()

            if kw in normalized_title:
                match_score += 3
            if kw in description:
                match_score += 2
            if any(kw in tag.strip() for tag in tags):
                match_score += 4
            if kw in ["backsplash", "kitchen"]:
                match_score += 1

        if len(description) < 40:
            match_score -= 2

        all_words_match = all(word in normalized_title for word in normalized_user_message.split())

        if all_words_match:
            similarity = 1.0
            match_score += 10
        else:
            similarity = SequenceMatcher(None, normalized_user_message, normalized_title).ratio()

        print(f"✅ Título normalizado: {normalized_title}")
        print(f"✅ Mensaje normalizado: {normalized_user_message}")
        print(f"✅ Todas las palabras presentes: {all_words_match}")
        print(f"🎯 Similaridad calculada: {similarity:.2f}")
        print(f"📌 Match Score de '{raw_title.strip()}': {match_score}")

        # ✅ Escoge el mejor producto solo si el score es bueno y similaridad también
        if match_score > 0:
            product["match_score"] = match_score
            relevant_products.append(product)

            # Aquí está la lógica mejorada: evitamos que se sobrescriba con uno irrelevante
            if similarity > best_similarity and match_score >= 10:
                best_similarity = similarity
                best_match_product = product



    print(f"👁️‍🗨️ MEJOR MATCH ACTUAL: {best_match_product['title'] if best_match_product else 'None'}")
    print(f"📊 SIMILITUD: {best_similarity:.2f}")
    if best_match_product:
        print(f"🏷️ Tags: {(best_match_product.get('tags') or '').lower()}")
        print(f"📛 Handle: {best_match_product.get('handle')}")
        print(f"📄 Title: {best_match_product.get('title')}")


    if best_match_product and (best_similarity > 0.7 or best_match_product.get("match_score", 0) >= 18):
        title = best_match_product.get("title", "").lower()
        tags = (best_match_product.get("tags", "") or "").lower()

        if "sample" not in title and "sample" not in tags:
            print(f"🎯 MATCH POR SIMILITUD: {best_match_product['title']} (score: {best_similarity:.2f})")
            description = summarize_product_description(best_match_product.get('body_html') or "")
            product_url = f"{shopify_store_url}/products/{best_match_product['handle']}"
            session_data = session_memory.setdefault(session_id, {})
            shown_products = session_data.setdefault("shown_products", set())
            shown_products.add(best_match_product["handle"])

            return (
                f"Yes! We have <b>{best_match_product['title']}</b>.<br>{description}<br>"
                f"<a href='{product_url}' target='_blank' style='color: #007bff; text-decoration: underline;'>View product</a>"
            )
            
        else:
            print(f"🚫 Mejor match descartado por ser muestra: {best_match_product['title']}")


    def is_sample_product(product):
        title = product.get("title", "").lower()
        tags = (product.get("tags", "") or "").lower()
        return "sample" in title or "sample" in tags

    if relevant_products:
        sorted_products = sorted(relevant_products, key=lambda x: -x["match_score"])
        selected = [p for p in sorted_products if p["handle"] not in shown_handles and not is_sample_product(p)][:3]
        session_data = session_memory.setdefault(session_id, {})
        shown_products = session_data.setdefault("shown_products", set())
        shown_products.update(p["handle"] for p in selected)

        # ✅ Generar intro natural con OpenAI
        try:
            print("🧠 Llamando a OpenAI para la introducción...")
            is_early_convo = user_message_count < 2
            prompt = (
                "You are a helpful assistant for a tile store. Based on the customer message, generate "
                + ("a short, friendly intro with a warm greeting. "
                if is_early_convo else
                "a short intro without any greeting. ")
                + "Include relevant details like color, finish, shape, or usage (e.g. kitchen, bathroom), if mentioned. "
                "Do not list products. Just introduce the upcoming list in a friendly way.\n\n"
                "Your response must be natural and **no more than 20 words**.\n\n"
                f"Customer said: {user_message}"
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
            intro_text = "Here are some great tiles you might like!"
            import traceback
            traceback.print_exc()


        response_text = f"{intro_text}<br>"

    else:
        selected = [
            p for p in products
            if p["handle"] not in shown_handles
            and "sample" not in (p["title"] or "").lower()
            and "sample" not in (p.get("tags") or "").lower()
        ]   
        selected = random.sample(selected, min(3, len(selected)))
        session_data = session_memory.setdefault(session_id, {})
        shown_products = session_data.setdefault("shown_products", set())
        shown_products.update(p["handle"] for p in selected)

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a friendly assistant helping a customer find the best products based on their request. Generate a short introduction that smoothly leads into product suggestions."},
                    {"role": "user", "content": f"The customer asked: {user_message}"}
                ],
                max_tokens=50,
                temperature=0.7
            )
            intro_text = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"⚠️ OpenAI intro failed: {e}")
            intro_text = "Here are some great options you might like!"

        response_text = f"{intro_text}<br>"

    response_text += '<div class="product-carousel" style="display: flex; gap: 20px; overflow-x: auto; padding: 10px 0;">'

    for p in selected:
        title = p['title']
        description = summarize_product_description(p.get('body_html', ''))
        product_url = f"{shopify_store_url}/products/{p['handle']}"
        tags = (p.get("tags") or "").lower().split(",")
        image_url = p.get("image", {}).get("src", "")

        # 🧩 Convertimos tags a emojis
        emojis = " ".join(
            sorted(set(
                tag_emojis.get(tag.strip(), tag_emojis.get("default", "🧩"))
                for tag in tags if tag.strip()
            ))
        )

        response_text += f"""
        <div class="product-card" style="flex: 0 0 220px; border: 1px solid #ccc; border-radius: 12px; padding: 12px; text-align: center; background: #fff;">
            <img src="{image_url}" alt="{title}" style="max-width: 100%; height: auto; border-radius: 8px;" />
            <h4 style="margin: 10px 0 4px;">{emojis} {title}</h4>
            <p style="font-size: 0.9rem; color: #333;">{description}</p>
            <a href="{product_url}" target="_blank" style="color: #007bff; text-decoration: underline; font-weight: bold;">View product</a>
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
            return "I'm here to help you with information about our store! 😊 Ask me about our products, policies, blogs, or anything related to our store."
        
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

        if is_ask_for_more(user_message):
            session_data = session_memory.get(session_id, {})
            last_intent = session_data.get("last_intent")
            
            if last_intent == "search_blog":
                last_query = session_data.get("last_blog_query")
                if last_query:
                    response_text = search_shopify_blogs(user_message, blog_articles, session_id=session_id, user_message_count=user_message_count)
                    intent = "search_blog"
            elif last_intent == "search_product":
                last_query = session_data.get("last_product_query")
                if last_query:
                    response_text = get_product_recommendations(last_query, session_id=session_id, user_message_count=user_message_count)
                    intent = "search_product"

            if not response_text:
                response_text = "Let me know what you'd like to see more of – products, blogs, or something else!"

            print("🔁 Intent: ask_for_more — using previous query")
            log_user_interaction(user_message, response_text, intent)
            return jsonify({"answer": response_text, "intent": intent})


        print("🎯 Detected intent:", intent)

        context_tag = detect_context(user_message)
        print("🏠 Detected context:", context_tag)


        shop_context = f"Store name: {get_shop_info().get('name', 'Unknown')}, Currency: {get_shop_info().get('currency', 'N/A')}"


        # Lógica según la intención
        if intent == "search_product":
            print("🪴 Intent: search_product")
            session_memory.setdefault(session_id, {})["last_product_query"] = user_message
            session_memory[session_id]["last_intent"] = "search_product"
            response_text = get_product_recommendations(user_message, context=context_tag, session_id=session_id, user_message_count=user_message_count)

        elif intent == "search_blog":
            print("📰 Intent: search_blog (from articles.json)")
            response_text = search_shopify_blogs(user_message, session_id=session_id, user_message_count=user_message_count)

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