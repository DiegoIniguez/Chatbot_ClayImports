# utils.py
import os
import requests

def get_shopify_pages():
    shopify_store_url = os.getenv("SHOPIFY_STORE_URL")
    shopify_access_token = os.getenv("SHOPIFY_API_KEY")

    pages = []
    url = f"{shopify_store_url}/admin/api/2024-01/pages.json?limit=250"
    headers = {"X-Shopify-Access-Token": shopify_access_token}

    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"⚠️ Error fetching pages: {response.status_code}")
            return pages

        data = response.json()
        filtered_pages = [p for p in data.get("pages", []) if p.get("published_at")]
        pages.extend(filtered_pages)

        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            next_url = link_header.split(";")[0].strip("<>")
            url = next_url
        else:
            url = None

    print(f"✅ Total published pages fetched: {len(pages)}")
    return pages
