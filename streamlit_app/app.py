import os
from datetime import datetime
from typing import Any, List, Dict

import streamlit as st
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Helpers ---------------------------------------------------------------

def _env(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    v = v.strip()
    return v if v else None

def _get_bool(env_name: str, default: bool) -> bool:
    val = os.getenv(env_name)
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")

def _get_int(env_name: str, default: int) -> int:
    try:
        return int(os.getenv(env_name, str(default)))
    except ValueError:
        return default

def _first_nonempty(*values):
    for v in values:
        if v:
            return v
    return None

# --- Model configuration (non-blocking) -----------------------------------
endpoint = _env("ENDPOINT_URL")
deployment = _env("DEPLOYMENT_NAME")
subscription_key = _env("AZURE_OPENAI_API_KEY")

client: AzureOpenAI | None = None
if endpoint and deployment and subscription_key:
    try:
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=subscription_key,
            api_version="2025-01-01-preview",
        )
        st.success(f"✅ Connected to Azure OpenAI: {deployment}")
    except Exception as e:
        client = None
        st.warning(
            f"⚠️ Could not initialize Azure OpenAI client: {e}. The app will still load, but chatting is disabled until configuration is fixed."
        )
else:
    st.info(
        "ℹ️ Model configuration not found. Set ENDPOINT_URL, DEPLOYMENT_NAME, and AZURE_OPENAI_API_KEY in your .env to enable chatting."
    )

# --- Optional: Azure AI Search (On Your Data) ------------------------------
search_endpoint = _first_nonempty(
    os.getenv("SEARCH_ENDPOINT"),
    os.getenv("AZURE_AI_SEARCH_ENDPOINT"),
)
search_index = _first_nonempty(
    os.getenv("SEARCH_INDEX_NAME"),
    os.getenv("AZURE_AI_SEARCH_INDEX_NAME"),
)
search_key = _first_nonempty(
    os.getenv("SEARCH_KEY"),
    os.getenv("AZURE_AI_SEARCH_ADMIN_KEY"),
    os.getenv("AZURE_AI_SEARCH_API_KEY"),
)

semantic_configuration = os.getenv("AZURE_AI_SEARCH_SEMANTIC_CONFIGURATION", "default")
query_type = os.getenv("AZURE_AI_SEARCH_QUERY_TYPE", "simple")
in_scope = _get_bool("AZURE_AI_SEARCH_IN_SCOPE", True)
strictness = _get_int("AZURE_AI_SEARCH_STRICTNESS", 3)
top_n_documents = _get_int("AZURE_AI_SEARCH_TOPN", 5)

def build_azure_search_extra_body(role_information: str | None = None):
    """Build extra_body for Azure OpenAI 'On Your Data' with Azure AI Search.

    Returns None if search is not fully configured.
    """
    if not (search_endpoint and search_index and search_key):
        return None

    params: Dict[str, Any] = {
        "endpoint": search_endpoint,
        "index_name": search_index,
        "semantic_configuration": semantic_configuration,
        "query_type": query_type,
        "fields_mapping": {},
        "in_scope": in_scope,
        "filter": None,
        "strictness": strictness,
        "top_n_documents": top_n_documents,
        "authentication": {
            "type": "api_key",
            "key": search_key,
        },
    }
    if role_information:
        params["role_information"] = role_information

    return {
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": params,
            }
        ]
    }

# --- UI setup --------------------------------------------------------------
st.set_page_config(page_title="AI Chat Pro", page_icon="💬", layout="wide")

# Load CSS if available
css_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_name" not in st.session_state:
    st.session_state.conversation_name = "AI Chat Session"

# --- Chat logic ------------------------------------------------------------
def get_chat_response(messages_history: List[Dict[str, str]], max_tokens=1000, temperature=0.7) -> str:
    """Get response from Azure OpenAI; returns a message or a friendly warning."""
    try:
        if client is None:
            return (
                "⚠️ Chat is disabled: model not configured. "
                "Set ENDPOINT_URL, DEPLOYMENT_NAME, and AZURE_OPENAI_API_KEY in your .env, then restart."
            )

        openai_messages: List[Dict[str, str]] = []
        for msg in messages_history:
            role = msg.get("role") or "user"
            content = msg.get("content") or ""
            openai_messages.append({"role": role, "content": content})

        # If the first message is a system prompt, pass as role_information to OYD
        system_role_info: str | None = None
        if openai_messages and openai_messages[0].get("role") == "system":
            first_content = openai_messages[0].get("content")
            if isinstance(first_content, str) and first_content.strip():
                system_role_info = first_content

        extra_body = build_azure_search_extra_body(role_information=system_role_info)

        completion = client.chat.completions.create(
            model=deployment,
            messages=openai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            **({"extra_body": extra_body} if extra_body else {}),
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        return f"❌ Error: {e}"

# --- Layout ---------------------------------------------------------------
st.title("💬 AI Chat Pro")

_deployment_display = deployment or "(not configured)"
if endpoint:
    try:
        _endpoint_name = endpoint.split(".")[0]
    except Exception:
        _endpoint_name = endpoint
else:
    _endpoint_name = "(not configured)"

st.markdown(f"**Model:** {_deployment_display} | **Endpoint:** {_endpoint_name}...")
if search_endpoint and search_index and search_key:
    st.caption(f"🔎 Retrieval: ON · Index: {search_index}")
elif any([search_endpoint, search_index, search_key]):
    st.caption("ℹ️ Retrieval: PARTIAL (incomplete configuration detected)")
else:
    st.caption("ℹ️ Retrieval: OFF")

# Sidebar
with st.sidebar:
    st.header("🎛️ Controls")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.subheader("⚙️ Settings")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
    max_tokens = st.slider("Max Tokens", 100, 2000, 1000, 100)

    st.subheader("📊 Info")
    st.metric("Messages", len(st.session_state.messages))
    if st.session_state.messages:
        st.metric("Last Message", datetime.now().strftime("%H:%M:%S"))

# Main chat area
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        role = (message.get("role") or "assistant")
        content = (message.get("content") or "").strip()
        with st.chat_message(role):
            if content:
                st.write(content)
            else:
                st.write("(empty message)")

# Chat input
prompt = st.chat_input("Type your message here...")
if prompt is not None:
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message
    with chat_container:
        with st.chat_message("user"):
            st.write(prompt if prompt.strip() else "(empty message)")

    # Prepare conversation context (system message + history)
    conversation = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI assistant. Provide clear, accurate, and friendly responses. "
                "If a data source is available, ground your answers in the provided documents."
            ),
        }
    ] + st.session_state.messages

    # Get AI response
    with chat_container:
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                response = get_chat_response(
                    conversation, max_tokens=max_tokens, temperature=temperature
                )
            st.write(response)

    # Add assistant response to history only if it looks like a valid answer
    if isinstance(response, str) and not response.startswith("❌") and not response.startswith("⚠️"):
        st.session_state.messages.append({"role": "assistant", "content": response})

    # Auto-rerun to update the chat
    st.rerun()

# Footer
st.markdown("---")
st.markdown("*Powered by Azure OpenAI* 🚀")