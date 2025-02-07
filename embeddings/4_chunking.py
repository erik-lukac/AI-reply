#!/usr/bin/env python3
"""
3_chunking.py

This script reads a large text file and splits it into overlapping, token-based chunks.
It is designed to prepare text for embeddings with the text-embedding-3-small model,
which supports up to 8,191 tokens per request. We use a default chunk size of 1,000 tokens
with an overlap of 150 tokens, but these values can be adjusted via command-line arguments.

Usage:
    python3 3_chunking.py --input path/to/your_file.txt [--output-dir chunks] [--chunk-size 1000] [--overlap 150]

Example:
    python3 3_chunking.py --input large_document.txt --output-dir output_chunks --chunk-size 1000 --overlap 150
"""

import argparse
import logging
import os
from typing import List

try:
    import tiktoken
except ImportError as e:
    raise ImportError("tiktoken module not found. Please install it with 'pip install tiktoken'.") from e

# =============================================================================
# Configuration Options (default values, can be overridden via command-line)
# =============================================================================
DEFAULT_CHUNK_SIZE: int = 1000  # Number of tokens per chunk
DEFAULT_OVERLAP: int = 150      # Number of tokens to overlap between consecutive chunks
ENCODING_NAME: str = "cl100k_base"  # Tokenizer encoding for text-embedding-3-small

def chunk_text_with_overlap(text: str, chunk_size: int, overlap: int, encoding_name: str) -> List[str]:
    """
    Splits the input text into overlapping chunks based on token counts.

    Args:
        text (str): The full text to split.
        chunk_size (int): Maximum number of tokens per chunk.
        overlap (int): Number of tokens to overlap between consecutive chunks.
        encoding_name (str): The name of the tokenizer encoding.

    Returns:
        List[str]: A list of text chunks.
    """
    encoding = tiktoken.get_encoding(encoding_name)
    tokens = encoding.encode(text)
    total_tokens = len(tokens)
    logging.info(f"Total tokens in input: {total_tokens}")

    chunks: List[str] = []
    start = 0

    # Use a sliding window with the specified overlap
    while start < total_tokens:
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        logging.info(f"Created chunk with tokens {start} to {min(end, total_tokens)} (size: {len(chunk_tokens)} tokens)")
        start += chunk_size - overlap

    return chunks

def main() -> None:
    """
    Main function:
      - Parses command-line arguments.
      - Reads the input text file.
      - Splits the text into overlapping chunks using token counts.
      - Writes each chunk to a separate file in the output directory.

    Example usage:
        python3 3_chunking.py --input large_document.txt --output-dir output_chunks --chunk-size 1000 --overlap 150
    """
    parser = argparse.ArgumentParser(
        description="Chunk a text file into overlapping token-based chunks for embeddings.",
        epilog="Example: python3 3_chunking.py --input large_document.txt --output-dir output_chunks --chunk-size 1000 --overlap 150"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the input text file."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="chunks",
        help="Directory to store the output chunk files."
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Number of tokens per chunk (default: {DEFAULT_CHUNK_SIZE})."
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=DEFAULT_OVERLAP,
        help=f"Number of tokens to overlap between chunks (default: {DEFAULT_OVERLAP})."
    )
    args = parser.parse_args()

    input_path: str = args.input
    output_dir: str = args.output_dir
    chunk_size: int = args.chunk_size
    overlap: int = args.overlap

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not os.path.isfile(input_path):
        logging.error(f"Input file not found: {input_path}")
        return

    try:
        with open(input_path, "r", encoding="utf-8") as file:
            text = file.read()
    except Exception as e:
        logging.error(f"Failed to read input file: {e}")
        return

    logging.info("Splitting text into chunks...")
    chunks = chunk_text_with_overlap(text, chunk_size, overlap, ENCODING_NAME)
    logging.info(f"Total chunks created: {len(chunks)}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created output directory: {output_dir}")

    base_name: str = os.path.splitext(os.path.basename(input_path))[0]
    for i, chunk in enumerate(chunks, start=1):
        output_file: str = os.path.join(output_dir, f"{base_name}_chunk_{i:03d}.txt")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(chunk)
            logging.info(f"Wrote chunk {i} to {output_file}")
        except Exception as e:
            logging.error(f"Error writing chunk {i}: {e}")

if __name__ == "__main__":
    main()