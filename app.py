"""
Streamlit Dashboard for Marketing Analytics.
Displays data from local SQLite database with charts and leaderboards.
"""

import os
import sys
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import google.generativeai as genai

from database_manager import get_db
from supabase_content import get_content_manager
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.twitter_scraper import TwitterScraper
from config import GEMINI_API_KEY

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

load_dotenv()

# Page config
st.set_page_config(
    page_title="Marketing Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    .stMetric {
        background-color: #ffffff;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)


def refresh_data():
    """Trigger Apify scrapers to refresh data."""
    with st.spinner("Scraping LinkedIn posts..."):
        try:
            linkedin = LinkedInScraper()
            linkedin_count = linkedin.save_to_database()
            st.success(f"Saved {linkedin_count} LinkedIn posts")
        except Exception as e:
            st.error(f"LinkedIn scraping error: {e}")

    with st.spinner("Scraping Twitter posts..."):
        try:
            twitter = TwitterScraper()
            twitter_count = twitter.save_to_database()
            st.success(f"Saved {twitter_count} tweets")
        except Exception as e:
            st.error(f"Twitter scraping error: {e}")


def render_sidebar():
    """Render the sidebar with navigation and filters."""
    with st.sidebar:
        st.title("📊 Marketing Dashboard")
        st.markdown("---")

        # Page navigation
        page = st.radio(
            "Navigate",
            ["📈 Analytics", "✍️ Content Generator"],
            index=0,
            label_visibility="collapsed"
        )

        st.markdown("---")

        # Analytics-specific controls
        if page == "📈 Analytics":
            # Refresh data button
            if st.button("🔄 Refresh Data", use_container_width=True):
                refresh_data()
                st.rerun()

            st.markdown("---")

            # Platform filter
            platform = st.selectbox(
                "Platform",
                ["All", "LinkedIn", "Twitter"],
                index=0
            )

            # Date range filter
            date_range = st.selectbox(
                "Date Range",
                ["Last 7 days", "Last 30 days", "Last 90 days", "All time"],
                index=1
            )
        else:
            platform = "All"
            date_range = "All time"

        st.markdown("---")
        st.markdown("**Last Updated**")
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M"))

        return page, platform, date_range


def render_metrics(db):
    """Render the top metrics cards."""
    stats = db.get_stats_summary()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Posts",
            value=f"{stats['total_posts']:,}",
            delta=None
        )

    with col2:
        st.metric(
            label="Total Views",
            value=f"{stats['total_views']:,}",
            delta=None
        )

    with col3:
        st.metric(
            label="LinkedIn Posts",
            value=f"{stats['linkedin_posts']:,}",
            delta=f"{stats['total_linkedin_views']:,} views"
        )

    with col4:
        st.metric(
            label="Twitter Posts",
            value=f"{stats['twitter_posts']:,}",
            delta=f"{stats['total_twitter_views']:,} views"
        )


