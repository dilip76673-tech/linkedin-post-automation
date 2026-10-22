import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

from database import get_connection, init_db

load_dotenv()
TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))


def publish_to_linkedin(caption, image_url):
    """Submit a post through Ayrshare (not a direct LinkedIn API integration)."""
    api_key = os.getenv("AYRSHARE_API_KEY")
    if not api_key:
        raise RuntimeError("AYRSHARE_API_KEY is missing from .env")

    payload = {"post": caption, "platforms": ["linkedin"]}
    if image_url:
        payload["mediaUrls"] = [image_url]

    response = requests.post(
        "https://api.ayrshare.com/api/post",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    try:
        result = response.json()
    except ValueError:
        result = {"response": response.text}

    if not response.ok:
        raise RuntimeError(f"Ayrshare HTTP {response.status_code}: {result}")
    return result


def process_due_posts():
    now_text = datetime.now(TIMEZONE).replace(tzinfo=None).isoformat(timespec="seconds")

    with get_connection() as connection:
        posts = connection.execute(
            """SELECT id, caption, scheduled_time, image_url
               FROM scheduled_posts
               WHERE status = 'pending'
                 AND scheduled_time <= ?
                 AND image_url IS NOT NULL
               ORDER BY scheduled_time, id""",
            (now_text,),
        ).fetchall()

    for post in posts:
        post_id = post["id"]
        with get_connection() as connection:
            claimed = connection.execute(
                """UPDATE scheduled_posts
                   SET status = 'processing', error_message = NULL
                   WHERE id = ? AND status = 'pending'""",
                (post_id,),
            )
            if claimed.rowcount != 1:
                continue

        try:
            result = publish_to_linkedin(post["caption"], post["image_url"])
            with get_connection() as connection:
                connection.execute(
                    """UPDATE scheduled_posts
                       SET status = 'submitted', error_message = ?
                       WHERE id = ?""",
                    (str(result)[:2000], post_id),
                )
            print(f"Post {post_id}: Ayrshare accepted the request; verify platform status.")
        except Exception as error:
            with get_connection() as connection:
                connection.execute(
                    """UPDATE scheduled_posts
                       SET status = 'failed', error_message = ?
                       WHERE id = ?""",
                    (str(error)[:2000], post_id),
                )
            print(f"Post {post_id} failed: {error}")


def main():
    init_db()
    scheduler = BlockingScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        process_due_posts,
        trigger="interval",
        seconds=10,
        id="process_due_posts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    print(f"Scheduler running in {TIMEZONE}; checking due posts every 10 seconds.")
    print("Keep this process running. Press Ctrl+C to stop.")
    try:
        process_due_posts()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("Scheduler stopped.")


if __name__ == "__main__":  
    main()


