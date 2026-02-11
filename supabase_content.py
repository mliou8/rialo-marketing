"""
Supabase-based content manager that replaces Notion for Content Pipeline and Twitter Calendar.
Provides the same API as notion_client.py for easy migration.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from database_manager import Base, Session, engine


class ContentPipeline(Base):
    """Model for content pipeline items (replaces Notion Content Pipeline)."""
    __tablename__ = "content_pipeline"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    topic = Column(Text, nullable=False)
    original_url = Column(Text)
    status = Column(String(50), default="Inspiration")
    draft = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TwitterCalendar(Base):
    """Model for Twitter calendar items (replaces Notion Twitter Calendar)."""
    __tablename__ = "twitter_calendar"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    topic = Column(Text, nullable=False)
    draft = Column(Text)
    scheduled_date = Column(Date)
    status = Column(String(50), default="Pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Create tables if they don't exist
Base.metadata.create_all(engine)


class ContentManager:
    """
    Manager for content operations using Supabase.
    API is compatible with NotionManager for easy migration.
    """

    def __init__(self):
        self.session = Session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the database session."""
        self.session.close()

    # Content Pipeline Operations
    def add_to_pipeline(self, title: str, original_url: str, status: str = "Inspiration") -> dict:
        """
        Add a new item to the Content Pipeline.

        Args:
            title: The title/topic of the content
            original_url: URL of the original LinkedIn post
            status: Status of the content (Inspiration, Drafted, Approved, Published)

        Returns:
            Dict with the created item's id
        """
        item = ContentPipeline(
            topic=title,
            original_url=original_url,
            status=status
        )
        self.session.add(item)
        self.session.commit()
        return {"id": str(item.id), "topic": item.topic, "status": item.status}

    def get_pipeline_items(self, status: Optional[str] = None) -> list:
        """
        Get items from the Content Pipeline.

        Args:
            status: Optional filter by status

        Returns:
            List of pipeline items in Notion-compatible format
        """
        query = self.session.query(ContentPipeline)
        if status:
            query = query.filter(ContentPipeline.status == status)

        items = query.order_by(ContentPipeline.created_at.desc()).all()

        # Return in a format compatible with the Notion API structure
        return [self._pipeline_to_notion_format(item) for item in items]

    def update_pipeline_status(self, page_id: str, status: str) -> dict:
        """Update the status of a pipeline item."""
        item = self.session.query(ContentPipeline).filter(
            ContentPipeline.id == page_id
        ).first()

        if item:
            item.status = status
            self.session.commit()
            return {"id": str(item.id), "status": item.status}
        return {}

    def update_pipeline_draft(self, page_id: str, draft: str) -> dict:
        """Update the draft content of a pipeline item."""
        item = self.session.query(ContentPipeline).filter(
            ContentPipeline.id == page_id
        ).first()

        if item:
            item.draft = draft
            item.status = "Drafted"
            self.session.commit()
            return {"id": str(item.id), "draft": item.draft}
        return {}

    # Twitter Calendar Operations
    def add_to_twitter_calendar(self, topic: str, scheduled_date: Optional[datetime] = None) -> dict:
        """
        Add a new item to the Twitter Calendar.

        Args:
            topic: The topic/title for the tweet
            scheduled_date: Optional scheduled date

        Returns:
            Dict with the created item's id
        """
        item = TwitterCalendar(
            topic=topic,
            scheduled_date=scheduled_date
        )
        self.session.add(item)
        self.session.commit()
        return {"id": str(item.id), "topic": item.topic}

    def get_twitter_calendar_items(self, has_draft: Optional[bool] = None) -> list:
        """
        Get items from the Twitter Calendar.

        Args:
            has_draft: If True, only return items that already have drafts
                      If False, only return items without drafts
                      If None, return all items

        Returns:
            List of calendar items in Notion-compatible format
        """
        query = self.session.query(TwitterCalendar)

        if has_draft is True:
            query = query.filter(TwitterCalendar.draft.isnot(None), TwitterCalendar.draft != "")
        elif has_draft is False:
            query = query.filter((TwitterCalendar.draft.is_(None)) | (TwitterCalendar.draft == ""))

        items = query.order_by(TwitterCalendar.scheduled_date.asc().nullslast()).all()

        return [self._calendar_to_notion_format(item) for item in items]

    def update_twitter_draft(self, page_id: str, draft: str) -> dict:
        """Update the draft content of a Twitter Calendar item."""
        item = self.session.query(TwitterCalendar).filter(
            TwitterCalendar.id == page_id
        ).first()

        if item:
            item.draft = draft[:2000]  # Same limit as Notion
            item.status = "Drafted"
            self.session.commit()
            return {"id": str(item.id), "draft": item.draft}
        return {}

    def get_item_title(self, item: dict) -> str:
        """Extract the title from an item (Notion-compatible format)."""
        # Handle Notion-compatible format
        props = item.get("properties", {})
        topic_prop = props.get("Topic", {}) or props.get("Title", {})
        title_content = topic_prop.get("title", [])
        if title_content:
            return title_content[0].get("text", {}).get("content", "")

        # Handle direct format
        return item.get("topic", "")

    # Helper methods to convert to Notion-compatible format
    def _pipeline_to_notion_format(self, item: ContentPipeline) -> dict:
        """Convert a ContentPipeline item to Notion-compatible format."""
        return {
            "id": str(item.id),
            "properties": {
                "Topic": {
                    "title": [{"text": {"content": item.topic or ""}}]
                },
                "Status": {
                    "select": {"name": item.status or "Inspiration"}
                },
                "Original URL": {
                    "url": item.original_url
                },
                "Draft": {
                    "rich_text": [{"text": {"content": item.draft or ""}}] if item.draft else []
                }
            },
            "created_time": item.created_at.isoformat() if item.created_at else None,
            "last_edited_time": item.updated_at.isoformat() if item.updated_at else None
        }

    def _calendar_to_notion_format(self, item: TwitterCalendar) -> dict:
        """Convert a TwitterCalendar item to Notion-compatible format."""
        return {
            "id": str(item.id),
            "properties": {
                "Topic": {
                    "title": [{"text": {"content": item.topic or ""}}]
                },
                "Status": {
                    "select": {"name": item.status or "Pending"}
                },
                "Draft": {
                    "rich_text": [{"text": {"content": item.draft or ""}}] if item.draft else []
                },
                "Scheduled Date": {
                    "date": {"start": item.scheduled_date.isoformat()} if item.scheduled_date else None
                }
            },
            "created_time": item.created_at.isoformat() if item.created_at else None,
            "last_edited_time": item.updated_at.isoformat() if item.updated_at else None
        }


def get_content_manager() -> ContentManager:
    """Get a content manager instance."""
    return ContentManager()


if __name__ == "__main__":
    # Test the content manager
    print("Testing Supabase content manager...")
    with get_content_manager() as cm:
        print("Content manager initialized successfully!")

        # Test adding a pipeline item
        result = cm.add_to_pipeline(
            title="Test Topic",
            original_url="https://example.com/post",
            status="Inspiration"
        )
        print(f"Added pipeline item: {result}")

        # Test getting pipeline items
        items = cm.get_pipeline_items()
        print(f"Pipeline items: {len(items)}")
