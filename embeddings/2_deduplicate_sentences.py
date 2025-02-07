#!/usr/bin/env python3

"""
Chunk-based TUI for interactive sentence deduplication.

Features:
- Splits text into sentences using NLTK.
- Finds duplicates (freq > 1), sorts them by descending frequency.
- In each chunk (default: 30 duplicates), shows a TUI:
  - Arrow keys to move selection
  - Space to toggle (X) dedup
  - 'a' to toggle select all/none
  - Enter to confirm the chunk
  - 'q' to quit early (remaining duplicates are kept)

All sentences marked for deduplication get only their first occurrence kept.
Everything else remains as-is. The final text is saved to "<input>_deduplicated.txt".
"""

import argparse
import os
import sys
import curses
from collections import Counter
from typing import List, Tuple, Set
import nltk

# Ensure 'punkt' is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download("punkt")

from nltk.tokenize import sent_tokenize

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive TUI-based sentence deduplication in chunks.",
        epilog="Example: python deduplicate_curses.py --input big_cleaned.txt --chunk-size 30"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to the cleaned text file."
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=30,
        help="How many duplicates to show per TUI screen (default=30)."
    )
    return parser.parse_args()

def load_text(file_path: str) -> str:
    if not os.path.isfile(file_path):
        print(f"Error: The file '{file_path}' does not exist.")
        sys.exit(1)
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def get_output_filename(input_filename: str) -> str:
    base, ext = os.path.splitext(input_filename)
    return f"{base}_deduplicated{ext}"

def chunked_list(lst: List, n: int) -> List[List]:
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def curses_select_chunk(stdscr, chunk: List[Tuple[str, int]]) -> Tuple[bool, Set[int]]:
    """
    Interactive TUI for a single chunk of duplicates (list of (sentence, freq)).

    Returns:
      - A boolean indicating if user quit early (True = user pressed 'q').
      - A set of indices that were toggled (marked for dedup).

    Controls:
      - ↑/↓: move selection
      - SPACE: toggle mark
      - 'a': toggle select all / clear all
      - ENTER: confirm and exit the chunk
      - 'q': quit the entire process
    """

    h, w = stdscr.getmaxyx()
    # We store toggles in a boolean list, same length as chunk
    toggles = [False] * len(chunk)
    selected_idx = 0
    quit_early = False

    # Helper function to redraw the UI
    def draw_ui():
        stdscr.clear()
        stdscr.addstr(0, 0, "TUI Deduplication - Use ↑/↓, Space to toggle, 'a' all/none, Enter to confirm, 'q' quit.")
        stdscr.addstr(1, 0, f"Chunk size: {len(chunk)} duplicates")
        # We'll start listing items from row=3 downward
        start_row = 3
        for i, (sentence, freq) in enumerate(chunk):
            # If it doesn't fit on the screen, we won't print further
            if start_row + i >= h - 1:
                break
            mark_char = "X" if toggles[i] else " "
            highlight = (i == selected_idx)
            display_line = f"({i+1}) [freq={freq}] [{mark_char}] {sentence[:80].replace('\n',' ')}"
            # We limit the sentence display to ~80 chars for brevity
            if highlight:
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(start_row + i, 0, display_line[:w-1])  # trim if needed
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(start_row + i, 0, display_line[:w-1])
        stdscr.refresh()

    while True:
        draw_ui()
        key = stdscr.getch()
        if key == curses.KEY_UP:
            selected_idx = max(0, selected_idx - 1)
        elif key == curses.KEY_DOWN:
            selected_idx = min(len(chunk) - 1, selected_idx + 1)
        elif key == ord(' '):
            # Toggle
            toggles[selected_idx] = not toggles[selected_idx]
        elif key == ord('a'):
            # Toggle all or none
            if all(toggles):
                # if everything is selected, clear them
                toggles = [False] * len(chunk)
            else:
                # else select all
                toggles = [True] * len(chunk)
        elif key in [curses.KEY_ENTER, 10, 13]:
            # Enter pressed => confirm and exit chunk
            break
        elif key == ord('q'):
            # Quit entire flow
            quit_early = True
            break

    # Build set of toggled indices
    toggled_indices = {i for i, t in enumerate(toggles) if t}
    return quit_early, toggled_indices

def run_curses_dedup(all_duplicates: List[Tuple[str, int]], chunk_size: int) -> Set[str]:
    """
    Main curses loop that processes duplicates in chunks.
    Returns a set of sentences user marked for deduplication.
    """
    # A set of sentences that user toggled for dedup
    dedup_sentences = set()

    def curses_main(stdscr):
        nonlocal dedup_sentences
        curses.curs_set(0)  # hide cursor
        stdscr.nodelay(False)

        chunks = list(chunked_list(all_duplicates, chunk_size))
        for cidx, chunk in enumerate(chunks, start=1):
            # chunk is list of (sentence, freq)
            # call the interactive function
            quit_early, toggled_indices = curses_select_chunk(stdscr, chunk)
            if quit_early:
                # user pressed 'q' => keep rest
                return
            # record toggled sentences in dedup_sentences
            for idx in toggled_indices:
                sentence_to_dedup = chunk[idx][0]
                dedup_sentences.add(sentence_to_dedup)

    curses.wrapper(curses_main)
    return dedup_sentences

def main():
    args = parse_arguments()
    text = load_text(args.input)
    sentences = sent_tokenize(text)
    print(f"Loaded {len(sentences)} sentences from '{args.input}'.")

    # Find duplicates
    counts = Counter(sentences)
    duplicates = [(s, c) for s, c in counts.items() if c > 1]
    # Sort by descending frequency
    duplicates.sort(key=lambda x: x[1], reverse=True)

    if not duplicates:
        print("No duplicates found! Exiting.")
        return

    print(f"Found {len(duplicates)} sentences with freq > 1. Entering curses UI...")

    # Step into curses TUI
    dedup_set = run_curses_dedup(duplicates, args.chunk_size)
    print(f"Selected {len(dedup_set)} sentences for deduplication...")

    # Rebuild final text
    # For sentences in dedup_set => keep only first occurrence
    occurrence_tracker = {}
    final_sentences = []
    for sent in sentences:
        if sent in dedup_set:
            if sent not in occurrence_tracker:
                final_sentences.append(sent)
                occurrence_tracker[sent] = 1
            # else skip duplicates
        else:
            # keep all
            final_sentences.append(sent)

    # Save
    output_path = get_output_filename(args.input)
    # For readability, we might join by newline. Adjust as you prefer.
    final_text = "\n".join(final_sentences)
    with open(output_path, "w", encoding="utf-8") as out_f:
        out_f.write(final_text)

    print(f"Done! Deduplicated text saved to: {output_path}")

if __name__ == "__main__":
    main()