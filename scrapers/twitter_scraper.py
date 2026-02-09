"""
Twitter/X scraper using Apify - saves metrics to local SQLite database.
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


class TwitterScraper:
    """Scraper for Twitter/X posts and profile data using Apify."""

    def __init__(self, username: str = ""):
        self.client = ApifyClient(APIFY_API_TOKEN)
        self.username = username.replace("@", "")

    def scrape_tweets(self, max_tweets: int = 50) -> list:
        """
        Scrape tweets with metrics.

        Args:
            max_tweets: Maximum number of tweets to scrape

        Returns:
            List of tweet data dictionaries
        """
        if not self.username:
            raise ValueError("TWITTER_USERNAME not configured")

        # Apify Twitter/X Scraper
        run_input = {
            "handles": [self.username],
            "maxTweets": max_tweets,
            "includeReplies": False,
            "includeRetweets": False,
        }

        try:
            # Using a popular Twitter scraper actor
            run = self.client.actor("apidojo/tweet-scraper").call(
                run_input=run_input
            )

            tweets = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                tweets.append(self._normalize_tweet(item))

            return tweets

        except Exception as e:
            print(f"Error scraping Twitter: {e}")
            return []

    def _normalize_tweet(self, raw_tweet: dict) -> dict:
        """Normalize raw Apify data to our schema."""
        # Parse date
        date_str = raw_tweet.get("createdAt", raw_tweet.get("date", ""))
        date_posted = None
        if date_str:
            try:
                date_posted = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                try:
                    # Twitter format: "Wed Oct 10 20:19:24 +0000 2018"
                    date_posted = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
                except (ValueError, AttributeError):
                    date_posted = datetime.utcnow()

        # Handle nested author data
        author = raw_tweet.get("author", {})

        return {
            "tweet_id": str(raw_tweet.get("id", raw_tweet.get("tweetId", ""))),
            "url": raw_tweet.get("url", f"https://twitter.com/{self.username}/status/{raw_tweet.get('id', '')}"),
            "content": raw_tweet.get("text", raw_tweet.get("fullText", "")),
            "date_posted": date_posted,
            "views": raw_tweet.get("viewCount", raw_tweet.get("views", 0)) or 0,
            "likes": raw_tweet.get("likeCount", raw_tweet.get("favoriteCount", 0)) or 0,
            "retweets": raw_tweet.get("retweetCount", raw_tweet.get("retweets", 0)) or 0,
            "replies": raw_tweet.get("replyCount", raw_tweet.get("replies", 0)) or 0,
            "quotes": raw_tweet.get("quoteCount", raw_tweet.get("quotes", 0)) or 0,
        }

    def scrape_profile_stats(self) -> dict:
        """
        Scrape profile statistics (follower count, etc.)

        Returns:
            Profile stats dictionary
        """
        run_input = {
            "handles": [self.username],
            "maxTweets": 1,  # Just need profile data
        }

        try:
            run = self.client.actor("apidojo/tweet-scraper").call(
                run_input=run_input
            )

            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                author = item.get("author", item)
                return {
                    "followers": author.get("followersCount", author.get("followers", 0)) or 0,
                    "following": author.get("followingCount", author.get("following", 0)) or 0,
                }

        except Exception as e:
            print(f"Error scraping profile stats: {e}")

        return {"followers": 0, "following": 0}

    def save_to_database(self, tweets: Optional[list] = None) -> int:
        """
        Scrape and save tweets to local database.

        Args:
            tweets: Optional list of tweets (will scrape if not provided)

        Returns:
            Number of tweets saved
        """
        if tweets is None:
            tweets = self.scrape_tweets()

        saved = 0
        with get_db() as db:
            for tweet in tweets:
                try:
                    db.upsert_twitter_post(tweet)
                    saved += 1
                except Exception as e:
                    print(f"Error saving tweet: {e}")

            # Also save follower snapshot
            try:
                stats = self.scrape_profile_stats()
                db.add_follower_snapshot(
                    platform="twitter",
                    follower_count=stats.get("followers", 0),
                    following_count=stats.get("following", 0)
                )
            except Exception as e:
                print(f"Error saving follower stats: {e}")

        return saved


def main():
    """Test the Twitter scraper."""
    scraper = TwitterScraper()
    print(f"Username: @{scraper.username}")

    print("\nScraping tweets...")
    tweets = scraper.scrape_tweets(max_tweets=10)
    print(f"Found {len(tweets)} tweets")

    if tweets:
        print("\nSample tweet:")
        print(tweets[0])

        print("\nSaving to database...")
        saved = scraper.save_to_database(tweets)
        print(f"Saved {saved} tweets")


if __name__ == "__main__":
    main()
