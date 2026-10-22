import os
import textwrap
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
import cloudinary
import cloudinary.uploader
import requests
import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image, ImageDraw, ImageFont

from database import add_scheduled_post, init_db, list_scheduled_posts

BASE_DIR = Path(__file__).resolve().parent
IMAGE_PATH = BASE_DIR / "linkedin_post.png"
load_dotenv()
TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Kolkata"))

st.set_page_config(page_title="LinkedIn Post Automation", layout="wide")
init_db()
st.title("LinkedIn Post Automation System")
st.caption("Generate captions, create graphics, publish now, or schedule a post.")


def get_font(size, bold=False):
    names = ["arialbd.ttf", "Arial Bold.ttf"] if bold else ["arial.ttf", "Arial.ttf"]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def create_linkedin_image(topic, tone):
    width, height = 1200, 627
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    top, bottom = (9, 28, 61), (10, 102, 194)
    for y in range(height):
        ratio = y / (height - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        for x in range(width):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image)
    draw.ellipse((920, -170, 1350, 260), fill=(18, 83, 150))
    draw.ellipse((1000, 420, 1330, 750), fill=(15, 75, 140))
    draw.rounded_rectangle((70, 70, 180, 80), radius=5, fill=(93, 220, 255))
    draw.text((70, 105), "IDEAS THAT MOVE YOU FORWARD",
              font=get_font(25, True), fill=(160, 225, 255))
    lines = textwrap.wrap(topic.strip(), width=27)[:4] or ["LinkedIn Insights"]
    y = 190
    for line in lines:
        draw.text((70, y), line, font=get_font(55, True), fill="white")
        y += 72
    draw.rounded_rectangle((70, 500, 350, 550), radius=18, fill="white")
    draw.text((88, 510), f"{tone} Insights", font=get_font(23), fill=(9, 50, 95))
    draw.text((70, 575), "LINKEDIN POST AUTOMATION",
              font=get_font(17, True), fill=(210, 230, 250))
    return image


def upload_image_to_cloudinary(path):
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not all([cloud_name, api_key, api_secret]):
        raise ValueError("Check CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET in .env")
    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
    result = cloudinary.uploader.upload(str(path), resource_type="image", folder="linkedin-automation")
    url = result.get("secure_url")
    if not url:
        raise ValueError("Cloudinary did not return a secure URL.")
    return url


def publish_now(caption, image_url):
    """Submit a post through Ayrshare, not the direct LinkedIn API."""
    key = os.getenv("AYRSHARE_API_KEY")
    if not key:
        raise ValueError("AYRSHARE_API_KEY is missing from .env")
    payload = {"post": caption, "platforms": ["linkedin"]}
    if image_url:
        payload["mediaUrls"] = [image_url]
    response = requests.post(
        "https://api.ayrshare.com/api/post",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
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


if "generated_caption" not in st.session_state:
    st.session_state.generated_caption = ""
if "generated_image" not in st.session_state:
    st.session_state.generated_image = None

topic = st.text_input("Enter your post topic",
                      placeholder="Example: Why Python is important in Data Science")
tone = st.selectbox("Select post tone",
                    ["Professional", "Friendly", "Informative", "Motivational"])

if st.button("Generate Post", type="primary"):
    if not topic.strip():
        st.warning("Please enter a topic first.")
    elif not os.getenv("GEMINI_API_KEY"):
        st.error("GEMINI_API_KEY is missing from .env.")
    else:
        prompt = f"""Write an engaging LinkedIn post about: {topic}
Tone: {tone}
Requirements:
- Start with a strong hook.
- Use clear, natural and professional language.
- Use short paragraphs and readable formatting.
- Include relevant hashtags.
- Do not invent facts, statistics or personal experiences.
- Return only the LinkedIn post text."""
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        caption = None
        errors = []
        with st.spinner("Generating your caption..."):
            for model in ["gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.8-flash"]:
                try:
                    response = client.models.generate_content(model=model, contents=prompt)
                    if response.text and response.text.strip():
                        caption = response.text.strip()
                        st.success(f"Caption generated using {model}.")
                        break
                    errors.append(f"{model}: empty response")
                except Exception as error:
                    errors.append(f"{model}: {error}")
        if not caption:
            st.error("Caption generation failed.")
            with st.expander("Technical details"):
                st.write("\n\n".join(errors))
        else:
            image = create_linkedin_image(topic, tone)
            image.save(IMAGE_PATH)
            st.session_state.generated_caption = caption
            st.session_state.generated_image = image
            st.session_state.caption_editor = caption
            st.success("Caption and image generated!")

if st.session_state.generated_caption:
    st.divider()
    st.subheader("1. Edit your caption")
    caption = st.text_area("Caption", key="caption_editor", height=260)
    st.subheader("2. Generated image")
    if st.session_state.generated_image is not None:
        st.image(st.session_state.generated_image, caption="LinkedIn graphic preview", use_container_width=True)
        with open(IMAGE_PATH, "rb") as file:
            st.download_button("Download PNG", data=file.read(),
                               file_name="linkedin_post.png", mime="image/png")

    st.divider()
    st.subheader("3. Publish now")
    st.warning("This sends a real post. Review the caption before publishing.")
    confirm = st.checkbox("I reviewed the caption and want to publish now.")
    if st.button("Publish to LinkedIn now", disabled=not confirm or not caption.strip()):
        try:
            with st.spinner("Uploading image and publishing..."):
                url = upload_image_to_cloudinary(IMAGE_PATH)
                result = publish_now(caption.strip(), url)
            st.success("Ayrshare accepted the request. Verify LinkedIn platform status.")
            st.json(result)
        except Exception as error:
            st.error(f"Publishing failed: {error}")

    st.divider()
    st.subheader("4. Schedule a post")
    st.caption("The image is uploaded now so the background scheduler can access its public URL later.")
    today = datetime.now(TIMEZONE).date()
    publish_date = st.date_input("Publish date", value=today, min_value=today, key="publish_date")
    publish_time = st.time_input("Publish time (India time)", value=time(18, 0), key="publish_time")

    if st.button("Schedule LinkedIn Post", type="primary", disabled=not caption.strip()):
        scheduled = datetime.combine(publish_date, publish_time)
        now = datetime.now(TIMEZONE).replace(tzinfo=None)
        if scheduled <= now:
            st.error("Please choose a future date and time.")
        else:
            try:
                with st.spinner("Uploading image and saving schedule..."):
                    url = upload_image_to_cloudinary(IMAGE_PATH)
                    post_id = add_scheduled_post(caption.strip(), scheduled.isoformat(timespec="seconds"), url)
                st.success(f"Post scheduled. ID: {post_id}. Keep scheduler.py running.")
            except Exception as error:
                st.error(f"Could not schedule post: {error}")

st.divider()
st.subheader("5. Scheduled posts")
posts = list_scheduled_posts()
if posts:
    st.dataframe([{
        "ID": p["id"], "Caption": p["caption"], "Scheduled time": p["scheduled_time"],
        "Status": p["status"], "Error": p["error_message"] or ""
    } for p in posts], use_container_width=True, hide_index=True)
else:
    st.info("No scheduled posts yet.")
