import streamlit as st
from datetime import datetime, timedelta
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
import hashlib
import string
import random
import smtplib
from email.mime.text import MIMEText

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

def verify_user(email, password):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE email = %s AND password_hash = %s",
                (email, hash_password(password))
            )
            return cur.fetchone()

def verify_user_by_id(user_id, email):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM users WHERE id = %s AND email = %s",
                (user_id, email)
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

# Add helper function for space validation
def contains_spaces(text):
    return ' ' in text

# Add new function for password update
def update_password(user_id, new_password):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(new_password), user_id)
            )
        conn.commit()

# Add new functions for profile updates
def update_username(user_id, new_username):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET username = %s WHERE id = %s",
                (new_username, user_id)
            )
        conn.commit()

def update_email(user_id, new_email):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check if email exists
            cur.execute("SELECT id FROM users WHERE email = %s AND id != %s", (new_email, user_id))
            if cur.fetchone():
                raise Exception("Email already exists")
            cur.execute(
                "UPDATE users SET email = %s WHERE id = %s",
                (new_email, user_id)
            )
        conn.commit()

# Add cookie management functions
def set_auth_cookie():
    cookie = json.dumps({
        'user_id': st.session_state.user['id'],
        'email': st.session_state.user['email']
    })
    st.query_params['auth'] = cookie

def clear_auth_cookie():
    if 'auth' in st.query_params:
        del st.query_params['auth']

def load_auth_cookie():
    try:
        cookie = st.query_params.get('auth')
        if cookie:
            data = json.loads(cookie)
            # Verify if cookie data is valid
            user = verify_user_by_id(data['user_id'], data['email'])
            if user:
                st.session_state.user = user
                return True
    except:
        pass
    return False

# Add new functions for password reset
def generate_temp_password(length=12):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def send_password_reset_email(email, temp_password):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    message = MIMEText(f"""
    Hello,
    
    You requested to reset your password. Here is your temporary password:
    
    {temp_password}
    
    Please login with this password and change it immediately.
    
    Best regards,
    Notes App Team
    """)
    
    message['Subject'] = 'Password Reset Request'
    message['From'] = smtp_user
    message['To'] = email
    
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)

def reset_user_password(email):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Verify email exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if not cur.fetchone():
                raise Exception("Email not found")
            
            # Generate and set temporary password
            temp_password = generate_temp_password()
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (hash_password(temp_password), email)
            )
            conn.commit()
            return temp_password

# Authentication UI
if not st.session_state.user:
    # Try to load from cookie first
    if load_auth_cookie():
        st.rerun()
    
    st.title("Welcome to Notes App")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        with st.form("login_form", clear_on_submit=True):
            email = st.text_input("Email*", placeholder="Enter your email")
            password = st.text_input("Password*", type="password", placeholder="Enter password")
            remember_me = st.checkbox("Remember me")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if not email or not password:
                    st.error("⚠️ All fields are required!")
                elif contains_spaces(password):
                    st.error("⚠️ Password cannot contain spaces!")
                elif '@' not in email:
                    st.error("⚠️ Please enter a valid email address")
                else:
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        if remember_me:
                            set_auth_cookie()
                        st.success("Logged in successfully!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
        
        # Add forgot password section
        with st.expander("Forgot Password?"):
            with st.form("forgot_password_form"):
                reset_email = st.text_input("Email", placeholder="Enter your email")
                if st.form_submit_button("Reset Password"):
                    if not reset_email or '@' not in reset_email:
                        st.error("⚠️ Please enter a valid email address")
                    else:
                        try:
                            temp_password = reset_user_password(reset_email)
                            send_password_reset_email(reset_email, temp_password)
                            st.success("✅ Check your email for the temporary password!")
                        except Exception as e:
                            if "Email not found" in str(e):
                                st.error("⚠️ Email not found!")
                            else:
                                st.error(f"Failed to reset password: {e}")

    with tab2:
        with st.form("signup_form", clear_on_submit=True):
            new_username = st.text_input("Username*", placeholder="Choose a username (no spaces)")
            new_email = st.text_input("Email*", placeholder="Enter your email")
            new_password = st.text_input("Password*", type="password", placeholder="Choose a password (no spaces)")
            submitted = st.form_submit_button("Sign Up", use_container_width=True)
            
            if submitted:
                if not new_username or not new_email or not new_password:
                    st.error("⚠️ All fields are required!")
                elif contains_spaces(new_username) or contains_spaces(new_password):
                    st.error("⚠️ Username and password cannot contain spaces!")
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

    # Show account options in sidebar
    with st.sidebar:
        st.write("Account Options")
        if st.button("Logout"):
            clear_auth_cookie()
            st.session_state.user = None
            st.rerun()
        
        # Add Profile Update Section
        st.write("---")
        st.write("👤 Update Profile")
        
        # Username change form
        with st.form("change_username_form"):
            new_username = st.text_input("New Username", placeholder="Enter new username")
            if st.form_submit_button("Change Username"):
                if not new_username:
                    st.error("⚠️ Username cannot be empty!")
                elif contains_spaces(new_username):
                    st.error("⚠️ Username cannot contain spaces!")
                else:
                    try:
                        update_username(st.session_state.user['id'], new_username)
                        st.session_state.user['username'] = new_username
                        st.success("✅ Username updated successfully!")
                    except Exception as e:
                        st.error(f"Failed to update username: {e}")
        
        # Email change form
        with st.form("change_email_form"):
            new_email = st.text_input("New Email", placeholder="Enter new email")
            if st.form_submit_button("Change Email"):
                if not new_email:
                    st.error("⚠️ Email cannot be empty!")
                elif '@' not in new_email:
                    st.error("⚠️ Please enter a valid email address")
                else:
                    try:
                        update_email(st.session_state.user['id'], new_email)
                        st.session_state.user['email'] = new_email
                        st.success("✅ Email updated successfully!")
                    except Exception as e:
                        if "already exists" in str(e):
                            st.error("⚠️ This email is already registered!")
                        else:
                            st.error(f"Failed to update email: {e}")
        
        # Add Password Change Section
        st.write("---")
        st.write("🔐 Change Password")
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password", placeholder="Enter current password")
            confirm_current = st.text_input("Confirm Current Password", type="password", placeholder="Confirm current password")
            new_password = st.text_input("New Password", type="password", placeholder="Enter new password")
            
            if st.form_submit_button("Change Password"):
                if not current_password or not confirm_current or not new_password:
                    st.error("⚠️ All fields are required!")
                elif current_password != confirm_current:
                    st.error("⚠️ Current passwords don't match!")
                elif contains_spaces(new_password):
                    st.error("⚠️ New password cannot contain spaces!")
                elif len(new_password) < 6:
                    st.error("⚠️ New password must be at least 6 characters long")
                else:
                    # Verify current password
                    user = verify_user(st.session_state.user['email'], current_password)
                    if user:
                        try:
                            update_password(st.session_state.user['id'], new_password)
                            st.success("✅ Password updated successfully!")
                        except Exception as e:
                            st.error(f"Failed to update password: {e}")
                    else:
                        st.error("⚠️ Current password is incorrect!")
        
        # Danger Zone section
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

