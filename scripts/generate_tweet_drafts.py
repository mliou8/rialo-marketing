"""
Script to read topics from Notion Twitter Calendar and generate tweet drafts using Gemini.
"""

import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notion_client import get_notion

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


def generate_tweet(topic: str, style: str = "professional") -> str:
    """
    Generate a tweet draft using Gemini.

    Args:
        topic: The topic/title to write a tweet about
        style: Writing style (professional, casual, engaging)

    Returns:
        Generated tweet text
    """
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""Write a single tweet about the following topic. The tweet should be:
- Under 280 characters
- {style} in tone
- Engaging and shareable
- Include 1-2 relevant hashtags if appropriate

Topic: {topic}

Respond with ONLY the tweet text, nothing else."""

    response = model.generate_content(prompt)
    return response.text.strip()


def generate_tweet_variations(topic: str, count: int = 3) -> list:
    """
    Generate multiple tweet variations for a topic.

    Args:
        topic: The topic to write tweets about
        count: Number of variations to generate

    Returns:
        List of tweet drafts
    """
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""Write {count} different tweet variations about the following topic. Each tweet should be:
- Under 280 characters
- Varied in tone (one professional, one casual, one provocative/engaging)
- Shareable and engaging
- Include 1-2 relevant hashtags where appropriate

Topic: {topic}

Format your response as:
1. [tweet 1]
2. [tweet 2]
3. [tweet 3]"""

    response = model.generate_content(prompt)
    response_text = response.text.strip()

    # Parse the numbered list
    tweets = []
    for line in response_text.split("\n"):
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            tweet = line.split(".", 1)[1].strip()
            tweets.append(tweet)

    return tweets


def process_calendar_items(dry_run: bool = False) -> int:
    """
    Process Twitter Calendar items without drafts and generate tweets.

    Args:
        dry_run: If True, don't save to Notion, just print

    Returns:
        Number of items processed
    """
    notion = get_notion()

    # Get items that don't have drafts yet
    items = notion.get_twitter_calendar_items(has_draft=False)
    print(f"Found {len(items)} items without drafts")

    processed = 0
    for item in items:
        try:
            title = notion.get_item_title(item)
            if not title:
                print("Skipping item with no title")
                continue

            print(f"\nGenerating tweet for: {title}")
            tweet = generate_tweet(title)
            print(f"Draft: {tweet}")

            if not dry_run:
                notion.update_twitter_draft(item["id"], tweet)
                print("Saved to Notion!")

            processed += 1

        except Exception as e:
            print(f"Error processing item: {e}")
            continue

    return processed


def main():
    """Main function to generate tweet drafts."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate tweet drafts from Notion calendar")
    parser.add_argument("--dry-run", action="store_true", help="Don't save to Notion")
    parser.add_argument("--topic", type=str, help="Generate a single tweet for a specific topic")
    parser.add_argument("--variations", action="store_true", help="Generate multiple variations")
    args = parser.parse_args()

    if args.topic:
        # Single topic mode
        print(f"Generating tweet for: {args.topic}")
        if args.variations:
            tweets = generate_tweet_variations(args.topic)
            print("\nVariations:")
            for i, tweet in enumerate(tweets, 1):
                print(f"\n{i}. {tweet}")
        else:
            tweet = generate_tweet(args.topic)
            print(f"\nDraft: {tweet}")
    else:
        # Process all calendar items
        processed = process_calendar_items(dry_run=args.dry_run)
        print(f"\nProcessed {processed} items")


if __name__ == "__main__":
    main()
