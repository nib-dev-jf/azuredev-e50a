import os
import sys
from datetime import datetime
from typing import List, Dict, Any

import streamlit as st
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_required_env_var(var_name, description):
    """Get required environment variable or show error."""
    value = os.getenv(var_name)
    if not value:
        st.error(f"❌ Missing {var_name} environment variable!")
        st.info(f"Please set {var_name} in your .env file: {description}")
        st.stop()
    return value

# Get required environment variables
try:
    endpoint = get_required_env_var("ENDPOINT_URL", "Your Azure OpenAI endpoint URL")
    deployment = get_required_env_var("DEPLOYMENT_NAME", "Your deployment model name")
    subscription_key = get_required_env_var("AZURE_OPENAI_API_KEY", "Your Azure OpenAI API key")
    
    # Initialize Azure OpenAI client
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=subscription_key,
        api_version="2025-01-01-preview",
    )
    st.success(f"✅ Connected to Azure OpenAI: {deployment}")
except Exception as e:
    st.error(f"❌ Failed to initialize Azure OpenAI: {e}")
    st.stop()

# --- Optional: Azure AI Search (On Your Data) configuration ---
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

# Support both generic and repo-specific env var names
search_endpoint = _first_nonempty(
    os.getenv("SEARCH_ENDPOINT"),
    os.getenv("AZURE_AI_SEARCH_ENDPOINT")
)
search_index = _first_nonempty(
    os.getenv("SEARCH_INDEX_NAME"),
    os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
)
search_key = _first_nonempty(
    os.getenv("SEARCH_KEY"),
    os.getenv("AZURE_AI_SEARCH_ADMIN_KEY"),
    os.getenv("AZURE_AI_SEARCH_API_KEY")
)

semantic_configuration = os.getenv("AZURE_AI_SEARCH_SEMANTIC_CONFIGURATION", "default")
query_type = os.getenv("AZURE_AI_SEARCH_QUERY_TYPE", "simple")
in_scope = _get_bool("AZURE_AI_SEARCH_IN_SCOPE", True)
strictness = _get_int("AZURE_AI_SEARCH_STRICTNESS", 3)
top_n_documents = _get_int("AZURE_AI_SEARCH_TOPN", 5)

def build_azure_search_extra_body(role_information: str | None = None):
    """Build extra_body for Azure OpenAI 'On Your Data' with Azure AI Search.

    Returns None if search is not configured.
    """
    if not (search_endpoint and search_index and search_key):
        return None

    params = {
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

st.set_page_config(
    page_title="AI Chat Pro",
    page_icon="💬",
    layout="wide"
)

# Load CSS if it exists
css_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(css_path):
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_name" not in st.session_state:
    st.session_state.conversation_name = "AI Chat Session"

def get_chat_response(messages_history, max_tokens=1000, temperature=0.7):
    """Get response from Azure OpenAI."""
    try:
        # Convert Streamlit message format to OpenAI format
        openai_messages = []
        for msg in messages_history:
            openai_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        # If a system prompt is present, pass it as role_information to OYD
        system_role_info = None
        if openai_messages and openai_messages[0].get("role") == "system" and isinstance(openai_messages[0].get("content"), str):
            system_role_info = openai_messages[0]["content"]
        extra_body = build_azure_search_extra_body(role_information=system_role_info)

        completion = client.chat.completions.create(
            model=deployment,
            messages=openai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            **({"extra_body": extra_body} if extra_body else {})
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error: {e}"

# App Layout
st.title("💬 AI Chat Pro")
st.markdown(f"**Model:** {deployment} | **Endpoint:** {endpoint.split('.')[0]}...")
if search_endpoint and search_index:
    st.caption(f"🔎 Retrieval: ON · Index: {search_index}")
else:
    st.caption("ℹ️ Retrieval: OFF")

# Sidebar
with st.sidebar:
    st.header("🎛️ Controls")
    
    # Clear conversation
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    # Model settings
    st.subheader("⚙️ Settings")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
    max_tokens = st.slider("Max Tokens", 100, 2000, 1000, 100)
    
    # Conversation info
    st.subheader("📊 Info")
    st.metric("Messages", len(st.session_state.messages))
    if st.session_state.messages:
        st.metric("Last Message", datetime.now().strftime("%H:%M:%S"))

# Main chat area
chat_container = st.container()

# Display chat history
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

# Chat input
if prompt := st.chat_input("Type your message here..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with chat_container:
        with st.chat_message("user"):
            st.write(prompt)
    
    # Prepare conversation context (system message + history)
    conversation = [
        {"role": "system", "content": "You are a helpful AI assistant. Provide clear, accurate, and friendly responses. If a data source is available, ground your answers in the provided documents."}
    ] + st.session_state.messages
    
    # Get AI response
    with chat_container:
        with st.chat_message("assistant"):
            with st.spinner("🤔 Thinking..."):
                response = get_chat_response(
                    conversation, 
                    max_tokens=max_tokens, 
                    temperature=temperature
                )
            st.write(response)
    
    # Add assistant response to history
    if not response.startswith("❌"):
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Auto-rerun to update the chat
    st.rerun()

# Footer
st.markdown("---")
st.markdown("*Powered by Azure OpenAI* 🚀")