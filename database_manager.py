"""
Database manager for storing analytics data in Supabase (PostgreSQL).
Stores LinkedIn and Twitter post metrics persistently in the cloud.
"""

import os
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import pandas as pd

from config import DATABASE_URL

# Database setup - use Supabase PostgreSQL
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not configured. Please set it in your .env or Streamlit secrets.")

# Create engine with connection pooling for cloud deployment
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections after 30 minutes
    echo=False
)

Session = sessionmaker(bind=engine)
Base = declarative_base()


class LinkedInPost(Base):
    """Model for LinkedIn post metrics."""
    __tablename__ = "linkedin_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(Text)
    content = Column(Text)
    date_posted = Column(DateTime)
    views = Column(BigInteger, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    reposts = Column(Integer, default=0)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class TwitterPost(Base):
    """Model for Twitter/X post metrics."""
    __tablename__ = "twitter_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tweet_id = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(Text)
    content = Column(Text)
    date_posted = Column(DateTime)
    views = Column(BigInteger, default=0)
    likes = Column(Integer, default=0)
    retweets = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    quotes = Column(Integer, default=0)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class FollowerSnapshot(Base):
    """Model for tracking follower counts over time."""
    __tablename__ = "follower_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    follower_count = Column(Integer, nullable=False)
    following_count = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow, index=True)


class DailyImpressions(Base):
    """Model for daily impression aggregates."""
    __tablename__ = "daily_impressions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    total_impressions = Column(BigInteger, default=0)
    total_engagements = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


# Create tables if they don't exist
Base.metadata.create_all(engine)


