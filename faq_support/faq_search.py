from sentence_transformers import SentenceTransformer, util
import json
import torch
import os

model = SentenceTransformer('all-MiniLM-L6-v2')

FAQ_PATH = os.path.join(os.path.dirname(__file__), 'faqs_claybot.json')
with open(FAQ_PATH, 'r', encoding='utf-8') as f:
    faqs = json.load(f)

EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), 'faq_embeddings.pt')
faq_embeddings = torch.load(EMBEDDINGS_PATH)

def search_faq_semantic(user_message, top_k=1):
    query_embedding = model.encode(user_message, convert_to_tensor=True)
    hits = util.semantic_search(query_embedding, faq_embeddings, top_k=top_k)[0]

    if hits and hits[0]['score'] > 0.5:
        match = faqs[hits[0]['corpus_id']]
        return {
            "title": match['title'],
            "subtitle": match['subtitle'],
            "answer": match['answer'],
            "url": match['url'],
            "score": hits[0]['score']
        }
    return None