def render_follower_chart(db, platform_filter: str):
    """Render follower growth line chart."""
    st.subheader("📈 Follower Growth")

    platform = None if platform_filter == "All" else platform_filter.lower()
    df = db.get_follower_history(platform=platform)

    if df.empty:
        st.info("No follower data available. Click 'Refresh Data' to scrape your profiles.")
        return

    fig = px.line(
        df,
        x="recorded_at",
        y="follower_count",
        color="platform" if platform_filter == "All" else None,
        title="Follower Count Over Time",
        labels={
            "recorded_at": "Date",
            "follower_count": "Followers",
            "platform": "Platform"
        }
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Follower Count",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)


def render_impressions_chart(db, platform_filter: str):
    """Render daily impressions line chart."""
    st.subheader("👁️ Daily Impressions")

    platform = None if platform_filter == "All" else platform_filter.lower()
    df = db.get_impressions_history(platform=platform)

    if df.empty:
        # Generate impressions from post data as fallback
        st.info("No daily impression data. Showing aggregated post views instead.")

        # Aggregate from posts
        linkedin_posts = db.get_linkedin_posts(limit=500)
        twitter_posts = db.get_twitter_posts(limit=500)

        data = []
        for post in linkedin_posts:
            if post.date_posted:
                data.append({
                    "date": post.date_posted.date(),
                    "views": post.views or 0,
                    "platform": "LinkedIn"
                })
        for post in twitter_posts:
            if post.date_posted:
                data.append({
                    "date": post.date_posted.date(),
                    "views": post.views or 0,
                    "platform": "Twitter"
                })

        if not data:
            st.warning("No post data available.")
            return

        df = pd.DataFrame(data)
        df = df.groupby(["date", "platform"]).sum().reset_index()

        if platform_filter != "All":
            df = df[df["platform"] == platform_filter]

    fig = px.bar(
        df,
        x="date",
        y="views" if "views" in df.columns else "total_impressions",
        color="platform" if platform_filter == "All" else None,
        title="Views by Date",
        labels={
            "date": "Date",
            "views": "Views",
            "total_impressions": "Impressions",
            "platform": "Platform"
        }
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Views",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)


def render_top_posts(db, platform_filter: str):
    """Render top performing posts leaderboard."""
    st.subheader("🏆 Top Performing Posts")

    # Tabs for different metrics
    tab1, tab2, tab3 = st.tabs(["By Views", "By Engagement", "By Likes"])

    with tab1:
        render_leaderboard(db, platform_filter, "views")

    with tab2:
        render_leaderboard(db, platform_filter, "engagement")

    with tab3:
        render_leaderboard(db, platform_filter, "likes")


def render_leaderboard(db, platform_filter: str, sort_by: str):
    """Render a single leaderboard view."""
    df = db.get_combined_top_posts(limit=20)

    if df.empty:
        st.info("No posts available. Click 'Refresh Data' to scrape your profiles.")
        return

    # Filter by platform if needed
    if platform_filter != "All":
        df = df[df["platform"] == platform_filter]

    if df.empty:
        st.info(f"No {platform_filter} posts available.")
        return

    # Sort by metric
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)

    # Display as table with styling
    for idx, row in df.head(10).iterrows():
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 4, 1, 1])

            with col1:
                rank = df.index.get_loc(idx) + 1 if isinstance(df.index, pd.RangeIndex) else idx + 1
                platform_emoji = "🔵" if row["platform"] == "LinkedIn" else "🐦"
                st.markdown(f"**#{rank}** {platform_emoji}")

            with col2:
                content = row["content"] if row["content"] else "No content"
                st.markdown(f"**{content}**")
                if row["url"]:
                    st.markdown(f"[View Post]({row['url']})")

            with col3:
                st.metric("Views", f"{row['views']:,}")

            with col4:
                st.metric("Engagement", f"{row['engagement']:,}")

            st.markdown("---")


def render_recent_activity(db):
    """Render recent posts section."""
    st.subheader("🕐 Recent Activity")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**LinkedIn**")
        linkedin_posts = db.get_linkedin_posts(limit=5)
        if linkedin_posts:
            for post in linkedin_posts:
                with st.expander(f"{post.content[:50] if post.content else 'Post'}..."):
                    st.write(f"**Views:** {post.views:,}")
                    st.write(f"**Likes:** {post.likes:,}")
                    st.write(f"**Comments:** {post.comments:,}")
                    st.write(f"**Date:** {post.date_posted}")
                    if post.url:
                        st.markdown(f"[View on LinkedIn]({post.url})")
        else:
            st.info("No LinkedIn posts found")

    with col2:
        st.markdown("**Twitter**")
        twitter_posts = db.get_twitter_posts(limit=5)
        if twitter_posts:
            for post in twitter_posts:
                with st.expander(f"{post.content[:50] if post.content else 'Tweet'}..."):
                    st.write(f"**Views:** {post.views:,}")
                    st.write(f"**Likes:** {post.likes:,}")
                    st.write(f"**Retweets:** {post.retweets:,}")
                    st.write(f"**Date:** {post.date_posted}")
                    if post.url:
                        st.markdown(f"[View on Twitter]({post.url})")
        else:
            st.info("No tweets found")


# ============== Content Generator Functions ==============

def generate_tweet_for_topic(topic: str) -> str:
    """Generate a tweet using Gemini."""
    if not GEMINI_API_KEY:
        return "[Error: GEMINI_API_KEY not configured]"

    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""Write a single tweet about the following topic. The tweet should be:
- Under 280 characters
- Professional but engaging
- Include 1-2 relevant hashtags if appropriate

Topic: {topic}

