#!/usr/bin/env python3
"""
7_embeddings.py

A collection of functions and a CLI to compute embeddings and query ChromaDB
for a Retrieval-Augmented Generation (RAG) system.
The script reads the OpenAI API key from a file defined in the constants section.

It returns a hybrid JSON result that includes:
  - "combined_context": a concatenation of the top matching document texts.
  - "documents": a list of candidate documents (each with "text", "similarity_score", and "metadata").

Examples:
    python3 7_embeddings.py --text "Hello world"
    python3 7_embeddings.py --text "Some query"
"""

import argparse
import logging
import os
import sys
import json
from typing import List

import numpy as np
import openai

# Try importing tiktoken for token counting
try:
    import tiktoken
except ImportError:
    tiktoken = None
    logging.warning("tiktoken is not installed. Token counting will not work.")


# ====================
# Constants
# ====================

# Script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# API key file (located one level above the folder of the script)
API_KEY_FILE_PATH = os.path.join(SCRIPT_DIR, "..", "openai_api.key")

# ChromaDB settings
CHROMA_EMBEDDINGS_FOLDER = os.path.join(SCRIPT_DIR, "..", "embeddings", "chroma_db")
COLLECTION_NAME = "text_embeddings"  # Updated collection name

# Embeddings model
DEFAULT_EMBEDDINGS_MODEL = "text-embedding-3-small"

# Maximum number of characters to output for truncated strings in logs
MAX_OUTPUT_LENGTH = 100

# Number of top results to return from ChromaDB
TOP_N = 3

# ====================
# Logging configuration
# ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
# Suppress PostHog logging (used for telemetry in chromadb) to avoid connection error messages.
logging.getLogger("posthog").setLevel(logging.CRITICAL)


# ====================
# Utility Functions
# ====================

