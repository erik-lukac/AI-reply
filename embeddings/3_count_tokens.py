#!/usr/bin/env python3
"""
3_tokenise.py

This script tokenizes a text file using OpenAI's tiktoken library, which is useful to verify how text
will be processed before sending it to an embedding model. The script prints out the total token count and,
if desired, the token IDs.

Usage:
    python 3_tokenise.py --input path/to/your_file.txt [--show-tokens]

Example:
    python 3_tokenise.py --input sample.txt --show-tokens
"""

import argparse
import logging
import os
from typing import List

try:
    import tiktoken
except ImportError as e:
    raise ImportError("tiktoken module not found. Install it with 'pip install tiktoken'.") from e

# =============================================================================
# Configuration Options
# =============================================================================
# Choose the encoding to use for tokenization. For many OpenAI models, "cl100k_base" is a common choice.
ENCODING_NAME: str = "cl100k_base"

# =============================================================================
# Functions
# =============================================================================
def tokenize_text(text: str) -> List[int]:
    """
    Tokenizes the input text into token IDs using tiktoken.

    Args:
        text (str): The text to tokenize.

    Returns:
        List[int]: A list of token IDs.
    """
    encoding = tiktoken.get_encoding(ENCODING_NAME)
    tokens: List[int] = encoding.encode(text)
    return tokens

def main() -> None:
    """
    Main function to:
      - Parse command-line arguments.
      - Read the input text file.
      - Tokenize the text.
      - Print the token count and optionally the token IDs.

    Example usage:
        python 3_tokenise.py --input sample.txt --show-tokens
    """
    parser = argparse.ArgumentParser(
        description="Tokenize a text file using OpenAI's tiktoken library.",
        epilog="Example usage: python 3_tokenise.py --input path/to/your_file.txt --show-tokens"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to the input text file'
    )
    parser.add_argument(
        '--show-tokens',
        action='store_true',
        help='Display the list of token IDs'
    )
    args = parser.parse_args()

    input_path: str = args.input

    # Set up logging to the console.
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if not os.path.isfile(input_path):
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Reading input file: {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as file:
            text: str = file.read()
    except Exception as e:
        logging.error(f"Error reading file {input_path}: {e}")
        return

    logging.info("Tokenizing text...")
    tokens: List[int] = tokenize_text(text)
    token_count: int = len(tokens)
    logging.info(f"Tokenization complete. Total tokens: {token_count}")

    if args.show_tokens:
        logging.info("Token IDs:")
        print(tokens)

if __name__ == "__main__":
    main()