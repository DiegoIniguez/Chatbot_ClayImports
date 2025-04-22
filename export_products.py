import json
import os
import requests

shopify_access_token = os.getenv("SHOPIFY_API_KEY")
shopify_store_url = os.getenv("SHOPIFY_STORE_URL")

def get_shopify_products():
    """Obtiene TODOS los productos activos de Shopify con paginación."""
    url = f"{shopify_store_url}/admin/api/2024-01/products.json?limit=250&status=active&fields=id,title,handle,body_html,tags,product_type,variants"
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

    available_products = []
    for product in all_products:
        for variant in product.get("variants", []):
            if variant.get("inventory_quantity", 0) > 0:
                available_products.append(product)
                break

    print(f"✅ Total available products with inventory: {len(available_products)}")
    return available_products

if __name__ == "__main__":
    products = get_shopify_products()
    with open("products.json", "w") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    print("📦 Archivo exportado: products.json")
