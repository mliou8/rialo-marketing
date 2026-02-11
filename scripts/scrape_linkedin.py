"""
Script to scrape LinkedIn posts using Apify and save them to the Content Pipeline.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from apify_client import ApifyClient

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase_content import get_content_manager

load_dotenv()


def scrape_linkedin_posts(profile_url: str, max_posts: int = 20) -> list:
    """
    Scrape LinkedIn posts using Apify's LinkedIn scraper.

    Args:
        profile_url: LinkedIn profile URL to scrape posts from
        max_posts: Maximum number of posts to scrape

    Returns:
        List of scraped post data
    """
    client = ApifyClient(os.getenv("APIFY_API_TOKEN"))

    # Using Apify's LinkedIn Profile Scraper
    # Actor: "anchor/linkedin-profile-scraper" or similar
    run_input = {
        "profileUrls": [profile_url],
        "maxPostCount": max_posts,
        "scrapeCompanyData": False,
        "scrapeContactInfo": False,
    }

    # Run the actor
    # Note: You may need to adjust the actor ID based on your Apify subscription
    run = client.actor("anchor/linkedin-profile-scraper").call(run_input=run_input)

    # Fetch results
    posts = []
    for item in client.dataset(run["defaultDatasetId"]).iterate_items():
        if "posts" in item:
            posts.extend(item["posts"])
        elif "text" in item:  # Direct post format
            posts.append(item)

    return posts


def extract_post_title(content: str, max_length: int = 100) -> str:
    """Extract a title from post content."""
    if not content:
        return "Untitled Post"

    # Take first line or first N characters
    first_line = content.split("\n")[0].strip()
    if len(first_line) > max_length:
        return first_line[:max_length] + "..."
    return first_line if first_line else content[:max_length] + "..."


def save_posts_to_pipeline(posts: list) -> int:
    """
    Save scraped LinkedIn posts to Content Pipeline.

    Args:
        posts: List of post data from Apify

    Returns:
        Number of posts saved
    """
    saved_count = 0

    with get_content_manager() as cm:
        for post in posts:
            try:
                content = post.get("text", post.get("content", ""))
                url = post.get("url", post.get("postUrl", ""))

                title = extract_post_title(content)

                cm.add_to_pipeline(
                    title=title,
                    original_url=url,
                    status="Inspiration"
                )
                saved_count += 1
                print(f"Saved: {title[:50]}...")

            except Exception as e:
                print(f"Error saving post: {e}")
                continue

    return saved_count


def main():
    """Main function to run the LinkedIn scraping pipeline."""
    profile_url = os.getenv("LINKEDIN_PROFILE_URL")

    if not profile_url:
        print("Error: LINKEDIN_PROFILE_URL not set in .env")
        return

    print(f"Scraping LinkedIn posts from: {profile_url}")
    posts = scrape_linkedin_posts(profile_url)
    print(f"Found {len(posts)} posts")

    if posts:
        saved = save_posts_to_pipeline(posts)
        print(f"Saved {saved} posts to Content Pipeline")
    else:
        print("No posts found to save")


if __name__ == "__main__":
    main()
