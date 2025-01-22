import streamlit as st
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import hashlib

# Updated modern CSS
st.markdown("""
<style>
    /* Essential styles only */
    * {
        box-sizing: border-box;
    }
    
    .stTextArea textarea {
        background: #1a1a1a !important;
        color: white !important;
        border: 1px solid #333 !important;
        border-radius: 8px;
        padding: 16px;
        font-size: 16px;
        transition: border-color 0.2s;
    }
    
    .stTextArea textarea:focus {
        border-color: #4a4a4a !important;
        box-shadow: 0 0 0 2px rgba(255,255,255,0.1);
    }
    
    .note-card {
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 20px;
        margin: 16px 0;
        transition: transform 0.2s;
    }
    
    .note-card:hover {
        transform: translateY(-2px);
    }
    
    .note-date {
        color: #888;
        font-size: 12px;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    /* Button improvements */
    .stButton button {
        border-radius: 6px !important;
        padding: 4px 16px !important;
        height: 36px !important;
        transition: all 0.2s;
    }
    
    /* Container layout */
    .main-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
    }
    
    /* Input group styling */
    .input-group {
        display: flex;
        gap: 16px;
        align-items: flex-start;
        margin-bottom: 32px;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Initialize session state for authentication first
if 'user' not in st.session_state:
    st.session_state.user = None
if 'notes' not in st.session_state:
    st.session_state.notes = []
if 'editing' not in st.session_state:
    st.session_state.editing = set()

# Database connection configuration
DB_CONFIG = {
    "user": os.getenv("user"),
    "password": os.getenv("password"),
    "host": os.getenv("host"),
    "port": os.getenv("port"),
    "dbname": os.getenv("dbname")
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Database operations
# Add user management functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, email, password):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                (username, email, hash_password(password))
            )
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id

def verify_user(username, password):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE username = %s AND password_hash = %s",
                (username, hash_password(password))
            )
            return cur.fetchone()

# Modify note functions to include user_id
def load_notes(user_id):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM notes WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
            return cur.fetchall()

def save_note(content, user_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO notes (content, user_id) VALUES (%s, %s) RETURNING id",
                (content, user_id)
            )
            note_id = cur.fetchone()[0]
        conn.commit()
        return note_id

def update_note(note_id, content):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE notes SET content = %s WHERE id = %s",
                (content, note_id)
            )
        conn.commit()

def delete_note(note_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM notes WHERE id = %s", (note_id,))
        conn.commit()

# Modify the delete account function to be simpler and more reliable
def delete_user_account(user_id):
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Delete all notes first
                cur.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
                # Then delete the user
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            raise e

# Authentication UI
if not st.session_state.user:
    st.title("Welcome to Notes App")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("Username*", placeholder="Enter username")
            password = st.text_input("Password*", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if not username or not password:
                    st.error("⚠️ All fields are required!")
                else:
                    user = verify_user(username, password)
                    if user:
                        st.session_state.user = user
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
    
    with tab2:
        with st.form("signup_form", clear_on_submit=True):
            new_username = st.text_input("Username*", placeholder="Choose a username")
            new_email = st.text_input("Email*", placeholder="Enter your email")
            new_password = st.text_input("Password*", type="password", placeholder="Choose a password")
            submitted = st.form_submit_button("Sign Up", use_container_width=True)
            
            if submitted:
                if not new_username or not new_email or not new_password:
                    st.error("⚠️ All fields are required!")
                elif len(new_password) < 6:
                    st.error("⚠️ Password must be at least 6 characters long")
                elif '@' not in new_email:
                    st.error("⚠️ Please enter a valid email address")
                else:
                    try:
                        user_id = create_user(new_username, new_email, new_password)
                        st.success("✅ Account created! Please log in.")
                    except Exception as e:
                        if "duplicate key" in str(e):
                            if "username" in str(e):
                                st.error("Username already exists!")
                            elif "email" in str(e):
                                st.error("Email already registered!")
                        else:
                            st.error(f"Failed to create account: {e}")

else:
    # After successful login, load notes
    try:
        if st.session_state.notes == []:  # Only load if notes are empty
            st.session_state.notes = load_notes(st.session_state.user['id'])
    except Exception as e:
        st.error(f"Failed to load notes: {e}")
        st.session_state.notes = []

    # Show logout and delete account buttons
    with st.sidebar:
        st.write("Account Options")
        if st.button("Logout"):
            st.session_state.user = None
            st.rerun()
        
        st.write("---")
        st.write("⚠️ Danger Zone")
        delete_col1, delete_col2 = st.columns(2)
        with delete_col1:
            if st.button("Delete Account", type="secondary"):
                st.session_state['show_delete_confirm'] = True
        
        if st.session_state.get('show_delete_confirm', False):
            st.warning("Are you sure? This will delete all your notes!")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, Delete"):
                    try:
                        if delete_user_account(st.session_state.user['id']):
                            st.session_state.user = None
                            st.session_state.notes = []
                            st.success("Account deleted")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete account: {e}")
            with col2:
                if st.button("Cancel"):
                    st.session_state['show_delete_confirm'] = False
                    st.rerun()

    # Only show notes app when user is logged in
    st.header(f"📝 Notes - Welcome {st.session_state.user['username']}")
    
    # Improved note input layout with better save button placement
    st.markdown("### Create Note")
    new_note = st.text_area("", height=100, placeholder="Write something...", label_visibility="collapsed")
    if st.button("💾 Save", type="primary", use_container_width=True):
        if new_note.strip():
            try:
                note_id = save_note(new_note, st.session_state.user['id'])
                st.session_state.notes = load_notes(st.session_state.user['id'])
                st.success("✓ Saved")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save note: {e}")
        else:
            st.warning("📝 Note is empty")

    # Improved notes display
    try:
        notes = load_notes(st.session_state.user['id'])
        if notes:
            st.markdown("### Your Notes")
            for idx, note in enumerate(notes):
                with st.container():
                    cols = st.columns([5,1,1])
                    with cols[0]:
                        st.markdown(f"""
                            <div class="note-card">
                                <div class="note-date">📅 {note['created_at'].strftime('%Y-%m-%d %H:%M')}</div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        is_editing = idx in st.session_state.editing
                        edited_note = st.text_area("", note['content'], height=100,
                                                 key=f"note_{idx}",
                                                 disabled=not is_editing,
                                                 label_visibility="collapsed")
                        
                        if is_editing and edited_note != note['content']:
                            try:
                                update_note(note['id'], edited_note)
                                st.session_state.notes = load_notes(st.session_state.user['id'])
                            except Exception as e:
                                st.error(f"Failed to update note: {e}")
                    
                    with cols[1]:
                        st.markdown("#")  # Spacing for alignment
                        if is_editing:
                            if st.button("✓", key=f"edit_{idx}", use_container_width=True):
                                st.session_state.editing.remove(idx)
                                st.rerun()
                        else:
                            if st.button("✏️", key=f"edit_{idx}", use_container_width=True):
                                st.session_state.editing.add(idx)
                                st.rerun()
                    
                    with cols[2]:
                        st.markdown("#")  # Spacing for alignment
                        if st.button("🗑️", key=f"del_{idx}", use_container_width=True):
                            try:
                                delete_note(note['id'])
                                st.session_state.notes = load_notes(st.session_state.user['id'])
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to delete note: {e}")

            st.divider()
            col1, col2, col3 = st.columns([2,1,2])
            with col2:
                if st.button("🧹 Clear all", type="secondary", use_container_width=True):
                    try:
                        for note in st.session_state.notes:
                            delete_note(note['id'])
                        st.session_state.notes = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to clear notes: {e}")
        else:
            st.caption("📌 No notes yet")
    except Exception as e:
        st.error(f"Failed to load notes: {e}")
        st.session_state.notes = []