class DatabaseManager:
    """Manager class for all database operations."""

    def __init__(self):
        self.session = Session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the database session."""
        self.session.close()

    # LinkedIn Operations
    def upsert_linkedin_post(self, post_data: dict) -> LinkedInPost:
        """Insert or update a LinkedIn post."""
        existing = self.session.query(LinkedInPost).filter_by(
            post_id=post_data["post_id"]
        ).first()

        if existing:
            for key, value in post_data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.scraped_at = datetime.utcnow()
        else:
            existing = LinkedInPost(**post_data)
            self.session.add(existing)

        self.session.commit()
        return existing

    def get_linkedin_posts(self, limit: int = 100) -> list[LinkedInPost]:
        """Get LinkedIn posts ordered by date."""
        return self.session.query(LinkedInPost).order_by(
            LinkedInPost.date_posted.desc()
        ).limit(limit).all()

    def get_top_linkedin_posts(self, metric: str = "views", limit: int = 10) -> list[LinkedInPost]:
        """Get top performing LinkedIn posts by a specific metric."""
        order_col = getattr(LinkedInPost, metric, LinkedInPost.views)
        return self.session.query(LinkedInPost).order_by(
            order_col.desc()
        ).limit(limit).all()

    # Twitter Operations
    def upsert_twitter_post(self, post_data: dict) -> TwitterPost:
        """Insert or update a Twitter post."""
        existing = self.session.query(TwitterPost).filter_by(
            tweet_id=post_data["tweet_id"]
        ).first()

        if existing:
            for key, value in post_data.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.scraped_at = datetime.utcnow()
        else:
            existing = TwitterPost(**post_data)
            self.session.add(existing)

        self.session.commit()
        return existing

    def get_twitter_posts(self, limit: int = 100) -> list[TwitterPost]:
        """Get Twitter posts ordered by date."""
        return self.session.query(TwitterPost).order_by(
            TwitterPost.date_posted.desc()
        ).limit(limit).all()

    def get_top_twitter_posts(self, metric: str = "views", limit: int = 10) -> list[TwitterPost]:
        """Get top performing Twitter posts by a specific metric."""
        order_col = getattr(TwitterPost, metric, TwitterPost.views)
        return self.session.query(TwitterPost).order_by(
            order_col.desc()
        ).limit(limit).all()

    # Follower Operations
    def add_follower_snapshot(self, platform: str, follower_count: int, following_count: int = 0):
        """Record a follower count snapshot."""
        snapshot = FollowerSnapshot(
            platform=platform,
            follower_count=follower_count,
            following_count=following_count
        )
        self.session.add(snapshot)
        self.session.commit()
        return snapshot

    def get_follower_history(self, platform: Optional[str] = None, days: int = 30) -> pd.DataFrame:
        """Get follower history as a DataFrame."""
        query = self.session.query(FollowerSnapshot)
        if platform:
            query = query.filter_by(platform=platform)

        snapshots = query.order_by(FollowerSnapshot.recorded_at.desc()).all()

        data = [{
            "platform": s.platform,
            "follower_count": s.follower_count,
            "following_count": s.following_count,
            "recorded_at": s.recorded_at
        } for s in snapshots]

        return pd.DataFrame(data)

    # Impressions Operations
    def add_daily_impressions(self, platform: str, date: datetime,
                               total_impressions: int, total_engagements: int = 0):
        """Record daily impression data."""
        impression = DailyImpressions(
            platform=platform,
            date=date,
            total_impressions=total_impressions,
            total_engagements=total_engagements
        )
        self.session.add(impression)
        self.session.commit()
        return impression

    def get_impressions_history(self, platform: Optional[str] = None, days: int = 30) -> pd.DataFrame:
        """Get impressions history as a DataFrame."""
        query = self.session.query(DailyImpressions)
        if platform:
            query = query.filter_by(platform=platform)

        impressions = query.order_by(DailyImpressions.date.desc()).all()

        data = [{
            "platform": i.platform,
            "date": i.date,
            "total_impressions": i.total_impressions,
            "total_engagements": i.total_engagements,
            "recorded_at": i.recorded_at
        } for i in impressions]

        return pd.DataFrame(data)

    # Analytics Helpers
    def get_combined_top_posts(self, limit: int = 10) -> pd.DataFrame:
        """Get combined top posts from both platforms."""
        linkedin_posts = self.get_top_linkedin_posts(limit=limit)
        twitter_posts = self.get_top_twitter_posts(limit=limit)

        data = []

        for post in linkedin_posts:
            data.append({
                "platform": "LinkedIn",
                "content": post.content[:100] + "..." if post.content and len(post.content) > 100 else post.content,
                "url": post.url,
                "views": post.views or 0,
                "likes": post.likes or 0,
                "date": post.date_posted,
                "engagement": (post.likes or 0) + (post.comments or 0) + (post.reposts or 0)
            })

        for post in twitter_posts:
            data.append({
                "platform": "Twitter",
                "content": post.content[:100] + "..." if post.content and len(post.content) > 100 else post.content,
                "url": post.url,
                "views": post.views or 0,
                "likes": post.likes or 0,
                "date": post.date_posted,
                "engagement": (post.likes or 0) + (post.retweets or 0) + (post.replies or 0) + (post.quotes or 0)
            })

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("views", ascending=False).head(limit)
        return df

    def get_stats_summary(self) -> dict:
        """Get a summary of all stats."""
        linkedin_count = self.session.query(LinkedInPost).count()
        twitter_count = self.session.query(TwitterPost).count()

        linkedin_total_views = self.session.query(
            LinkedInPost
        ).with_entities(
            LinkedInPost.views
        ).all()
        linkedin_views = sum(v[0] or 0 for v in linkedin_total_views)

        twitter_total_views = self.session.query(
            TwitterPost
        ).with_entities(
            TwitterPost.views
        ).all()
        twitter_views = sum(v[0] or 0 for v in twitter_total_views)

        return {
            "linkedin_posts": linkedin_count,
            "twitter_posts": twitter_count,
            "total_linkedin_views": linkedin_views,
            "total_twitter_views": twitter_views,
            "total_posts": linkedin_count + twitter_count,
            "total_views": linkedin_views + twitter_views
        }


# Convenience function for quick access
def get_db() -> DatabaseManager:
    """Get a database manager instance."""
    return DatabaseManager()


if __name__ == "__main__":
    # Test the database connection
    print("Testing Supabase connection...")
    with get_db() as db:
        print("Connected to Supabase successfully!")
        print(f"Stats: {db.get_stats_summary()}")
