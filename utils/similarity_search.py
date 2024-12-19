import numpy as np
import faiss
import json

# Load embeddings and keys
def load_embeddings_and_keys(embeddings_file_path, keys_file_path):
    embeddings = np.load(embeddings_file_path)
    with open(keys_file_path, 'r') as f:
        keys = json.load(f)
    return embeddings, keys

# Setup FAISS index
def setup_faiss_index(embeddings):
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)  # Cosine similarity
    index.add(embeddings)
    return index

# Query FAISS for top-n similar graphs
def query_similarity_faiss(query, index, keys, query_embedding,model, top_k=3):
    query_embedding = model.encode(query).astype('float32').reshape(1, -1)
    scores, indices = index.search(query_embedding, top_k)
    matches = [(keys[indices[0][i]], scores[0][i]) for i in range(len(indices[0]))]
    return matches

def get_urls_of_documents()-> dict: 
    document_urls = {
        "FATF Rec": "https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Fatf-recommendations.html",
        "AMLD5": "https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:32018L0843",
        "AMLD6": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A52021PC0423",
        "FATF Sanctions": "https://www.fatf-gafi.org/en/publications/Fatfrecommendations/Bpp-finsanctions-tf-r6.html",
        "MICA": "https://eur-lex.europa.eu/eli/reg/2023/1114/oj",
        "EU Sanctions": "https://finance.ec.europa.eu/document/download/803d74d5-84a0-4bf4-a735-30f1fe5ae6dd_en?filename=national-competent-authorities-sanctions-implementation_en.pdf"
        }
    return document_urls