#!/usr/bin/env python3
"""
5_embedings.py

This script reads text chunk files (stored in the "chunks" folder), generates embeddings
for each chunk using OpenAI's embedding API (default model: text-embedding-3-small),
and writes the resulting data to a CSV file.

The OpenAI API key is loaded from a file located one level up ("../openai_api.key").

Usage:
    python3 5_embedings.py --input-dir chunks --output-file embeddings.csv --model text-embedding-3-small

Example:
    python3 5_embedings.py --input-dir chunks --output-file chunk_embeddings.csv --model text-embedding-3-small
"""

import argparse
import csv
import json
import logging
import os
from typing import List, Dict

import openai

def load_api_key() -> str:
    """
    Loads the OpenAI API key from a file one level up ("../openai_api.key").
    
    Returns:
        str: The API key.
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))
    api_key_path = os.path.join(script_dir, "..", "openai_api.key")
    try:
        with open(api_key_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
            return key
    except Exception as e:
        logging.error(f"Failed to load API key from {api_key_path}: {e}")
        raise

def get_embedding(text: str, model: str) -> List[float]:
    """
    Generates an embedding vector for the provided text using the new OpenAI API interface.
    
    Args:
        text (str): The text to embed.
        model (str): The embedding model to use.
        
    Returns:
        List[float]: The embedding vector.
    """
    # IMPORTANT: Pass the input as a plain string (not a list) for a single text input.
    response = openai.embeddings.create(input=text, model=model)
    # Use attribute access instead of subscripting.
    embedding: List[float] = response.data[0].embedding
    return embedding

def embed_chunks_in_directory(input_dir: str, model: str) -> List[Dict]:
    """
    Processes all text chunk files in the specified directory to generate embeddings.
    
    Args:
        input_dir (str): Directory containing the chunk text files.
        model (str): The embedding model to use.
        
    Returns:
        List[Dict]: A list of dictionaries, each with:
            - 'chunk_file': Filename of the chunk.
            - 'token_count': An estimated token count (using a simple word split).
            - 'embedding': The generated embedding vector.
    """
    embeddings_list = []
    files = sorted([f for f in os.listdir(input_dir) if f.endswith(".txt")])
    logging.info(f"Found {len(files)} chunk files in '{input_dir}'.")
    
    for filename in files:
        file_path = os.path.join(input_dir, filename)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            logging.error(f"Error reading {file_path}: {e}")
            continue
        
        try:
            embedding = get_embedding(text, model)
            # Use a simple word split to estimate token count; for precision, consider using tiktoken.
            token_count = len(text.split())
            embeddings_list.append({
                "chunk_file": filename,
                "token_count": token_count,
                "embedding": embedding
            })
            logging.info(f"Processed {filename}: ~{token_count} tokens.")
        except Exception as e:
            logging.error(f"Error generating embedding for {filename}: {e}")
    
    return embeddings_list

def write_embeddings_to_csv(embeddings_data: List[Dict], output_file: str) -> None:
    """
    Writes the embeddings data to a CSV file.
    
    Each row in the CSV includes:
      - chunk_file: The filename.
      - token_count: The estimated token count.
      - embedding: The embedding vector stored as a JSON string.
    
    Args:
        embeddings_data (List[Dict]): The embeddings data.
        output_file (str): Path to the output CSV file.
    """
    fieldnames = ["chunk_file", "token_count", "embedding"]
    try:
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for entry in embeddings_data:
                # Convert the embedding list to a JSON string for storage.
                entry["embedding"] = json.dumps(entry["embedding"])
                writer.writerow(entry)
        logging.info(f"Embeddings saved to {output_file}.")
    except Exception as e:
        logging.error(f"Error writing embeddings to CSV {output_file}: {e}")

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate embeddings for text chunks using OpenAI's API (new interface).",
        epilog="Example: python3 5_embedings.py --input-dir chunks --output-file embeddings.csv --model text-embedding-3-small"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="chunks",
        help="Directory containing chunk text files (default: chunks)."
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="embeddings.csv",
        help="CSV file to save embeddings (default: embeddings.csv)."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="text-embedding-3-small",
        help="Embedding model to use (default: text-embedding-3-small)."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    try:
        openai.api_key = load_api_key()
    except Exception as e:
        logging.error("API key could not be loaded. Exiting.")
        return

    logging.info(f"Embedding chunks from directory '{args.input_dir}' using model '{args.model}'.")
    embeddings_data = embed_chunks_in_directory(args.input_dir, args.model)
    
    if embeddings_data:
        write_embeddings_to_csv(embeddings_data, args.output_file)
    else:
        logging.warning("No embeddings were generated.")

if __name__ == "__main__":
    main()