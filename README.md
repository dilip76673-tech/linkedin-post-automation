# LinkedIn Post Automation System

This project helps users generate, design, publish, and schedule LinkedIn posts using Python and Streamlit.

**Features**
- ai caption generation using Gemini
- image creation using Pillow
- image hosting with Cloudinary
- post scheduling using APScheduler
- SQLite database for storing posts
- ayrshare integration for publishing

**Setup**
1. install dependencies: `pip install -r requirements.txt`
2. add API keys to `.env`.
3. run `streamlit run app.py`
4. in another terminal, run `python scheduler.py`

**Note:** publishing currently uses Ayrshare, not the official LinkedIn API. Keep `.env` private.