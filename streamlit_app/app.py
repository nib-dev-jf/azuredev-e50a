import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Iterator

import httpx
import streamlit as st

# Load environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

st.set_page_config(
    page_title="AI Chat Pro",
    page_icon="💬",
    layout="wide"
)

# Constants / Config
DEFAULT_API_BASE = os.getenv("CHAT_API_BASE_URL", "http://localhost:8000")
API_CHAT_ENDPOINT = "/chat"
BASIC_USER = os.getenv("WEB_APP_USERNAME")
BASIC_PASS = os.getenv("WEB_APP_PASSWORD")
DEFAULT_MODEL = os.getenv("AZURE_AI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini")

# Inject CSS
css_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------- Session State Initialization ----------
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, Any]] = []
if "conversation_name" not in st.session_state:
    st.session_state.conversation_name = "Session 1"
if "streaming" not in st.session_state:
    st.session_state.streaming = False
if "api_base" not in st.session_state:
    st.session_state.api_base = DEFAULT_API_BASE
if "model" not in st.session_state:
    st.session_state.model = DEFAULT_MODEL
if "token_usage" not in st.session_state:
    st.session_state.token_usage = {"input": 0, "output": 0}

# ---------- Helpers ----------

def sse_events(client: httpx.Client, url: str, json_payload: Dict[str, Any], auth: Optional[tuple[str,str]]) -> Iterator[Dict[str, Any]]:
    headers = {"Accept": "text/event-stream"}
    with client.stream("POST", url, json=json_payload, headers=headers, auth=auth, timeout=90.0) as r:
        for raw_line in r.iter_lines():
            if not raw_line:
                continue
            if raw_line.startswith(":"):
                continue
            if raw_line.startswith("data:"):
                data = raw_line[5:].strip()
                try:
                    evt = json.loads(data)
                except json.JSONDecodeError:
                    continue
                yield evt


def render_messages(container):
    with container:
        for m in st.session_state.messages:
            role = m.get("role")
            content = m.get("content", "")
            bubble_role = "assistant" if role != "user" else "user"
            st.markdown(
                f"<div class='chat-bubble {bubble_role}'>" \
                f"<h4>{role.title()}</h4>" \
                f"{content}" \
                f"</div>", unsafe_allow_html=True
            )


def export_json() -> str:
    return json.dumps({
        "name": st.session_state.conversation_name,
        "created": datetime.utcnow().isoformat(),
        "messages": st.session_state.messages
    }, indent=2)


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown("<span class='badge'>SESSION</span>", unsafe_allow_html=True)
    st.text_input("Conversation name", key="conversation_name")
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.token_usage = {"input":0,"output":0}
        st.session_state.conversation_name = f"Session {datetime.utcnow().strftime('%H%M%S')}"
        st.rerun()

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<span class='badge'>BACKEND</span>", unsafe_allow_html=True)
    st.text_input("API Base", key="api_base")
    st.text_input("Model", key="model")
    rag_enabled = st.toggle("RAG Context", value=True, help="Uses search index if server configured.")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<span class='badge'>ACTIONS</span>", unsafe_allow_html=True)
    if st.download_button("⬇️ Export Chat JSON", data=export_json(), file_name="chat_export.json", mime="application/json"):
        pass
    if st.button("🗑️ Clear Messages"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.markdown("<span class='badge'>USAGE</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='token-box'>Input: {st.session_state.token_usage['input']} • Output: {st.session_state.token_usage['output']}</div>", unsafe_allow_html=True)

    st.caption("If Basic Auth is configured on the API, set WEB_APP_USERNAME & WEB_APP_PASSWORD.")

# ---------- Main Layout ----------
col_chat, col_meta = st.columns([4,1])
chat_container = col_chat.container()
render_messages(chat_container)

if st.session_state.streaming:
    with chat_container:
        st.markdown("<div class='streaming-indicator'><div class='dot'></div><div class='dot'></div><div class='dot'></div>Generating</div>", unsafe_allow_html=True)

# ---------- Input / Interaction ----------
prompt = st.chat_input("Type your message and press Enter...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state.streaming = True
    st.rerun()

# ---------- Streaming logic on rerun ----------
if st.session_state.streaming:
    messages_payload = [
        {"role": m["role"], "content": m["content"]} for m in st.session_state.messages
    ]
    url = st.session_state.api_base.rstrip('/') + API_CHAT_ENDPOINT
    auth = (BASIC_USER, BASIC_PASS) if BASIC_USER and BASIC_PASS else None

    accumulated = ""
    placeholder = chat_container.empty()

    try:
        with httpx.Client() as client:
            for evt in sse_events(client, url, {"messages": messages_payload}, auth):
                etype = evt.get("type")
                if etype == "message":
                    piece = evt.get("content", "")
                    accumulated += piece
                    placeholder.markdown(
                        f"<div class='chat-bubble assistant'><h4>Assistant</h4>{accumulated}</div>",
                        unsafe_allow_html=True
                    )
                elif etype == "completed_message":
                    accumulated = evt.get("content", accumulated)
                elif etype == "stream_end":
                    break
    except Exception as e:
        placeholder.markdown(
            f"<div class='chat-bubble assistant'><h4>Error</h4>{str(e)}</div>",
            unsafe_allow_html=True
        )
    finally:
        st.session_state.messages.append({"role": "assistant", "content": accumulated})
        st.session_state.streaming = False
        st.rerun()

st.markdown("<div class='footer-note'>AI Chat Pro • Streamlit • Azure Backend • Professional UI</div>", unsafe_allow_html=True)
