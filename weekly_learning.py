import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import classification_report
import joblib

# 📁 ARCHIVO DE DATOS
TRAINING_FILE = "training_data.json"
MODEL_FILE = "intent_model.joblib"
GOOGLE_SHEET_NAME = "Chatbot logs"

# 🔐 AUTENTICACIÓN GOOGLE SHEETS
def load_logs():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    return sheet.get_all_records()

# 📊 CARGAR EJEMPLOS EXISTENTES
def load_existing_examples():
    try:
        with open(TRAINING_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# 🧠 DETECTAR EJEMPLOS NUEVOS
def extract_new_training_examples(logs, known_examples):
    # Recolectar todos los textos ya conocidos desde el formato agrupado
    known_phrases = set()
    for group in known_examples:
        known_phrases.update(group["examples"])

    new_data = []
    for entry in logs:
        msg = entry.get('User Message', '').strip()
        intent = entry.get('Intent', '').strip()
        if intent and msg and msg not in known_phrases:
            new_data.append((msg, intent))
    return new_data


# 💾 GUARDAR EN ARCHIVO JSON
def append_to_training_data(new_examples, existing):
    intent_map = {group["intent"]: set(group["examples"]) for group in existing}

    for msg, intent in new_examples:
        if intent in intent_map:
            intent_map[intent].add(msg)
        else:
            intent_map[intent] = {msg}

    # Volver a formato de lista para guardar
    updated_data = [{"intent": intent, "examples": list(examples)} for intent, examples in intent_map.items()]

    with open(TRAINING_FILE, "w") as f:
        json.dump(updated_data, f, indent=2)

    print(f"✅ {len(new_examples)} nuevos ejemplos añadidos al training_data.json")


def retrain_intent_model(training_data):
    X = []
    y = []
    for entry in training_data:
        intent = entry["intent"]
        for example in entry["examples"]:
            X.append(example)
            y.append(intent)

    model = make_pipeline(TfidfVectorizer(), MultinomialNB())
    model.fit(X, y)

    joblib.dump(model, MODEL_FILE)
    print(f"🎉 Modelo reentrenado y guardado como {MODEL_FILE}")

    return model, X, y  # ← 🔥 Retornamos para evaluar luego



# 🚀 FLUJO PRINCIPAL
def main():
    print("🔄 Iniciando entrenamiento semanal...")
    logs = load_logs()
    existing = load_existing_examples()
    new_examples = extract_new_training_examples(logs, existing)
    print(f"🆕 Nuevos ejemplos detectados: {len(new_examples)}")
    for msg, intent in new_examples:
        print(f"➕ {msg} → {intent}")


    if new_examples:
        append_to_training_data(new_examples, existing)
        model, X, y = retrain_intent_model(existing + new_examples)
    else:
        print("📭 No se encontraron nuevos ejemplos para añadir.")
        model, X, y = retrain_intent_model(existing)

    # Ahora sí puedes imprimir el reporte
    print("\n📊 Modelo de intención entrenado:")
    print(classification_report(y, model.predict(X)))

if __name__ == "__main__":
    main()
    print(f"\n📚 Total ejemplos en training_data.json: {len(load_existing_examples())}")
