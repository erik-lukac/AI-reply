#!/usr/bin/env python3
"""
6_chromaDB.py

This script loads text chunks and their vector embeddings from a CSV file
and stores them in a ChromaDB collection for similarity search.

The CSV is expected to have three columns:
    chunk_file: The filename of the text chunk.
    token_count: The number of tokens in the chunk.
    embedding: A string representation of a list of floats (e.g. "[0.12, 0.34, 0.56, 0.78]").

Example CSV row:
    dfs_cleanup_deduplicated_chunk_001.txt,123,"[0.12, 0.34, 0.56, 0.78]"

Constants (update these as needed):
    CSV_PATH: Path to the embeddings CSV file.
    CHUNKS_DIR: Directory where the chunk text files are stored.
    DB_DIR: Directory for the ChromaDB persistent store.
    COLLECTION_NAME: Name of the ChromaDB collection.
    CLEAR_COLLECTION: Whether to clear the collection before inserting new embeddings.

Usage:
    python 6_chromaDB.py
"""

import os
import logging
import ast
from typing import List, Dict, Any

import pandas as pd
import chromadb
from chromadb.config import Settings  # Import Settings to configure telemetry

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------
CSV_PATH: str = "embeddings.csv"          # Path to the CSV file
CHUNKS_DIR: str = "chunks"                # Directory containing the chunk text files
DB_DIR: str = "chroma_db"                 # Directory for storing ChromaDB data
COLLECTION_NAME: str = "text_embeddings"  # Name of the ChromaDB collection
CLEAR_COLLECTION: bool = True             # Clear the collection before inserting new embeddings

# -----------------------------------------------------------------------------
# LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# -----------------------------------------------------------------------------
# FUNCTIONS
# -----------------------------------------------------------------------------
def load_embeddings(csv_path: str, chunks_dir: str) -> List[Dict[str, Any]]:
    """
    Load embeddings from a CSV file with the structure:
        chunk_file, token_count, embedding

    For each row, this function:
      - Reads the text from the file specified in the 'chunk_file' column.
      - If the file is not found at the provided path, it will look inside chunks_dir.
      - Parses the 'embedding' field into a list of floats.
      - Keeps the token_count as metadata.

    Args:
        csv_path (str): Path to the CSV file.
        chunks_dir (str): Directory where chunk files are stored.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries where each dictionary contains:
            - 'document': The text content of the chunk.
            - 'embedding': The embedding vector (list of floats).
            - 'metadata': A dict with additional metadata (token_count and chunk_file).
    """
    logging.info(f"Loading embeddings from CSV file: {csv_path}")
    df = pd.read_csv(csv_path)

    # Ensure required columns are present.
    required_columns = {"chunk_file", "token_count", "embedding"}
    if not required_columns.issubset(df.columns):
        raise ValueError(f"CSV file must contain the columns: {required_columns}")

    data: List[Dict[str, Any]] = []

    for index, row in df.iterrows():
        file_path: str = row["chunk_file"]
        token_count: int = int(row["token_count"])
        embedding_str: str = row["embedding"]

        # Parse the embedding string into a list of floats.
        try:
            embedding: List[float] = ast.literal_eval(embedding_str)
        except Exception as e:
            logging.error(f"Error parsing embedding at row {index}: {e}")
            continue

        # Check if the chunk file exists; if not, try looking in the chunks_dir.
        if not os.path.exists(file_path):
            alt_file_path = os.path.join(chunks_dir, file_path)
            if os.path.exists(alt_file_path):
                file_path = alt_file_path
            else:
                logging.error(f"Chunk file '{row['chunk_file']}' does not exist (row {index}).")
                continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text: str = f.read().strip()
        except Exception as e:
            logging.error(f"Error reading file '{file_path}' at row {index}: {e}")
            continue

        data.append({
            "document": text,
            "embedding": embedding,
            "metadata": {
                "token_count": token_count,
                "chunk_file": file_path
            }
        })

    logging.info(f"Successfully loaded {len(data)} embeddings from CSV.")
    return data


def store_in_chromadb(embeddings: List[Dict[str, Any]], db_dir: str, collection_name: str, clear_collection: bool) -> None:
    """
    Store a list of embeddings into a ChromaDB collection.

    Args:
        embeddings (List[Dict[str, Any]]): List of dictionaries containing the document text,
            its embedding vector, and metadata.
        db_dir (str): Directory path for the ChromaDB persistent store.
        collection_name (str): Name of the collection where embeddings will be stored.
        clear_collection (bool): If True, clear the collection before inserting new embeddings.
    """
    logging.info("Initializing ChromaDB client...")
    # Pass a Settings object to disable telemetry.
    client = chromadb.PersistentClient(
        path=db_dir,
        settings=Settings(
            anonymized_telemetry=False
        )
    )

    # Create or retrieve the collection.
    collection = client.get_or_create_collection(name=collection_name)
    logging.info(f"Using collection: '{collection_name}'")

    if clear_collection:
        # Retrieve all current IDs and delete them to clear the collection.
        existing = collection.get()
        if "ids" in existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
            logging.info(f"Cleared existing collection '{collection_name}'.")

    # Prepare lists for bulk insertion.
    ids: List[str] = []
    documents: List[str] = []
    vectors: List[List[float]] = []
    metadatas: List[Dict[str, Any]] = []

    for i, item in enumerate(embeddings):
        ids.append(f"doc_{i}")
        documents.append(item["document"])
        vectors.append(item["embedding"])
        metadatas.append(item["metadata"])

    # Add all embeddings to the collection in a single bulk operation.
    collection.add(
        ids=ids,
        documents=documents,
        embeddings=vectors,
        metadatas=metadatas
    )

    logging.info(f"Added {len(embeddings)} embeddings to the ChromaDB collection '{collection_name}'.")


def main() -> None:
    """
    Main function that loads embeddings from the CSV and stores them in ChromaDB.
    """
    # Verify the CSV file exists.
    if not os.path.exists(CSV_PATH):
        logging.error(f"CSV file '{CSV_PATH}' not found. Exiting.")
        return

    # Load embeddings from CSV.
    embeddings = load_embeddings(CSV_PATH, CHUNKS_DIR)
    if not embeddings:
        logging.error("No valid embeddings were loaded. Exiting.")
        return

    # Store the loaded embeddings in ChromaDB.
    store_in_chromadb(embeddings, DB_DIR, COLLECTION_NAME, CLEAR_COLLECTION)
    logging.info("ChromaDB has been populated successfully.")


if __name__ == "__main__":
    main()