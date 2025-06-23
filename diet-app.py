"""
Diet Agent Chat Application
==============================

This Streamlit application provides a chat interface for interacting with the ADK Diet Agent.
It allows users to create sessions, send messages, and receive text responses.

Requirements:
------------
- ADK API Server running on localhost:8000
- Diet Agent registered and available in the ADK
- Streamlit and related packages installed

Usage:
------
1. Start the ADK API Server: `adk api_server`
2. Ensure the Diet Agent is registered and working
3. Run this Streamlit app: `streamlit run apps/diet_app.py`
4. Click "Create Session" in the sidebar
5. Start chatting with the Diet Agent

Architecture:
------------
- Session Management: Creates and manages ADK sessions for stateful conversations
- Message Handling: Sends user messages to the ADK API and processes responses

API Assumptions:
--------------
1. ADK API Server runs on localhost:8000
2. Diet Agent is registered with app_name="diet"
3. Responses follow the ADK event structure with model outputs and function calls/responses

"""
import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import os
import uuid
import time
import sys

# Disable automatic browser opening to prevent xdg-settings errors
if not sys.warnoptions:
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'

st.set_page_config(
    page_title="My Diet Assistant",
    page_icon=":robot:",
    layout="wide"
)

API_BASE_URL = "http://localhost:8000"
APP_NAME = "my-diet-assistant"

def login_screen():
    st.header("This app is private.")
    st.subheader("Please log in.")
    st.button("Log in with Google", on_click=st.login)


def create_session():
    """
    Create a new session with the diet agent.
    
    This function:
    1. Generates a unique session ID based on timestamp
    2. Sends a POST request to the ADK API to create a session
    3. Updates the session state variables if successful
    
    Returns:
        bool: True if session was created successfully, False otherwise
    
    API Endpoint:
        POST /apps/{app_name}/users/{user_id}/sessions/{session_id}
    """
    session_id = f"session-{int(time.time())}"
    response = requests.post(
        f"{API_BASE_URL}/apps/{APP_NAME}/users/{st.session_state.user_id}/sessions/{session_id}",
        headers={"Content-Type": "application/json"},
        data=json.dumps({})
    )
    
    if response.status_code == 200:
        st.session_state.session_id = session_id
        st.session_state.messages = []
        return True
    else:
        st.error(f"Failed to create session: {response.text}")
        return False

if not st.user.is_logged_in:
    login_screen()
    st.stop()  # Stop further execution until logged in
else:
    #st.user
    st.header(f"Welcome, {st.user.name}!")
    st.button("Log out", on_click=st.logout)

# Initialize session state variables
if "user_id" not in st.session_state:
    st.session_state.user_id = f"{st.user.email}-{uuid.uuid4()}"
    
if "session_id" not in st.session_state:
    #st.session_state.session_id = None
    #print("******initial session")
    if create_session():
        st.rerun()
    
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "clipboard" not in st.session_state:
    st.session_state.clipboard = ""

