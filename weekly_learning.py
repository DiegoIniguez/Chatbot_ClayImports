import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import classification_report
import joblib

# 📁 DATA FILES
TRAINING_FILE = "training_data.json"
MODEL_FILE = "intent_model.joblib"
GOOGLE_SHEET_NAME = "Chatbot logs"

# 🔐 GOOGLE SHEETS AUTHENTICATION
def load_logs():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    return sheet.get_all_records()

# 📊 LOAD EXISTING EXAMPLES
def load_existing_examples():
    try:
        with open(TRAINING_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# 🧠 DETECT NEW EXAMPLES
def extract_new_training_examples(logs, known_examples):
    # Collect all known texts from grouped format
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


# 💾 SAVED INTO A JSON FILE
def append_to_training_data(new_examples, existing):
    intent_map = {group["intent"]: set(group["examples"]) for group in existing}

    for msg, intent in new_examples:
        if intent in intent_map:
            intent_map[intent].add(msg)
        else:
            intent_map[intent] = {msg}

    # Return to list format to save
    updated_data = [{"intent": intent, "examples": list(examples)} for intent, examples in intent_map.items()]

    with open(TRAINING_FILE, "w") as f:
        json.dump(updated_data, f, indent=2)

    print(f"✅ {len(new_examples)} new examples added to training_data.json")


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
    print(f"🎉 Model retrained and saved as {MODEL_FILE}")

    return model, X, y

# 🚀 MAIN FLOW
def main():
    print("🔄 Starting weekly training...")
    logs = load_logs()
    existing = load_existing_examples()
    new_examples = extract_new_training_examples(logs, existing)
    print(f"🆕 New examples added: {len(new_examples)}")
    for msg, intent in new_examples:
        print(f"➕ {msg} → {intent}")


    if new_examples:
        append_to_training_data(new_examples, existing)
        model, X, y = retrain_intent_model(existing + new_examples)
    else:
        print("📭 No new examples were found to add.")
        model, X, y = retrain_intent_model(existing)

    print("\n📊 Trained intent model:")
    print(classification_report(y, model.predict(X)))

if __name__ == "__main__":
    main()
    print(f"\n📚 Total examples in training_data.json: {len(load_existing_examples())}")
