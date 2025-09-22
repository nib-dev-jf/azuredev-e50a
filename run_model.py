
import os
import sys
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_required_env_var(var_name, description):
    """Get required environment variable or exit with error message."""
    value = os.getenv(var_name)
    if not value:
        print(f"Error: {var_name} environment variable is required.")
        print(f"Please set {var_name} in your .env file: {description}")
        sys.exit(1)
    return value

# Get required environment variables
endpoint = get_required_env_var("ENDPOINT_URL", "Your Azure OpenAI endpoint URL")
deployment = get_required_env_var("DEPLOYMENT_NAME", "Your deployment model name")
subscription_key = get_required_env_var("AZURE_OPENAI_API_KEY", "Your Azure OpenAI API key")

print(f"Connecting to Azure OpenAI at: {endpoint}")
print(f"Using deployment: {deployment}")

# Initialize Azure OpenAI client with key-based authentication
try:
    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=subscription_key,
        api_version="2025-01-01-preview",
    )
    print("✅ Successfully connected to Azure OpenAI")
except Exception as e:
    print(f"❌ Failed to initialize Azure OpenAI client: {e}")
    sys.exit(1)

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
# Try a few common names for the key
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

def get_chat_response(messages, max_tokens=1000, temperature=0.7):
    """Get response from Azure OpenAI chat completion."""
    try:
        # If Azure AI Search is configured, attach it via extra_body
        system_role_info = None
        if messages and isinstance(messages[0].get("content"), str) and messages[0].get("role") == "system":
            system_role_info = messages[0]["content"]
        extra_body = build_azure_search_extra_body(role_information=system_role_info)

        completion = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            stream=False,
            **({"extra_body": extra_body} if extra_body else {})
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error getting response: {e}"

def run_chatbot():
    """Run the interactive chatbot."""
    print("\n" + "="*60)
    print("🤖 Azure OpenAI Chatbot - Ready to chat!")
    print("Type 'quit', 'exit', or 'bye' to end the conversation")
    print("="*60)
    
    # Initialize conversation with system message
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI assistant. Provide clear, accurate, and friendly responses. "
                "If a data source is available, ground your answers in the provided documents."
            ),
        }
    ]

    if search_endpoint and search_index:
        print(
            f"🔎 Using Azure AI Search index '{search_index}' at '{search_endpoint}'. "
            "Responses will be grounded in retrieved documents."
        )
    else:
        print("ℹ️ Azure AI Search not configured. Proceeding without retrieval.")
    
    while True:
        # Get user input
        try:
            user_input = input("\n👤 You: ").strip()
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Chat ended by user.")
            break
        
        # Check for exit commands
        if user_input.lower() in ['quit', 'exit', 'bye', 'q']:
            print("\n👋 Goodbye! Thanks for chatting!")
            break
        
        # Skip empty input
        if not user_input:
            continue
        
        # Add user message to conversation
        messages.append({"role": "user", "content": user_input})
        
        # Show typing indicator
        print("\n🤖 Assistant: ", end="", flush=True)
        
        # Get AI response
        response = get_chat_response(messages)
        print(response)
        
        # Add assistant response to conversation
        if not response.startswith("❌"):
            messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    run_chatbot()
