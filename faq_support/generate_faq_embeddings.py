from sentence_transformers import SentenceTransformer
import json
import torch
import os

# Load model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Path to FAQS file
FAQ_PATH = os.path.join(os.path.dirname(__file__), 'faqs_claybot.json')
with open(FAQ_PATH, 'r', encoding='utf-8') as f:
    faqs = json.load(f)

faq_texts = [
    f"{faq['title']} {faq['subtitle']} {' '.join(faq['keywords'])}" for faq in faqs
]

# Calculate embeddings
print("Calculating embeddings... 🚀")
faq_embeddings = model.encode(faq_texts, convert_to_tensor=True)

# Save embeddings in .pt file
output_path = os.path.join(os.path.dirname(__file__), 'faq_embeddings.pt')
torch.save(faq_embeddings, output_path)
print(f"✅ Embeddings saved in {output_path}")