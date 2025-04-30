
import json
import os
from openai import OpenAI
from tqdm import tqdm

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cargar colecciones y productos
with open("collections.json", "r", encoding="utf-8") as f:
    collections = json.load(f)

with open("products.json", "r", encoding="utf-8") as f:
    products = json.load(f)

# Indexar productos por tag
tag_to_products = {}
for product in products:
    product_tags = product.get("tags", "").split(", ")
    for tag in product_tags:
        tag_to_products.setdefault(tag.strip().lower(), []).append(product)

def generate_description(title, product_list):
    product_titles = [p["title"] for p in product_list[:10]]
    prompt = f"""
You're a tile branding expert for Clay Imports. Write a 1–2 sentence product collection description for a Shopify collection titled "{title}".
These are some of the products in this collection: {", ".join(product_titles)}.
Highlight the overall feel, style, or applications without naming individual products. Be clear, inspiring, and professional.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error generating description: {e}")
        return ""

# Generar descripciones
updated = 0
for collection in tqdm(collections, desc="🔄 Generando descripciones"):
    matched_products = []
    rules = collection.get("rules", [])

    # 1. Buscar productos por reglas de tag (colecciones automáticas)
    if rules:
        for rule in rules:
            if rule["column"] == "tag":
                tag = rule["condition"].strip().lower()
                matched_products.extend(tag_to_products.get(tag, []))

    # 2. Si no hay reglas (colecciones manuales), buscar por coincidencia de título
    if not matched_products:
        title_keywords = collection.get("title", "").lower().split()
        for product in products:
            product_title = product.get("title", "").lower()
            if all(word in product_title for word in title_keywords if len(word) > 3):
                matched_products.append(product)

    # 3. Guardar conteo y títulos
    collection["product_count"] = len(matched_products)
    collection["product_titles"] = [p["title"] for p in matched_products]

    if not collection.get("body_html") and matched_products:
        desc = generate_description(collection["title"], matched_products)
        if desc:
            collection["body_html"] = desc
            updated += 1

# Guardar colección enriquecida
with open("collections_described.json", "w", encoding="utf-8") as f:
    json.dump(collections, f, indent=2, ensure_ascii=False)

print(f"✅ Descripciones generadas para {updated} colecciones.")
