
import os
import subprocess
import hashlib
import datetime

def hash_file(path):
    hasher = hashlib.md5()
    try:
        with open(path, "rb") as afile:
            buf = afile.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except FileNotFoundError:
        return None

HASH_PATH = "collections_described.hash"

def should_regenerate_cache():
    current_hash = hash_file("collections_described.json")
    if not current_hash:
        print("⚠️ Couldn't find collections_described.json.")
        return False

    if not os.path.exists(HASH_PATH):
        with open(HASH_PATH, "w") as f:
            f.write(current_hash)
        return True

    with open(HASH_PATH, "r") as f:
        last_hash = f.read().strip()

    if current_hash != last_hash:
        with open(HASH_PATH, "w") as f:
            f.write(current_hash)
        return True

    print("💾 No changes to collections_described.json. Skipping cache regeneration.")
    return False

log_file = f"pipeline_log_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

def run_script(label, script):
    print(f"🔄 {label} - {script}")
    try:
        subprocess.run(["python3", script], check=True)
        print(f"✅ {label} - done\n")
        return f"✅ {label} - SUCCESS"
    except subprocess.CalledProcessError:
        print(f"❌ {label} - failed\n")
        return f"❌ {label} - FAILED"

# Script pipeline
pipeline = [
    ("🧠 ML Retraining", "weekly_learning.py"),
    ("🧼 Duplicate Check", "check_duplicates.py"),
    ("📦 Export Collections + Products", "export_collections_and_products.py"),
    ("🧠 Generate Collection Descriptions", "generate_collection_descriptions.py"),
    ("📰 Update Blog Articles", "build_articles.py")
]

results = []

# Run normal scripts
for label, script in pipeline:
    result = run_script(label, script)
    results.append(result)

# Regenerate cache only if collections_described.json changed
if should_regenerate_cache():
    result = run_script("💾 Regenerate Cache", "regenerate_cache.py")
    results.append(result)

# Save log
with open(log_file, "w") as log:
    for line in results:
        log.write(line + "\n")

print(f"📘 Log guardado en {log_file}")
