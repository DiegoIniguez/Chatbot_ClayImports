import json
import joblib

with open("collections_described.json", "r", encoding="utf-8") as f:
    enriched_collections = json.load(f)

joblib.dump(enriched_collections, "cached_collections.joblib")
print(f"✅ Cache regenerated with {len(enriched_collections)} collections.")
