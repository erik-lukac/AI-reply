#!/usr/bin/env python3
"""
chatgpt_api.py

A command-line script to query the ChatGPT API using the new OpenAI client interface.
It reads the API key from the file 'chatgpt_api.key' and supports command-line arguments
for the user input, an optional system prompt, and a model alias (or module) to use.

Usage Examples:
    # Example 1: Using default model with only a user prompt.
    ./chatgpt_api.py --input "Who is the latest US president?"
    
    # Example 2: Specifying a system prompt and an alternate model alias.
    ./chatgpt_api.py --input "Tell me a joke." --system "You are a funny assistant." --model gpt-4o

Mandatory Arguments:
    --input     The message content for the user.

Optional Arguments:
    --system    An optional system message that sets the behavior of the assistant.
    --model     The model alias (or module) to use. The default is 'gpt-4o-mini'.
                You may use any model alias such as:
                    gpt-4o, gpt-4o-2024-08-06, chatgpt-4o-latest,
                    gpt-4o-mini, o1, o1-mini, o3-mini, o1-preview,
                    gpt-4o-realtime-preview, gpt-4o-mini-realtime-preview,
                    gpt-4o-audio-preview, etc.

Output:
    Prints a JSON object to stdout with the key 'text' containing the ChatGPT response.
"""

import argparse
import json
import logging
from typing import Any, Dict, List, Optional

# Use the new OpenAI client
from openai import OpenAI

# Configure logging to output only essential information.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)


def load_api_key(filename: str) -> str:
    """
    Load the OpenAI API key from the given file.

    Args:
        filename (str): Path to the file containing the API key.

    Returns:
        str: The API key.
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
    Parse the command-line arguments.

    Returns:
        argparse.Namespace: The parsed arguments.
    """
    parser = argparse.ArgumentParser(
        description="Query ChatGPT API with user input, optional system prompt, and model alias."
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="The message content for the user."
    )
    parser.add_argument(
        "--system",
        type=str,
        default=None,
        help="Optional system message that sets the assistant's behavior."
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help=("The model alias (or module) to use. Default is 'gpt-4o-mini'. "
              "Examples: gpt-4o, gpt-4o-2024-08-06, chatgpt-4o-latest, "
              "gpt-4o-mini, o1, o1-mini, o3-mini, o1-preview, "
              "gpt-4o-realtime-preview, gpt-4o-mini-realtime-preview, gpt-4o-audio-preview.")
    )
    args = parser.parse_args()
    logging.info("Command-line arguments parsed successfully.")
    return args


def build_messages(user_input: str, system: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Build the list of messages for the ChatGPT API.

    Args:
        user_input (str): The message content for the user.
        system (Optional[str]): Optional system message.

    Returns:
        List[Dict[str, str]]: The messages formatted for the API.
    """
    messages: List[Dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
        logging.info("Added system message to the conversation.")
    messages.append({"role": "user", "content": user_input})
    logging.info("Added user message to the conversation.")
    return messages


def query_chatgpt(api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    """
    Query the ChatGPT API using the new OpenAI client interface.

    Args:
        api_key (str): The OpenAI API key.
        model (str): The model alias (or module) to use.
        messages (List[Dict[str, str]]): The conversation messages.

    Returns:
        str: The text of the API response.
    """
    client = OpenAI(api_key=api_key)
    try:
        logging.info(f"Sending request to model '{model}'.")
        completion = client.chat.completions.create(
            model=model,
            messages=messages
        )
        # Extract only the essential reply content.
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
    Main function to parse arguments, query the API, and output the result.
    """
    args = parse_arguments()
    api_key = load_api_key("chatgpt_api.key")
    messages = build_messages(user_input=args.input, system=args.system)
    response_text = query_chatgpt(api_key=api_key, model=args.model, messages=messages)
    output = {"text": response_text}
    print(json.dumps(output, indent=4))
    logging.info("Output JSON printed to console.")


if __name__ == "__main__":
    main()