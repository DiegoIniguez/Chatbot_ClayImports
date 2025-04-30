
import os
import requests
import json

# 🔑 API Credentials
SHOPIFY_ACCESS_TOKEN = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")

HEADERS = {"X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN}

# 📦 Fetch collections from Shopify
def get_all_collections():
    collections = []
    endpoints = ["custom_collections", "smart_collections"]

    for endpoint in endpoints:
        url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/{endpoint}.json?limit=250"

        while url:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 200:
                data = response.json().get(endpoint, [])
                collections.extend(data)

                # Shopify pagination
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
    return collections

# 🧱 Fetch all products from Shopify
def get_all_products():
    products = []
    url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/products.json?limit=250&status=active"

    while url:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = [p for p in response.json().get("products", []) if p.get("status") == "active"]
            products.extend(data)

            # Shopify pagination
            link_header = response.headers.get("Link", "")
            if 'rel="next"' in link_header:
                parts = link_header.split(",")
                next_link = [p.split(";")[0].strip("<> ") for p in parts if 'rel="next"' in p]
                url = next_link[0] if next_link else None
            else:
                url = None
        else:
            print(f"❌ Error fetching products: {response.status_code}")
            break

    print(f"✅ Total products fetched: {len(products)}")
    return products

if __name__ == "__main__":
    print("🚀 Exporting Shopify collections and products...")
    collections = get_all_collections()
    products = get_all_products()

    with open("collections.json", "w", encoding="utf-8") as f:
        json.dump(collections, f, indent=2, ensure_ascii=False)

    with open("products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, indent=2, ensure_ascii=False)

    print("📦 collections.json and products.json exported successfully!")
