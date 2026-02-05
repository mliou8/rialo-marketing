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

from database_manager import get_db
from scrapers.linkedin_scraper import LinkedInScraper
from scrapers.twitter_scraper import TwitterScraper

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
    """Render the sidebar with refresh button and filters."""
    with st.sidebar:
        st.title("📊 Marketing Dashboard")
        st.markdown("---")

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

        st.markdown("---")
        st.markdown("**Last Updated**")
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M"))

        return platform, date_range


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


def main():
    """Main dashboard function."""
    # Sidebar
    platform_filter, date_range = render_sidebar()

    # Main content
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
