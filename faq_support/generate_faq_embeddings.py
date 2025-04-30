from sentence_transformers import SentenceTransformer
import json
import torch
import os

# Cargar modelo
model = SentenceTransformer('all-MiniLM-L6-v2')

# Ruta del archivo de FAQs
FAQ_PATH = os.path.join(os.path.dirname(__file__), 'faqs_claybot.json')
with open(FAQ_PATH, 'r', encoding='utf-8') as f:
    faqs = json.load(f)

# Preparar textos para embedir: título + subtítulo + keywords
faq_texts = [
    f"{faq['title']} {faq['subtitle']} {' '.join(faq['keywords'])}" for faq in faqs
]

# Calcular embeddings
print("Calculando embeddings... 🚀")
faq_embeddings = model.encode(faq_texts, convert_to_tensor=True)

# Guardar embeddings en archivo .pt
output_path = os.path.join(os.path.dirname(__file__), 'faq_embeddings.pt')
torch.save(faq_embeddings, output_path)
print(f"✅ Embeddings guardados en {output_path}")