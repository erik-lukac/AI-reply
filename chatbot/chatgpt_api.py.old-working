#!/usr/bin/env python3
"""
chatgpt_api.py

A command-line script to query the ChatGPT API using the new OpenAI client interface.
It reads the API key from the file defined in the constants section (by default, one directory above the script)
and supports command-line arguments for the user input and an optional system prompt.

Usage Examples:
    # Example: Using the default model with only a user prompt.
    ./chatgpt_api.py --user-input "Who is the latest US president?"

Mandatory Arguments:
    --user-input     The message content for the user.

Optional Arguments:
    --system-input   An optional system message that sets the assistant's behavior.

Output:
    Prints a JSON object to stdout with the key 'text' containing the ChatGPT response.
"""

import argparse
import json
import logging
import os
from typing import Dict, List, Optional

import openai
from openai import OpenAI

# ====================
# Constants
# ====================

# Script directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# API key file (located one level above the folder of the script)
API_KEY_FILE_PATH = os.path.join(SCRIPT_DIR, "..", "openai_api.key")

# Model constant (use this default model)
DEFAULT_MODEL = "gpt-4o-mini"

# Default maximum length for logging (not used for truncation in this version)
LOG_QUERY_MAX_LENGTH = 100

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
        description="Query ChatGPT API with user input and optional system prompt."
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
    args = parser.parse_args()
    logging.info("Command-line arguments parsed successfully.")
    return args


def build_messages(user_input: str, system: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Build the list of messages for the ChatGPT API.
    """
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
        logging.info("Added system message to the conversation.")
    messages.append({"role": "user", "content": user_input})
    logging.info("Added user message to the conversation.")
    return messages


def query_chatgpt(api_key: str, messages: List[Dict[str, str]]) -> str:
    """
    Query the ChatGPT API using the new OpenAI client interface.
    """
    openai.api_key = api_key
    client = OpenAI(api_key=api_key)
    try:
        logging.info(f"Sending request to model '{DEFAULT_MODEL}'.")
        completion = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages
        )
        reply_obj = completion.choices[0].message
        reply = (
            reply_obj.get("content", "").strip()
            if isinstance(reply_obj, dict)
            else reply_obj.content.strip()
        )
        logging.info("Received response from ChatGPT API.")
        return reply
    except Exception as e:
        logging.error(f"Error during API call: {e}")
        raise


def main() -> None:
    """
    Main function to parse arguments, log the messages to be sent, query the API, and output the result.
    """
    args = parse_arguments()
    api_key = load_api_key(API_KEY_FILE_PATH)

    messages = build_messages(
        user_input=args.user_input, 
        system=args.system_input
    )

    # Log the complete messages list as a compact JSON string.
    messages_json = json.dumps(messages, separators=(',',':'))
    logging.info(f"message to openapi: {messages_json}")

    response_text = query_chatgpt(api_key=api_key, messages=messages)
    output = {"text": response_text}
    print(json.dumps(output, indent=4))
    logging.info("Output JSON printed to console.")


if __name__ == "__main__":
    main()