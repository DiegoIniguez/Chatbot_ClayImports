
# 🧱 ClayBot - Proyecto Inteligente para Shopify Support

Bienvenido al proyecto **ClayBot**, un chatbot inteligente diseñado para mejorar la atención al cliente y navegación de productos en tiendas Shopify.

---

## 📦 Estructura General del Proyecto

| Categoría | Archivos | Descripción |
|----------|----------|-------------|
| 🤖 Core Bot | `server.py`, `bot.py` | Backend principal del chatbot |
| 🧠 Intent ML | `weekly_learning.py`, `check_duplicates.py`, `intent_model.joblib`, `training_data.json` | Clasificador de intención con aprendizaje semanal |
| 🧱 Colecciones/Productos | `export_collections_and_products.py`, `generate_collection_descriptions.py`, `regenerate_cache.py`, `products.json`, `collections_described.json`, `cached_collections.joblib` | Extracción y enriquecimiento de colecciones con OpenAI |
| 📄 Informational Pages | `utils.py`, `pages.json` | Descarga y cacheo de páginas de ayuda desde Shopify |
| 📰 Blog | `build_articles.py`, `articles.json` | Descarga y cacheo de artículos del blog de Shopify |
| 🔎 Page Matching | `page_scraper.py`, `smart_page_router.py` | Busca, scrapea y resume páginas de ayuda según intención |
| ⚙️ Automatización | `run_pipeline.py` | Ejecuta todo el flujo de entrenamiento, exportación y actualización |
| 🔐 Accesos | `google_credentials.json` | Registro de logs en Google Sheets |
| 🧹 Utilidades | `.gitignore`, `cleanup_vscode.sh` | Herramientas de entorno (opcional) |

---

## ✅ Flujo Recomendado (Manual o Automatizado)

### 🔁 Opción A: Todo automático
```bash
python3 run_pipeline.py
```

Este comando corre en orden:
1. 🧠 Reentrena intención (`weekly_learning.py`)
2. 🔍 Verifica duplicados (`check_duplicates.py`)
3. 🧱 Exporta datos (`export_collections_and_products.py`)
4. 🧠 Genera descripciones IA (`generate_collection_descriptions.py`)
5. 💾 Regenera caché del bot (`regenerate_cache.py`)
6. 📰 Actualiza artículos del blog (`build_articles.py`)

---

### 🧪 Opción B: Ejecución manual paso por paso

```bash
python3 weekly_learning.py
python3 check_duplicates.py
python3 export_collections_and_products.py
python3 generate_collection_descriptions.py
python3 regenerate_cache.py
python3 build_articles.py
```

---

## 🧠 Matching y scraping de páginas

ClayBot usa `page_scraper.py` y `smart_page_router.py` como módulos internos para:

- Scrapear contenido real de páginas Shopify (`/pages/...`).
- Limpiar HTML y contenido irrelevante.
- Resumir el contenido con OpenAI usando `text-embedding-3-small` y `gpt-4o-mini`.
- Mostrar el resumen al usuario con un enlace.

Esto ocurre automáticamente cuando un intent como `contact`, `shipping`, `our_story` o `search_pages` se detecta.

🔒 No necesitas correr estos scripts manualmente. Ya están integrados dentro del flujo de `server.py`.

---

## 📁 Archivos Generados Clave

- `collections.json` → export desde Shopify
- `products.json` → productos activos
- `collections_described.json` → colecciones enriquecidas
- `cached_collections.joblib` → caché del bot
- `intent_model.joblib` → clasificador actualizado
- `articles.json`, `pages.json` → contenido útil cacheado

---

## ⚠️ Notas Importantes

- **No borres `cached_collections.joblib`** a menos que lo regeneres.
- **Revisa `google_credentials.json` y tus variables de entorno antes de correr.**
- `utils.py` actualiza `pages.json` automáticamente desde `server.py`.
- No necesitas correr `page_scraper.py` manualmente. Está conectado a `search_shopify_pages()`.

---

## 🧠 ¿Qué sigue?

- Generar `collection_embeddings.json` para hacer matching semántico.
- Mejorar `run_pipeline.py` con lógica condicional y logging bonito.
- Sincronizar descripciones generadas con Shopify vía API si lo deseas.

---

Hecho con ❤️ para Clay Imports.
