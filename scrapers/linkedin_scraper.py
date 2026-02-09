"""
LinkedIn scraper using Apify - saves metrics to local SQLite database.
"""

import os
import sys
from datetime import datetime
from typing import Optional
from apify_client import ApifyClient

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_manager import get_db
from config import APIFY_API_TOKEN


class LinkedInScraper:
    """Scraper for LinkedIn posts and profile data using Apify."""

    def __init__(self, profile_url: str = ""):
        self.client = ApifyClient(APIFY_API_TOKEN)
        self.profile_url = profile_url

    def scrape_posts(self, max_posts: int = 50) -> list:
        """
        Scrape LinkedIn posts with metrics.

        Args:
            max_posts: Maximum number of posts to scrape

        Returns:
            List of post data dictionaries
        """
        if not self.profile_url:
            raise ValueError("LINKEDIN_PROFILE_URL not configured")

        # Apify LinkedIn Posts Scraper
        # You may need to adjust this based on available actors
        run_input = {
            "profileUrls": [self.profile_url],
            "maxPosts": max_posts,
            "includeMetrics": True,
        }

        try:
            run = self.client.actor("curious_coder/linkedin-post-scraper").call(
                run_input=run_input
            )

            posts = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                posts.append(self._normalize_post(item))

            return posts

        except Exception as e:
            print(f"Error scraping LinkedIn: {e}")
            # Return empty list on error
            return []

    def _normalize_post(self, raw_post: dict) -> dict:
        """Normalize raw Apify data to our schema."""
        # Parse date - handle various formats
        date_str = raw_post.get("postedAt", raw_post.get("date", ""))
        date_posted = None
        if date_str:
            try:
                # Try ISO format first
                date_posted = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    # Try common formats
                    date_posted = datetime.strptime(date_str, "%Y-%m-%d")
                except (ValueError, AttributeError):
                    date_posted = datetime.utcnow()

        return {
            "post_id": raw_post.get("postId", raw_post.get("id", str(hash(raw_post.get("text", "")[:50])))),
            "url": raw_post.get("postUrl", raw_post.get("url", "")),
            "content": raw_post.get("text", raw_post.get("content", "")),
            "date_posted": date_posted,
            "views": raw_post.get("views", raw_post.get("impressions", 0)) or 0,
            "likes": raw_post.get("likes", raw_post.get("reactions", 0)) or 0,
            "comments": raw_post.get("comments", raw_post.get("commentCount", 0)) or 0,
            "reposts": raw_post.get("reposts", raw_post.get("shares", 0)) or 0,
        }

    def scrape_profile_stats(self) -> dict:
        """
        Scrape profile statistics (follower count, etc.)

        Returns:
            Profile stats dictionary
        """
        run_input = {
            "profileUrls": [self.profile_url],
            "scrapeCompanyData": False,
        }

        try:
            run = self.client.actor("anchor/linkedin-profile-scraper").call(
                run_input=run_input
            )

            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                return {
                    "followers": item.get("followersCount", item.get("followers", 0)) or 0,
                    "connections": item.get("connectionsCount", item.get("connections", 0)) or 0,
                }

        except Exception as e:
            print(f"Error scraping profile stats: {e}")

        return {"followers": 0, "connections": 0}

    def save_to_database(self, posts: Optional[list] = None) -> int:
        """
        Scrape and save posts to local database.

        Args:
            posts: Optional list of posts (will scrape if not provided)

        Returns:
            Number of posts saved
        """
        if posts is None:
            posts = self.scrape_posts()

        saved = 0
        with get_db() as db:
            for post in posts:
                try:
                    db.upsert_linkedin_post(post)
                    saved += 1
                except Exception as e:
                    print(f"Error saving post: {e}")

            # Also save follower snapshot
            try:
                stats = self.scrape_profile_stats()
                db.add_follower_snapshot(
                    platform="linkedin",
                    follower_count=stats.get("followers", 0),
                    following_count=stats.get("connections", 0)
                )
            except Exception as e:
                print(f"Error saving follower stats: {e}")

        return saved


def main():
    """Test the LinkedIn scraper."""
    scraper = LinkedInScraper()
    print(f"Profile URL: {scraper.profile_url}")

    print("\nScraping posts...")
    posts = scraper.scrape_posts(max_posts=10)
    print(f"Found {len(posts)} posts")

    if posts:
        print("\nSample post:")
        print(posts[0])

        print("\nSaving to database...")
        saved = scraper.save_to_database(posts)
        print(f"Saved {saved} posts")


if __name__ == "__main__":
    main()
