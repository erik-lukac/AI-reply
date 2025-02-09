#!/usr/bin/env python3
"""
4_create_embedding_to_chromaDB.py

This script:
  - Reads .txt files from a directory ("chunks" by default).
  - Generates embeddings using OpenAI's new embeddings API (default: "text-embedding-3-small").
  - Applies L2 normalization to those embeddings.
  - Stores the embeddings directly in a ChromaDB collection.
  - Clears the existing collection by default.
  - Logs an overall summary of pre- and post- normalization norms.

Usage:
    python 4_create_embedding_to_chromaDB.py
      --input-dir <some_directory>
      --model <openai_embedding_model>

Defaults:
    --input-dir = "chunks"
    --model = "text-embedding-3-small"

Example:
    python 4_create_embedding_to_chromaDB.py --input-dir my_chunks --model text-embedding-3-small
"""

import os
import sys
import math
import logging
import argparse
from typing import List, Dict, Any

import openai
import chromadb
from chromadb.config import Settings

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------
DEFAULT_INPUT_DIR = "chunks"               # where chunk .txt files are stored
DEFAULT_MODEL = "text-embedding-3-small"   # default embedding model
CHROMA_DB_DIR = "chroma_db"                # folder for ChromaDB persistent store
COLLECTION_NAME = "text_embeddings"        # name of the ChromaDB collection
CLEAR_DB = True                            # clear the existing collection first
API_KEY_PATH = "../openai_api.key"         # path to your OpenAI API key file

# -----------------------------------------------------------------------------
# LOGGING CONFIG
# -----------------------------------------------------------------------------
# Keep it at INFO to ensure we see the summary log without switching to DEBUG
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------
def load_api_key(api_key_path: str = API_KEY_PATH) -> str:
    """
    Loads the OpenAI API key from a file.
    """
    try:
        with open(api_key_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logging.error(f"Failed to load API key from {api_key_path}: {e}")
        sys.exit(1)

def get_embedding(text: str, model: str) -> List[float]:
    """
    Generates an embedding vector for 'text' using the OpenAI Embeddings API.
    Uses the new method: openai.embeddings.create(input=..., model=...).

    Args:
        text (str): The text to embed.
        model (str): The OpenAI embedding model name.

    Returns:
        List[float]: The embedding vector.
    """
    response = openai.embeddings.create(input=text, model=model)
    return response.data[0].embedding

def l2_normalize(vector: List[float]) -> (List[float], float, float):
    """
    Applies L2 normalization to the input vector (v -> v / ||v||).
    Returns:
      - normalized_vector
      - norm_before
      - norm_after
    """
    norm_before = math.sqrt(sum(x*x for x in vector))
    if norm_before == 0.0:
        # Return the vector as-is and norm_after=0 if it's entirely zeros
        return vector, norm_before, 0.0

    normalized_vector = [x / norm_before for x in vector]
    norm_after = math.sqrt(sum(x*x for x in normalized_vector))
    return normalized_vector, norm_before, norm_after

def read_and_embed_chunks(input_dir: str, model: str) -> List[Dict[str, Any]]:
    """
    Reads each .txt file in 'input_dir', generates an L2-normalized embedding,
    and returns a list of dicts with the structure:
      {
        "document": <text content>,
        "embedding": <list of floats>,
        "metadata": {
            "chunk_file": <filename>,
            "token_count": <approx word count>
        }
      }

    Args:
        input_dir (str): Directory containing the .txt chunks.
        model (str): OpenAI embedding model name.
    """
    logging.info(f"Reading chunk files from: {input_dir}")
    if not os.path.isdir(input_dir):
        logging.error(f"Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    chunk_files = sorted(
        [f for f in os.listdir(input_dir) if f.lower().endswith(".txt")]
    )
    if not chunk_files:
        logging.warning(f"No .txt files found in directory '{input_dir}'.")
        return []

    # For a final summary of norms
    pre_norms = []
    post_norms = []

    all_data = []
    for idx, filename in enumerate(chunk_files):
        file_path = os.path.join(input_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
            continue

        try:
            embedding_raw = get_embedding(text, model)
            embedding_normalized, norm_before, norm_after = l2_normalize(embedding_raw)
            pre_norms.append(norm_before)
            post_norms.append(norm_after)
        except Exception as e:
            logging.error(f"Error generating embedding for {filename}: {e}")
            continue

        token_count = len(text.split())
        logging.info(f"Processed '{filename}' (~{token_count} words).")

        all_data.append({
            "document": text,
            "embedding": embedding_normalized,
            "metadata": {
                "chunk_file": filename,
                "token_count": token_count
            }
        })

    # Log a summary of norms at INFO level
    if pre_norms and post_norms:
        avg_pre = sum(pre_norms) / len(pre_norms)
        avg_post = sum(post_norms) / len(post_norms)
        min_post = min(post_norms)
        max_post = max(post_norms)
        logging.info(
            f"Normalization summary for {len(pre_norms)} embeddings: "
            f"Average pre-norm={avg_pre:.4f}, Average post-norm={avg_post:.4f}, "
            f"Min post-norm={min_post:.4f}, Max post-norm={max_post:.4f}"
        )

    return all_data

def store_in_chromadb(
    embeddings: List[Dict[str, Any]],
    db_dir: str,
    collection_name: str,
    clear_collection: bool = True
) -> None:
    """
    Stores a list of embeddings in a ChromaDB collection.

    Args:
        embeddings (List[Dict[str, Any]]): Embeddings data to store.
        db_dir (str): Directory for the ChromaDB persistent store.
        collection_name (str): Name of the ChromaDB collection.
        clear_collection (bool): Whether to clear the collection before insertion.
    """
    if not embeddings:
        logging.warning("No embeddings to store in ChromaDB.")
        return

    # Initialize ChromaDB client
    client = chromadb.PersistentClient(
        path=db_dir,
        settings=Settings(anonymized_telemetry=False)
    )

    # Get or create the collection
    collection = client.get_or_create_collection(name=collection_name)
    logging.info(f"Using ChromaDB collection: '{collection_name}'")

    # Clear existing entries if requested
    if clear_collection:
        existing = collection.get()
        if "ids" in existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            logging.info(f"Cleared existing collection '{collection_name}'.")

    # Prepare data for bulk insertion
    ids = []
    documents = []
    vectors = []
    metadatas = []
    for i, item in enumerate(embeddings):
        ids.append(f"doc_{i}")
        documents.append(item["document"])
        vectors.append(item["embedding"])
        metadatas.append(item["metadata"])

    # Insert in bulk
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=vectors,
        metadatas=metadatas
    )
    logging.info(f"Added {len(embeddings)} items to the '{collection_name}' collection.")

def main():
    parser = argparse.ArgumentParser(
        description="Generate L2-normalized embeddings from local .txt files and store them in ChromaDB."
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing .txt files. Defaults to '{DEFAULT_INPUT_DIR}'."
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"OpenAI embedding model. Defaults to '{DEFAULT_MODEL}'."
    )
    args = parser.parse_args()

    # Load OpenAI API key
    openai.api_key = load_api_key()

    # Step 1: Read files and generate embeddings (L2-normalized)
    embeddings_data = read_and_embed_chunks(args.input_dir, args.model)

    # Step 2: Store embeddings in ChromaDB
    store_in_chromadb(
        embeddings=embeddings_data,
        db_dir=CHROMA_DB_DIR,
        collection_name=COLLECTION_NAME,
        clear_collection=CLEAR_DB
    )

if __name__ == "__main__":
    main()