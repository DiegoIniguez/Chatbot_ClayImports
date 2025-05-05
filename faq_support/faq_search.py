from sentence_transformers import SentenceTransformer, util
import json
import torch
import os
import openai
import traceback
import tiktoken
import re
from bs4 import BeautifulSoup

model = SentenceTransformer('all-MiniLM-L6-v2')

def clean_faq_answer(answer, max_lines=5):
    # Removes HTML tags
    cleaned = BeautifulSoup(answer, "html.parser").get_text()

    # Replace line breaks with <br> and clean spaces
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    limited_lines = lines[:max_lines]
    return "<br>".join(limited_lines)

FAQ_PATH = os.path.join(os.path.dirname(__file__), 'faqs_claybot.json')
with open(FAQ_PATH, 'r', encoding='utf-8') as f:
    faqs = json.load(f)

EMBEDDINGS_PATH = os.path.join(os.path.dirname(__file__), 'faq_embeddings.pt')
faq_embeddings = torch.load(EMBEDDINGS_PATH)

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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

def fallback_faq_ai(user_message):
    query_embedding = model.encode(user_message, convert_to_tensor=True)
    hits = util.semantic_search(query_embedding, faq_embeddings, top_k=5)[0]

    encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
    max_tokens = 3000
    current_tokens = 0
    selected_faqs = []

    for hit in hits:
        faq = faqs[hit['corpus_id']]
        faq_text = f"Q: {faq['title']}\nA: {faq['answer']}\n\n"
        token_count = len(encoder.encode(faq_text))
        if current_tokens + token_count > max_tokens:
            break
        selected_faqs.append((faq_text, faq))
        current_tokens += token_count

    if not selected_faqs:
        return "Sorry, I couldn't find a relevant answer."

    faqs_text = "".join([f[0] for f in selected_faqs])
    prompt = (
        "You are a support assistant for Clay Imports. Only answer based on the following FAQs.\n"
        "If the user's question is unrelated, reply with 'Sorry, I can't help with that.'\n"
        f"FAQs:\n{faqs_text}\n"
        f"User: {user_message}\nAssistant:"
    )

    print("🧾 Prompt length (tokens):", len(encoder.encode(prompt)))

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=250
        )
        content = response.choices[0].message.content.strip()
        if content and "Sorry" not in content:
            return content
        else:
            top_faq = selected_faqs[0][1]
            return (
                "Hmm 🤔 I couldn't find an exact match, but this might help:\n\n"
                f"<b>{top_faq['title']}</b><br>{top_faq['subtitle']}<br><br>"
                f"{clean_faq_answer(top_faq['answer'])}<br><br>"
                f"<a href='{top_faq['url']}' target='_blank' style='color: #007bff; text-decoration: underline;'>View FAQ</a><br><br>"
                "You can also try rephrasing your question if this isn’t what you need."
            )
    except Exception as e:
        print(f"❌ OpenAI fallback failed: {e}")
        return "Sorry, I couldn't find a relevant answer."

def get_best_faq_answer(user_message):
    result = search_faq_semantic(user_message)
    if result:
        return {
            "source": "semantic",
            "answer": (
                f"<b>{result['title']}</b><br>{result['subtitle']}<br><br>"
                f"{clean_faq_answer(result['answer'])}<br><br>"
                f"<a href='{result['url']}' target='_blank' style='color: #007bff; text-decoration: underline;'>View FAQ</a>"
            )
        }
    else:
        ai_answer = fallback_faq_ai(user_message)
        return {
            "source": "ai",
            "answer": ai_answer
        }