def load_api_key(filename: str) -> str:
    """
    Load the OpenAI API key from the given file.
    """
    try:
        with open(filename, "r", encoding="utf-8") as file:
            key = file.read().strip()
            logging.info(f"API key loaded from {filename}.")
            return key
    except Exception as e:
        logging.error(f"Error loading API key: {e}")
        raise

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Compute the cosine similarity between two vectors.
    """
    v1 = np.array(v1)
    v2 = np.array(v2)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def compute_embedding(api_key: str, text: str, log_embedding: bool = True) -> List[float]:
    """
    Compute the embedding for a given text using OpenAI's embeddings API.
    
    Args:
        api_key (str): The OpenAI API key.
        text (str): The text to embed.
        log_embedding (bool): Whether to log embedding details.
    
    Returns:
        List[float]: The embedding vector (1D).
    """
    openai.api_key = api_key
    try:
        response = openai.embeddings.create(
            model=DEFAULT_EMBEDDINGS_MODEL,
            input=[text]
        )
        embedding = response.data[0].embedding
        if log_embedding:
            logging.info(f"Computed embedding: dimension = {len(embedding)}, first 5 values = {embedding[:5]}")
        return embedding
    except Exception as e:
        logging.error(f"Error computing embedding: {e}")
        raise

def count_tokens(text: str, model: str = "gpt2") -> int:
    """
    Count the number of tokens in the given text using tiktoken.
    
    Args:
        text (str): The text to count tokens for.
        model (str): The model encoding to use. Default is "gpt2".
    
    Returns:
        int: The number of tokens.
    """
    if tiktoken is None:
        logging.warning("tiktoken not installed; cannot count tokens.")
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("gpt2")
    return len(encoding.encode(text))


# ====================
# ChromaDB Query Functions
# ====================

def query_chroma_db(query: str, api_key: str, top_n: int = TOP_N) -> dict:
    """
    Retrieve context from ChromaDB using the query.
    This function queries for the top-N matching documents, computes a cosine similarity
    for each candidate, and returns a hybrid JSON result suitable for a RAG system.
    
    Returns a dictionary with:
      - "combined_context": concatenated texts of the candidate documents.
      - "documents": list of candidate documents with keys "text", "similarity_score", and "metadata".
    """
    # Compute the query embedding (this logs one "Computed embedding" message)
    query_embedding = compute_embedding(api_key, query)
    try:
        import chromadb
        from chromadb.config import Settings

        # Ensure the persistence folder exists.
        os.makedirs(CHROMA_EMBEDDINGS_FOLDER, exist_ok=True)

        # Create the ChromaDB client with telemetry disabled.
        client = chromadb.PersistentClient(
            path=CHROMA_EMBEDDINGS_FOLDER,
            settings=Settings(anonymized_telemetry=False)
        )

        try:
            collection = client.get_collection(name=COLLECTION_NAME)
        except Exception:
            logging.info(f"Collection '{COLLECTION_NAME}' not found. Creating a new collection.")
            collection = client.create_collection(name=COLLECTION_NAME)

        # Query for the top N results; request documents, metadatas, and embeddings.
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_n,
            include=["documents", "metadatas", "embeddings"]
        )

        # Extract results (we expect list-of-lists)
        docs = results.get("documents", [[]])[0] if "documents" in results else []
        metas = results.get("metadatas", [[]])[0] if "metadatas" in results else []
        embs = results.get("embeddings", [[]])[0] if "embeddings" in results else []

        candidate_docs = []
        for i, doc in enumerate(docs):
            if i >= top_n:
                break
            metadata = metas[i] if (i < len(metas)) else {}
            # Assume chunk name is stored under "chunk_file" in metadata (if available)
            chunk_name = metadata.get("chunk_file", "<unknown>")
            if i < len(embs) and embs[i] is not None:
                candidate_embedding = embs[i]
            else:
                candidate_embedding = compute_embedding(api_key, doc, log_embedding=False)

            candidate_embedding = np.array(candidate_embedding)
            if candidate_embedding.ndim == 2:
                logging.warning(f"Document {i} embedding is 2D. Taking the first row. shape={candidate_embedding.shape}")
                candidate_embedding = candidate_embedding[0]

            similarity_score = cosine_similarity(query_embedding, candidate_embedding)

            # Log the chunk name, similarity (3 decimals), and token count for the document
            token_count = count_tokens(doc)
            logging.info(f"Document {i} chunk='{chunk_name}' similarity={similarity_score:.3f} tokens={token_count}")

            candidate_docs.append({
                "text": doc,
                "similarity_score": similarity_score,
                "metadata": metadata
            })

        # Sort candidate docs by similarity (highest first)
        candidate_docs.sort(key=lambda x: x["similarity_score"], reverse=True)
        combined_context = "\n".join([doc["text"] for doc in candidate_docs])

        # Log only the first 100 characters of the merged document along with its token count
        merged_tokens = count_tokens(combined_context)
        logging.info(f"Merged doc (truncated 100 chars): {combined_context[:MAX_OUTPUT_LENGTH]}")
        logging.info(f"Merged doc token count: {merged_tokens}")

        return {
            "combined_context": combined_context,
            "documents": candidate_docs
        }

    except Exception as e:
        logging.error(f"Error querying ChromaDB: {e}")
        return {}

def retrieve_context(query: str, api_key: str) -> dict:
    """
    Wrapper function to retrieve context using ChromaDB.
    """
    return query_chroma_db(query, api_key)

# ====================
# Custom Argument Parser
# ====================

class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Print the full help (including epilog) then the error message.
        self.print_help(sys.stderr)
        self.exit(2, f"\n{self.prog}: error: {message}\n")

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments for this script.
    """
    parser = CustomArgumentParser(
        description="Compute embeddings and query ChromaDB for a RAG system.",
        epilog=("Examples:\n"
                "  python3 7_embeddings.py --text \"Hello world\"\n"
                "  python3 7_embeddings.py --text \"Some query\""),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--text",
        type=str,
        required=True,
        help="Text input to embed and use as a query for ChromaDB."
    )
    return parser.parse_args()

# ====================
# Main Function
# ====================

def main():
    args = parse_arguments()
    api_key = load_api_key(API_KEY_FILE_PATH)
    result = query_chroma_db(args.text, api_key, top_n=TOP_N)
    return result

if __name__ == "__main__":
    # When running as a script, call main() (which returns the JSON result)
    _ = main()