Respond with ONLY the tweet text, nothing else."""

    response = model.generate_content(prompt)
    return response.text.strip()


def render_content_generator():
    """Render the content generator page."""
    st.title("✍️ Content Generator")
    st.markdown("Add topics and generate tweet drafts with AI")
    st.markdown("---")

    # Add new topics
    st.subheader("Add Topics")

    tab_single, tab_bulk = st.tabs(["Single Topic", "Bulk Add"])

    with tab_single:
        with st.form("add_topic_form", clear_on_submit=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_topic = st.text_input("Topic/Title", placeholder="Enter a topic or theme for a tweet...")
            with col2:
                st.write("")  # Spacing
                submit = st.form_submit_button("Add", use_container_width=True)

            if submit and new_topic.strip():
                with get_content_manager() as cm:
                    cm.add_to_twitter_calendar(topic=new_topic.strip())
                st.success(f"Added: {new_topic}")
                st.rerun()

    with tab_bulk:
        with st.form("bulk_add_form", clear_on_submit=True):
            bulk_topics = st.text_area(
                "Topics (one per line)",
                placeholder="Topic 1\nTopic 2\nTopic 3",
                height=150
            )
            bulk_submit = st.form_submit_button("Add All Topics", use_container_width=True)

            if bulk_submit and bulk_topics.strip():
                topics = [t.strip() for t in bulk_topics.strip().split("\n") if t.strip()]
                if topics:
                    with get_content_manager() as cm:
                        for topic in topics:
                            cm.add_to_twitter_calendar(topic=topic)
                    st.success(f"Added {len(topics)} topics!")
                    st.rerun()

    st.markdown("---")

    # Two columns: Pending topics and Generated drafts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📝 Pending Topics")
        with get_content_manager() as cm:
            pending_items = cm.get_twitter_calendar_items(has_draft=False)

        if pending_items:
            st.info(f"{len(pending_items)} topics waiting for content")

            # Generate content button
            if st.button("🚀 Generate Content", type="primary", use_container_width=True):
                progress = st.progress(0)
                status = st.empty()

                with get_content_manager() as cm:
                    for i, item in enumerate(pending_items):
                        topic = cm.get_item_title(item)
                        status.text(f"Generating for: {topic[:50]}...")

                        try:
                            tweet = generate_tweet_for_topic(topic)
                            cm.update_twitter_draft(item["id"], tweet)
                        except Exception as e:
                            st.error(f"Error generating for '{topic}': {e}")

                        progress.progress((i + 1) / len(pending_items))

                status.text("Done!")
                st.success(f"Generated {len(pending_items)} tweets!")
                st.rerun()

            # List pending topics
            for item in pending_items:
                topic = item.get("properties", {}).get("Topic", {}).get("title", [{}])[0].get("text", {}).get("content", "")
                with st.container():
                    cols = st.columns([4, 1])
                    with cols[0]:
                        st.write(f"• {topic}")
                    with cols[1]:
                        if st.button("🗑️", key=f"del_{item['id']}", help="Delete topic"):
                            # Delete functionality could be added here
                            pass
        else:
            st.info("No pending topics. Add some above!")

    with col2:
        st.subheader("✅ Generated Drafts")
        with get_content_manager() as cm:
            drafted_items = cm.get_twitter_calendar_items(has_draft=True)

        if drafted_items:
            st.success(f"{len(drafted_items)} drafts ready")

            for item in drafted_items:
                topic = item.get("properties", {}).get("Topic", {}).get("title", [{}])[0].get("text", {}).get("content", "")
                draft = item.get("properties", {}).get("Draft", {}).get("rich_text", [{}])
                draft_text = draft[0].get("text", {}).get("content", "") if draft else ""

                with st.expander(f"📌 {topic[:40]}..." if len(topic) > 40 else f"📌 {topic}"):
                    st.markdown("**Topic:**")
                    st.write(topic)
                    st.markdown("**Generated Tweet:**")
                    st.code(draft_text, language=None)

                    # Copy button
                    st.button("📋 Copy", key=f"copy_{item['id']}",
                              on_click=lambda t=draft_text: st.write(t),
                              help="Click to show tweet for copying")

                    # Regenerate button
                    if st.button("🔄 Regenerate", key=f"regen_{item['id']}"):
                        with st.spinner("Regenerating..."):
                            with get_content_manager() as cm:
                                new_tweet = generate_tweet_for_topic(topic)
                                cm.update_twitter_draft(item["id"], new_tweet)
                        st.rerun()
        else:
            st.info("No drafts yet. Generate content from pending topics!")


def main():
    """Main dashboard function."""
    # Sidebar
    page, platform_filter, date_range = render_sidebar()

    if page == "✍️ Content Generator":
        render_content_generator()
    else:
        # Analytics page
        st.title("📊 Marketing Analytics Dashboard")
        st.markdown("Track your LinkedIn and Twitter performance metrics")
        st.markdown("---")

        with get_db() as db:
            # Top metrics
            render_metrics(db)

            st.markdown("---")

            # Charts row
            col1, col2 = st.columns(2)

            with col1:
                render_follower_chart(db, platform_filter)

            with col2:
                render_impressions_chart(db, platform_filter)

            st.markdown("---")

            # Top posts leaderboard
            render_top_posts(db, platform_filter)

            st.markdown("---")

            # Recent activity
            render_recent_activity(db)


if __name__ == "__main__":
    main()
