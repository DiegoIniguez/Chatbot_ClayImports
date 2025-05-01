import os
import requests
import json

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_STORE_URL = os.getenv("SHOPIFY_STORE_URL")

HEADERS = {
    "X-Shopify-Access-Token": SHOPIFY_API_KEY,
    "Content-Type": "application/json"
}

def get_all_blog_ids():
    url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/blogs.json"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        blogs = response.json().get("blogs", [])
        return [b["id"] for b in blogs]
    print(f"❌ Error fetching blog list: {response.status_code}")
    return []

def get_blog_articles(blog_id, blog_handle):
    all_articles = []
    base_url = f"{SHOPIFY_STORE_URL}/admin/api/2024-01/blogs/{blog_id}/articles.json?limit=250"
    url = base_url

    while url:
        response = requests.get(url, headers=HEADERS)
        if response.status_code != 200:
            print(f"❌ Error fetching articles for blog ID {blog_id}: {response.status_code} — {response.text}")
            break

        articles = response.json().get("articles", [])
        for art in articles:
            if art.get("published_at"):
                all_articles.append({
                    "title": art.get("title"),
                    "content": art.get("body_html"),
                    "tags": art.get("tags"),
                    "author": art.get("author"),
                    "url": f"{SHOPIFY_STORE_URL}/blogs/{blog_handle}/{art.get('handle')}"
                })

        link_header = response.headers.get("Link", "")
        if 'rel="next"' in link_header:
            parts = link_header.split(",")
            next_link = next((p.split(";")[0].strip("<> ") for p in parts if 'rel="next"' in p), None)
            url = next_link
        else:
            url = None

    return all_articles

def save_articles(data):
    with open("articles.json", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved articles: {len(data)} in articles.json")

if __name__ == "__main__":
    all_articles = []
    blog_ids = get_all_blog_ids()
    for blog_id in blog_ids:
        print(f"🔍 Fetching articles for blog ID {blog_id}")

        # Get blog handle
        blog_resp = requests.get(f"{SHOPIFY_STORE_URL}/admin/api/2024-01/blogs/{blog_id}.json", headers=HEADERS)
        if blog_resp.status_code != 200:
            print(f"❌ Could not get blog handle for {blog_id}")
            continue

        blog_handle = blog_resp.json().get("blog", {}).get("handle", "news")

        # Get articles based on handle
        articles = get_blog_articles(blog_id, blog_handle)
        all_articles.extend(articles)

    save_articles(all_articles)
