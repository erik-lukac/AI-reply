#!/usr/bin/env python3
"""
chatgpt_api.py

A command-line script to query the ChatGPT API using the new OpenAI client interface.
It reads the API key from the file defined in the constants section (by default, one directory above the script)
and supports command-line arguments for the user input, an optional system prompt, and an optional flag to use embeddings.

Usage Examples:
    # Example 1: Using the default model with only a user prompt.
    ./chatgpt_api.py --user-input "Who is the latest US president?"
    
    # Example 2: Specifying a system prompt and enabling embeddings (using ChromaDB).
    ./chatgpt_api.py --user-input "Tell me a joke." --system-input "You are a funny assistant." --embeddings

Mandatory Arguments:
    --user-input     The message content for the user.

Optional Arguments:
    --system-input   An optional system message that sets the assistant's behavior.
    --embeddings     Flag to enable usage of embeddings (via ChromaDB) for extra context.

Output:
    Prints a JSON object to stdout with the key 'text' containing the ChatGPT response.
"""

import argparse
import json
import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
import openai
from openai import OpenAI

# ====================
# Constants
# ====================

# Script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# API key file (located one level above the folder of the script)
API_KEY_FILE_PATH = os.path.join(SCRIPT_DIR, "..", "openai_api.key")

# Model constant (the --model argument is removed; use this default model)
DEFAULT_MODEL = "gpt-4o-mini"

# ChromaDB settings
CHROMA_EMBEDDINGS_FOLDER = os.path.join(SCRIPT_DIR, "..", "embeddings", "chroma_db")
COLLECTION_NAME = "text_embeddings"  # Updated collection name

# ====================
# Logging configuration
# ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)


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


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Query ChatGPT API with user input, optional system prompt, and optional embeddings (ChromaDB)."
    )
    parser.add_argument(
        "--user-input",
        type=str,
        required=True,
        help="The message content for the user."
    )
    parser.add_argument(
        "--system-input",
        type=str,
        default=None,
        help="Optional system message that sets the assistant's behavior."
    )
    parser.add_argument(
        "--embeddings",
        action="store_true",
        help="Enable usage of embeddings (via ChromaDB) for extra context."
    )
    args = parser.parse_args()
    logging.info("Command-line arguments parsed successfully.")
    return args


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """
    Compute the cosine similarity between two vectors.
    """
    v1 = np.array(v1)
    v2 = np.array(v2)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


def compute_embedding(api_key: str, text: str) -> List[float]:
    """
    Compute the embedding for a given text using OpenAI's embeddings API.
    Updated to use the newest embeddings model: text-embedding-3-small.
    """
    openai.api_key = api_key
    try:
        response = openai.embeddings.create(
            model="text-embedding-3-small",  # Updated model name
            input=[text]  # Input must be a list of strings
        )
        embedding = response.data[0].embedding
        logging.info(f"Computed embedding: dimension = {len(embedding)}, first 5 values = {embedding[:5]}")
        return embedding
    except Exception as e:
        logging.error(f"Error computing embedding: {e}")
        raise


def query_chroma_db(query: str, api_key: str) -> str:
    """
    Retrieve context from ChromaDB using the query.
    Requires the chromadb package to be installed (pip install chromadb).
    Uses the collection defined by COLLECTION_NAME and persists data in CHROMA_EMBEDDINGS_FOLDER.
    Telemetry is disabled.
    """
    # Compute the query's embedding.
    query_embedding = compute_embedding(api_key, query)
    logging.info(f"Computed query embedding (first 5 dims): {query_embedding[:5]}, length: {len(query_embedding)}")
    try:
        import chromadb
        from chromadb.config import Settings
        # Initialize a PersistentClient with telemetry disabled.
        client = chromadb.PersistentClient(
            path=CHROMA_EMBEDDINGS_FOLDER,
            settings=Settings(telemetry_enabled=False)
        )
        try:
            # Try to get an existing collection.
            collection = client.get_collection(name=COLLECTION_NAME)
        except Exception:
            # If the collection doesn't exist, create a new one.
            logging.info(f"Collection '{COLLECTION_NAME}' not found. Creating a new collection.")
            collection = client.create_collection(name=COLLECTION_NAME)
        # Query the collection using the computed embedding.
        results = collection.query(query_embeddings=[query_embedding], n_results=1)
        # Log only the first 100 characters of the query results.
        truncated_results = str(results)[:100] + "..."
        logging.info(f"ChromaDB query results (truncated): {truncated_results}")
        # Check that results contain at least one document.
        if (results and "documents" in results and 
            results["documents"] and 
            isinstance(results["documents"], list) and 
            len(results["documents"]) > 0 and 
            isinstance(results["documents"][0], list) and 
            len(results["documents"][0]) > 0):
            best_text = results["documents"][0][0]
            # Truncate the logged document to the first 100 characters.
            truncated_doc = best_text[:100] + "..." if len(best_text) > 100 else best_text
            logging.info(f"ChromaDB returned document (truncated): {truncated_doc}")
            return best_text
        else:
            logging.info("ChromaDB query returned no results.")
            return ""
    except Exception as e:
        logging.error(f"Error querying ChromaDB: {e}")
        return ""


def retrieve_context(query: str, api_key: str) -> str:
    """
    Retrieve context using ChromaDB.
    """
    return query_chroma_db(query, api_key)


def build_messages(user_input: str, system: Optional[str] = None, context: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Build the list of messages for the ChatGPT API.
    If a context string is provided, it is added as an extra system message.
    """
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
        logging.info("Added system message to the conversation.")
    if context:
        messages.append({"role": "system", "content": f"Context:\n{context}"})
        logging.info("Added context message to the conversation.")
    messages.append({"role": "user", "content": user_input})
    logging.info("Added user message to the conversation.")
    return messages


def query_chatgpt(api_key: str, messages: List[Dict[str, str]]) -> str:
    """
    Query the ChatGPT API using the new OpenAI client interface.
    """
    client = OpenAI(api_key=api_key)
    try:
        logging.info(f"Sending request to model '{DEFAULT_MODEL}'.")
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages
        )
        reply_obj = completion.choices[0].message
        reply = (reply_obj.get("content", "").strip()
                 if isinstance(reply_obj, dict)
                 else reply_obj.content.strip())
        logging.info("Received response from ChatGPT API.")
        return reply
    except Exception as e:
        logging.error(f"Error during API call: {e}")
        raise


def main() -> None:
    """
    Main function to parse arguments, optionally retrieve extra context via ChromaDB,
    query the API, and output the result.
    """
    args = parse_arguments()
    api_key = load_api_key(API_KEY_FILE_PATH)
    context = ""
    if args.embeddings:
        logging.info("Embeddings flag is enabled. Retrieving additional context using ChromaDB.")
        context = retrieve_context(args.user_input, api_key)
    else:
        logging.info("Embeddings flag is disabled. No additional context will be retrieved.")
    messages = build_messages(user_input=args.user_input, system=args.system_input, context=context)
    response_text = query_chatgpt(api_key=api_key, messages=messages)
    output = {"text": response_text}
    print(json.dumps(output, indent=4))
    logging.info("Output JSON printed to console.")


if __name__ == "__main__":
    main()