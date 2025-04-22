import requests
from bs4 import BeautifulSoup
import json

def scrape_clay_product(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ Failed to fetch page. Status code: {response.status_code}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    # Buscar JSON-LD correcto (tipo Product)
    scripts = soup.find_all("script", type="application/ld+json")
    product_data = None
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "Product":
                product_data = data
                break
        except Exception:
            continue

    if not product_data:
        print("❌ No se encontró JSON-LD tipo Product.")
        return {}

    title = product_data.get("name", "No title found")
    description = product_data.get("description", "No description found").strip()
    images = product_data.get("image", [])
    if not isinstance(images, list):
        images = [images]

    # Scrape de la sección USAGE
    usage_section = soup.find("details", id=lambda x: x and "collapsible_tab_Fy7pbk" in x)
    usage_text = usage_section.get_text(separator=" ", strip=True) if usage_section else "No usage info found"

    return {
        "title": title,
        "description": description,
        "usage": usage_text,
        "images": images
    }

if __name__ == "__main__":
    url = "https://clayimports.com/products/glazed-linen-2x6"
    data = scrape_clay_product(url)
    print("📦 Producto scrapeado:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