def send_message(message):
    """
    Send a message to the diet agent and process the response.
    
    This function:
    1. Adds the user message to the chat history
    2. Sends the message to the ADK API
    3. Processes the response to extract text
    4. Updates the chat history with the assistant's response
    
    Args:
        message (str): The user's message to send to the agent
        
    Returns:
        bool: True if message was sent and processed successfully, False otherwise
    
    API Endpoint:
        POST /run
        
    Response Processing:
        - Parses the ADK event structure to extract text responses
        - Adds text information to the chat history
    """
    if not st.session_state.session_id:
        st.error("No active session. Please create a session first.")
        return False
    
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": message})
    
    # Create a placeholder for the assistant's message
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("Thinking...")
    
    try:
        # Send message to API
        response = requests.post(
            f"{API_BASE_URL}/run",
            headers={"Content-Type": "application/json"},
            data=json.dumps({
                "app_name": APP_NAME,
                "user_id": st.session_state.user_id,
                "session_id": st.session_state.session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": message}]
                }
            }),
            timeout=300*2  # Add timeout to prevent hanging
        )
        
        # Check for HTTP errors
        response.raise_for_status()
        
        # Process the response
        events = response.json()
        
        # Extract assistant's text response
        assistant_message = None
        
        for event in events:
            # Look for the final text response from the model
            if event.get("content", {}).get("role") == "model" and "text" in event.get("content", {}).get("parts", [{}])[0]:
                assistant_message = event["content"]["parts"][0]["text"]
        
        # Add assistant response to chat
        if assistant_message:
            st.session_state.messages.append({"role": "assistant", "content": assistant_message})
            # Check if message appears to be markdown by looking for common markdown indicators
            if any(marker in assistant_message for marker in ['#', '```', '*', '_', '>', '-', '[']):
                message_placeholder.markdown(assistant_message)
            else:
                message_placeholder.write(assistant_message)
            return True
        else:
            error_msg = "No response received from the model."
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error_msg}"})
            message_placeholder.markdown(f"⚠️ {error_msg}")
            return False
            
    except requests.exceptions.HTTPError as e:
        # Handle HTTP errors (like 503)
        error_msg = f"API Error: {e.response.status_code} - {e.response.reason}"
        if e.response.status_code == 503:
            error_msg = "The model is currently overloaded. Please try again in a few moments."
        
        st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error_msg}"})
        message_placeholder.markdown(f"⚠️ {error_msg}")
        st.error(error_msg)
        return False
        
    except requests.exceptions.Timeout:
        error_msg = "Request timed out. The server might be busy."
        st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error_msg}"})
        message_placeholder.markdown(f"⚠️ {error_msg}")
        st.error(error_msg)
        return False
        
    except requests.exceptions.ConnectionError:
        error_msg = "Connection error. Please check if the API server is running."
        st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error_msg}"})
        message_placeholder.markdown(f"⚠️ {error_msg}")
        st.error(error_msg)
        return False
        
    except json.JSONDecodeError:
        error_msg = "Invalid response format from the server."
        st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error_msg}"})
        message_placeholder.markdown(f"⚠️ {error_msg}")
        st.error(error_msg)
        return False
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": f"⚠️ {error_msg}"})
        message_placeholder.markdown(f"⚠️ {error_msg}")
        st.error(error_msg)
        return False

# UI Components
st.title("🔊 Diet Agent Chat")

# Add custom CSS to make the chat area wider
st.markdown("""
<style>
.stChatMessage {
    max-width: 90%;
}
.stChatMessage .stMarkdown {
    width: 100%;
}
button[data-testid="baseButton-secondary"] {
    background-color: transparent;
    border: none;
    padding: 0.2rem;
    font-size: 1.2rem;
    cursor: pointer;
}
</style>
""", unsafe_allow_html=True)

# Sidebar for session management
#with st.sidebar:
#st.sidebar.collapsed = True
#st.header("Session Management")
with st.sidebar.expander("Session Management", expanded=False):
    st.header("Session Management")
    
    if st.session_state.session_id:
        st.success(f"Active session: {st.session_state.session_id}")
        if st.button("➕ New Session"):
            #print("******new session button")
            if create_session():
                st.rerun()
    else:
        st.warning("No active session")
        if st.button("➕ Create Session"):
            #print("******create session button")
            if create_session():
                st.rerun()
    
    st.divider()
    st.caption("You can start a new session.")
    
# Chat interface
st.subheader("Conversation")

# Display messages
for idx, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        with st.chat_message("assistant"):
            # Display the message content
            st.markdown(msg["content"])
            
            # Add a copy button below the message
            if msg["content"] and not msg["content"].startswith("⚠️"):
                # Use an expander to hide the copyable content until needed
                with st.expander("Copy this response", expanded=False):
                    st.code(msg["content"], language="")
                    st.caption("Click the copy button in the top-right corner of the code block above")
                    # Add a button to copy directly to clipboard using JavaScript
                    components_js = f"""
                    <script>
                    const copyToClipboard = async () => {{
                        try {{
                            await navigator.clipboard.writeText({repr(msg["content"])});
                            alert('Response copied to clipboard!');
                        }} catch (err) {{
                            alert('Failed to copy: ' + err);
                        }}
                    }};
                    </script>
                    <button onclick="copyToClipboard()">One-click copy</button>
                    """
                    st.components.v1.html(components_js, height=50)

# Input for new messages
if st.session_state.session_id:  # Only show input if session exists
    user_input = st.chat_input("Type your message...")
    if user_input:
        # Don't rerun if send_message returns False (error occurred)
        if send_message(user_input):
            st.rerun()  # Only rerun on successful message sending
else:
    st.info("👈 Create a session to start chatting")
