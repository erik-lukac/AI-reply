#!/usr/bin/env python3
"""
4_chunking.py

This script reads a large text file and splits it into overlapping, token-based chunks.
It is designed to prepare text for embeddings with the text-embedding-3-small model,
which supports up to 8,191 tokens per request. We use a default chunk size of 1,000 tokens
with an overlap of 150 tokens, but these values can be adjusted via command-line arguments.

Additionally, the script calculates and logs the token count before chunking and the sum of tokens
across all chunks after chunking.

Usage:
    python3 4_chunking.py --input path/to/your_file.txt [--output-dir chunks] [--chunk-size 1000] [--overlap 150]

Examples:
    python3 4_chunking.py --input large_document.txt
    python3 4_chunking.py --input large_document.txt --output-dir output_chunks --chunk-size 1000 --overlap 150
"""

import argparse
import logging
import os
import sys
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
    logging.debug(f"Total tokens in input (inside chunking function): {total_tokens}")

    chunks: List[str] = []
    start = 0

    # Use a sliding window with the specified overlap.
    # Log each chunk creation at DEBUG level.
    while start < total_tokens:
        end = start + chunk_size
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)
        logging.debug(f"Created chunk with tokens {start} to {min(end, total_tokens)} (size: {len(chunk_tokens)} tokens)")
        start += chunk_size - overlap

    return chunks

# Custom ArgumentParser to print epilog (examples) on errors
class CustomArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # Print usage and epilog (if provided) before the error message.
        sys.stderr.write(self.format_usage())
        if self.epilog:
            sys.stderr.write("\n" + self.epilog + "\n")
        sys.stderr.write(f"\n{self.prog}: error: {message}\n")
        sys.exit(2)

def main() -> None:
    """
    Main function:
      - Parses command-line arguments.
      - Reads the input text file.
      - Tokenizes the text to count tokens before chunking.
      - Splits the text into overlapping chunks using token counts.
      - Calculates and logs the sum of tokens across all chunks.
      - Writes each chunk to a separate file in the output directory.
    """
    parser = CustomArgumentParser(
        description="Chunk a text file into overlapping token-based chunks for embeddings.",
        epilog="""Examples:
    python3 4_chunking.py --input large_document.txt
    python3 4_chunking.py --input large_document.txt --output-dir output_chunks --chunk-size 1000 --overlap 150""",
        formatter_class=argparse.RawDescriptionHelpFormatter
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
        help="Directory to store the output chunk files (default: 'chunks')."
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

    # Set logging level to INFO (DEBUG messages will not be shown unless the level is lowered)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.info(f"Input file: {input_path}")
    logging.info(f"Output directory: {output_dir}")
    logging.info(f"Chunk size: {chunk_size} tokens")
    logging.info(f"Overlap: {overlap} tokens")

    if not os.path.isfile(input_path):
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Reading input file: {input_path}")
    try:
        with open(input_path, "r", encoding="utf-8") as file:
            text = file.read()
    except Exception as e:
        logging.error(f"Failed to read input file: {e}")
        return

    # Calculate token count before chunking
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    original_tokens = encoding.encode(text)
    total_tokens_before = len(original_tokens)
    logging.info(f"Token count before chunking: {total_tokens_before} tokens")

    logging.info("Splitting text into chunks...")
    chunks = chunk_text_with_overlap(text, chunk_size, overlap, ENCODING_NAME)
    logging.info(f"Created {len(chunks)} chunks (each {chunk_size} tokens with {overlap} overlap) in memory.")

    # Calculate the sum of tokens across all chunks
    sum_tokens_after = sum(len(encoding.encode(chunk)) for chunk in chunks)
    logging.info(f"Sum of tokens across all chunks: {sum_tokens_after}")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logging.info(f"Created output directory: {output_dir}")

    base_name: str = os.path.splitext(os.path.basename(input_path))[0]
    successful_writes = 0
    for i, chunk in enumerate(chunks, start=1):
        output_file: str = os.path.join(output_dir, f"{base_name}_chunk_{i:03d}.txt")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(chunk)
            successful_writes += 1
            logging.debug(f"Wrote chunk {i} to {output_file}")
        except Exception as e:
            logging.error(f"Error writing chunk {i}: {e}")

    logging.info(f"Wrote {successful_writes} chunks to {output_dir}")

if __name__ == "__main__":
    main()