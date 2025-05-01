import json
from collections import defaultdict
from difflib import SequenceMatcher

TRAINING_FILE = "training_data.json"
SIMILARITY_THRESHOLD = 0.85  # Adjust between 0.7 and 0.95 depending on how strict you want it

def load_training_data():
    with open(TRAINING_FILE, "r") as f:
        return json.load(f)

def find_exact_duplicates(data):
    phrase_to_intents = defaultdict(set)

    for entry in data:
        intent = entry["intent"]
        for phrase in entry["examples"]:
            clean = phrase.strip().lower()
            phrase_to_intents[clean].add(intent)

    return {p: i for p, i in phrase_to_intents.items() if len(i) > 1}

def find_fuzzy_conflicts(data, threshold=SIMILARITY_THRESHOLD):
    all_phrases = []

    for entry in data:
        intent = entry["intent"]
        for phrase in entry["examples"]:
            clean = phrase.strip().lower()
            all_phrases.append((clean, intent))

    fuzzy_conflicts = []
    for i, (phrase1, intent1) in enumerate(all_phrases):
        for phrase2, intent2 in all_phrases[i+1:]:
            if intent1 != intent2:
                ratio = SequenceMatcher(None, phrase1, phrase2).ratio()
                if ratio >= threshold:
                    fuzzy_conflicts.append((phrase1, intent1, phrase2, intent2, round(ratio, 2)))

    return fuzzy_conflicts

def main():
    data = load_training_data()

    print("🔎 Checking for exact duplicates across intents...")
    exact = find_exact_duplicates(data)
    if exact:
        print("⚠️ Exact duplicates found:")
        for phrase, intents in exact.items():
            print(f' - "{phrase}" in intents: {", ".join(intents)}')
    else:
        print("✅ No exact duplicates.")

    print("\n🔍 Checking for similar phrases across intents...")
    fuzzy = find_fuzzy_conflicts(data)
    if fuzzy:
        print(f"⚠️ Found {len(fuzzy)} fuzzy conflicts:")
        for p1, i1, p2, i2, score in fuzzy:
            print(f' - "{p1}" ({i1}) vs "{p2}" ({i2}) → similarity: {score}')
    else:
        print("✅ No fuzzy duplicates detected.")

if __name__ == "__main__":
    main()
