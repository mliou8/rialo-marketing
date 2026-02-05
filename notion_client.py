"""
Notion API client for managing Content Pipeline and Twitter Calendar databases.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()


class NotionManager:
    """Manager for Notion database operations."""

    def __init__(self):
        self.client = Client(auth=os.getenv("NOTION_TOKEN"))
        self.pipeline_db_id = os.getenv("PIPELINE_DB_ID")
        self.twitter_calendar_db_id = os.getenv("TWITTER_CALENDAR_DB_ID")

    # Content Pipeline Operations
    def add_to_pipeline(self, title: str, original_url: str, status: str = "Inspiration") -> dict:
        """
        Add a new item to the Content Pipeline database.

        Args:
            title: The title/topic of the content
            original_url: URL of the original LinkedIn post
            status: Status of the content (Inspiration, Drafted, Approved)

        Returns:
            The created page object
        """
        properties = {
            "Topic": {
                "title": [{"text": {"content": title}}]
            },
            "Status": {
                "select": {"name": status}
            },
            "Original URL": {
                "url": original_url
            }
        }

        return self.client.pages.create(
            parent={"database_id": self.pipeline_db_id},
            properties=properties
        )

    def get_pipeline_items(self, status: Optional[str] = None) -> list:
        """
        Get items from the Content Pipeline database.

        Args:
            status: Optional filter by status

        Returns:
            List of pipeline items
        """
        filter_params = {}
        if status:
            filter_params = {
                "filter": {
                    "property": "Status",
                    "select": {"equals": status}
                }
            }

        response = self.client.databases.query(
            database_id=self.pipeline_db_id,
            **filter_params
        )
        return response.get("results", [])

    def update_pipeline_status(self, page_id: str, status: str) -> dict:
        """Update the status of a pipeline item."""
        return self.client.pages.update(
            page_id=page_id,
            properties={
                "Status": {"select": {"name": status}}
            }
        )

    def update_pipeline_draft(self, page_id: str, draft: str) -> dict:
        """Update the draft content of a pipeline item."""
        return self.client.pages.update(
            page_id=page_id,
            properties={
                "Draft": {"rich_text": [{"text": {"content": draft}}]}
            }
        )

    # Twitter Calendar Operations
    def get_twitter_calendar_items(self, has_draft: bool = False) -> list:
        """
        Get items from the Twitter Calendar database.

        Args:
            has_draft: If True, only return items that already have drafts
                      If False, only return items without drafts

        Returns:
            List of calendar items
        """
        response = self.client.databases.query(
            database_id=self.twitter_calendar_db_id
        )

        results = response.get("results", [])

        if has_draft is not None:
            filtered = []
            for item in results:
                draft_prop = item.get("properties", {}).get("Draft", {})
                rich_text = draft_prop.get("rich_text", [])
                item_has_draft = len(rich_text) > 0 and rich_text[0].get("text", {}).get("content", "").strip()

                if has_draft and item_has_draft:
                    filtered.append(item)
                elif not has_draft and not item_has_draft:
                    filtered.append(item)

            return filtered

        return results

    def update_twitter_draft(self, page_id: str, draft: str) -> dict:
        """Update the draft content of a Twitter Calendar item."""
        return self.client.pages.update(
            page_id=page_id,
            properties={
                "Draft": {"rich_text": [{"text": {"content": draft[:2000]}}]}  # Notion limit
            }
        )

    def get_item_title(self, item: dict) -> str:
        """Extract the title from a Notion page item."""
        title_prop = item.get("properties", {}).get("Topic", {})
        if not title_prop:
            title_prop = item.get("properties", {}).get("Title", {})

        title_content = title_prop.get("title", [])
        if title_content:
            return title_content[0].get("text", {}).get("content", "")
        return ""


def get_notion() -> NotionManager:
    """Get a Notion manager instance."""
    return NotionManager()


if __name__ == "__main__":
    # Test the Notion client
    notion = get_notion()
    print("Notion client initialized successfully!")
    print(f"Pipeline DB ID: {notion.pipeline_db_id}")
    print(f"Twitter Calendar DB ID: {notion.twitter_calendar_db_id}")
