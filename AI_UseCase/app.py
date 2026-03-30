import streamlit as st
import sys, os, tempfile
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database import (
    init_db, login_user, register_user,
    get_user_bookings, update_booking, get_all_bookings, get_booking_stats,
    create_chat_session, save_chat_session, get_chat_sessions,
    load_chat_session, delete_chat_session,
    update_smtp_settings, get_smtp_settings,
)
from chat_logic import process_message, get_pdf_response
from rag_pipeline import ingest_pdf, ingest_pdf_for_chat, load_vectorstore, pdf_vs_ready
from models.llm import set_api_key
from config.config import GUEST_CHAT_LIMIT, APP_NAME, GROQ_API_KEY as DEFAULT_API_KEY
import pandas as pd

# ── Bootstrap ─────────────────────────────────────────────────────────────────
init_db()
load_vectorstore()

st.set_page_config(
    page_title=f"🤖 {APP_NAME} – Talk. Book. Done.",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Theme: Red accents only — background follows Streamlit dark/light mode ────
st.markdown("""
<style>
[data-testid="stSidebar"] { border-right: 2px solid #cc0000 !important; }

.tb-header {
    background: linear-gradient(135deg,rgba(180,0,0,.18),rgba(80,0,0,.28));
    border: 1px solid #cc0000; border-radius: 14px;
    padding: 22px 32px; margin-bottom: 24px; text-align: center;
}
.tb-header h1 { color: #ff3333 !important; font-size: 2.2rem; margin: 0; letter-spacing: -0.5px; }
.tb-header p  { margin: 6px 0 0; font-size: .95rem; opacity: .75; }

.stButton > button {
    background-color: #cc0000 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; transition: background .2s;
}
.stButton > button:hover { background-color: #ff2222 !important; }

.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border: 1px solid #cc0000 !important; border-radius: 8px !important;
}

[data-testid="stChatMessage"] {
    border-radius: 14px !important;
    border: 1px solid rgba(204,0,0,.2) !important;
    margin-bottom: 10px !important;
}

[data-testid="stMetric"] {
    border: 1px solid #cc0000 !important;
    border-radius: 10px !important; padding: 14px !important;
}
[data-testid="stMetricValue"] { color: #ff4444 !important; }

.stTabs [aria-selected="true"] {
    color: #ff3333 !important;
    border-bottom: 2px solid #cc0000 !important;
}

hr { border-color: rgba(204,0,0,.35) !important; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: #cc0000; border-radius: 3px; }

.logo-text {
    font-size: 1.6rem; font-weight: 800;
    background: linear-gradient(90deg, #ff3333, #ff8800);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "user":                  None,
    "messages":              [],
    "pdf_messages":          [],
    "booking_slots":         {},
    "booking_active":        False,
    "awaiting_confirmation": False,
    "guest_count":           0,
    "groq_api_key":          os.getenv("GROQ_API_KEY", DEFAULT_API_KEY),
    "pdf_uploaded":          False,
    "edit_booking_id":       None,
    "active_session_id":     None,
    "active_pdf_session_id": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Always sync API key on load
if st.session_state.groq_api_key:
    set_api_key(st.session_state.groq_api_key)

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_logged_in():  return st.session_state.user is not None
def is_admin():      return is_logged_in() and st.session_state.user.get("role") == "admin"

def logout():
    for k in DEFAULTS:
        st.session_state[k] = DEFAULTS[k]
    st.rerun()

def _session_title(messages):
    for m in messages:
        if m["role"] == "user":
            t = m["content"][:48]
            return t + ("…" if len(m["content"]) > 48 else "")
    return "💬 New Chat"

def _persist_general():
    if not is_logged_in() or not st.session_state.messages: return
    uid, sid = st.session_state.user["id"], st.session_state.active_session_id
    title = _session_title(st.session_state.messages)
    if sid is None:
        sid = create_chat_session(uid, title, "general")
        st.session_state.active_session_id = sid
    save_chat_session(sid, st.session_state.messages, title)

def _persist_pdf():
    if not is_logged_in() or not st.session_state.pdf_messages: return
    uid, sid = st.session_state.user["id"], st.session_state.active_pdf_session_id
    title = _session_title(st.session_state.pdf_messages)
    if sid is None:
        sid = create_chat_session(uid, title, "pdf")
        st.session_state.active_pdf_session_id = sid
    save_chat_session(sid, st.session_state.pdf_messages, title)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo
    st.markdown('<div class="logo-text">🤖 TalkBook</div>', unsafe_allow_html=True)
    st.caption("✨ Talk. Book. Done.")
    st.divider()

    # API Key — pre-filled with default, editable
    api_key_input = st.text_input(
        "🔑 Groq API Key",
        value=st.session_state.groq_api_key,
        type="password",
        placeholder="gsk_...",
        help="Default key loaded. Get your own free key at console.groq.com/keys"
    )
    if api_key_input != st.session_state.groq_api_key:
        st.session_state.groq_api_key = api_key_input
        set_api_key(api_key_input)
    if st.session_state.groq_api_key:
        st.success("✅ API key active")
    else:
        st.warning("⚠️ Enter a Groq API key to chat.")

    st.divider()

    if is_logged_in():
        user = st.session_state.user
        role_icon = "👑" if user["role"] == "admin" else "👤"
        st.markdown(f"**{role_icon} {user['name']}**")
        st.caption(f"📧 {user['email']}  •  🏷️ {user['role'].capitalize()}")
        st.divider()

        nav_options = ["💬 General Chat", "📄 PDF Chat", "📅 My Bookings"]
        if is_admin():
            nav_options.append("📊 Admin Dashboard")
        nav_options.append("⚙️ Settings")
        page = st.radio("🧭 Navigate", nav_options, label_visibility="collapsed")

        # ── Chat history (ChatGPT-style) ────────────────────────────────────
        st.divider()
        if page == "💬 General Chat":
            st.markdown("**🗂️ Your chats**")
            if st.button("＋ New Chat", use_container_width=True, key="new_gen"):
                _persist_general()
                st.session_state.update({
                    "messages": [], "booking_slots": {},
                    "booking_active": False, "awaiting_confirmation": False,
                    "active_session_id": None
                })
                st.rerun()
            for s in get_chat_sessions(user["id"], "general"):
                active = st.session_state.active_session_id == s["id"]
                c1, c2 = st.columns([5, 1])
                with c1:
                    lbl = ("▶ " if active else "💬 ") + s["title"]
                    if st.button(lbl, key=f"gs_{s['id']}", use_container_width=True):
                        _persist_general()
                        st.session_state.messages = load_chat_session(s["id"])
                        st.session_state.active_session_id = s["id"]
                        st.session_state.update({"booking_slots": {}, "booking_active": False, "awaiting_confirmation": False})
                        st.rerun()
                with c2:
                    if st.button("🗑", key=f"gd_{s['id']}"):
                        delete_chat_session(s["id"])
                        if st.session_state.active_session_id == s["id"]:
                            st.session_state.messages = []
                            st.session_state.active_session_id = None
                        st.rerun()

        elif page == "📄 PDF Chat":
            st.markdown("**🗂️ Your PDF chats**")
            if st.button("＋ New PDF Chat", use_container_width=True, key="new_pdf"):
                _persist_pdf()
                st.session_state.pdf_messages = []
                st.session_state.active_pdf_session_id = None
                st.rerun()
            for s in get_chat_sessions(user["id"], "pdf"):
                active = st.session_state.active_pdf_session_id == s["id"]
                c1, c2 = st.columns([5, 1])
                with c1:
                    lbl = ("▶ " if active else "📄 ") + s["title"]
                    if st.button(lbl, key=f"ps_{s['id']}", use_container_width=True):
                        _persist_pdf()
                        st.session_state.pdf_messages = load_chat_session(s["id"])
                        st.session_state.active_pdf_session_id = s["id"]
                        st.rerun()
                with c2:
                    if st.button("🗑", key=f"pd_{s['id']}"):
                        delete_chat_session(s["id"])
                        if st.session_state.active_pdf_session_id == s["id"]:
                            st.session_state.pdf_messages = []
                            st.session_state.active_pdf_session_id = None
                        st.rerun()

        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
    else:
        page = "🔐 Auth"
        st.info("🔒 Sign in for unlimited chat.")
        st.caption(f"👤 Guest: {st.session_state.guest_count}/{GUEST_CHAT_LIMIT} messages used")

# ══════════════════════════════════════════════════════════════════════════════
# Pages
# ══════════════════════════════════════════════════════════════════════════════

# ── 🔐 Auth ───────────────────────────────────────────────────────────────────
if page == "🔐 Auth" or not is_logged_in():
    st.markdown("""
    <div class="tb-header">
        <h1>🤖 TalkBook</h1>
        <p>✨ Talk. Book. Done. — Your AI-Powered Booking Assistant</p>
    </div>""", unsafe_allow_html=True)

    col_l, col_r = st.columns([1, 1])
    with col_l:
        st.markdown("### 🚀 What you can do")
        st.markdown("""
        - 💬 **Chat** with an AI assistant
        - 📅 **Book** Doctor, Hotel, Salon & more
        - 📄 **Upload PDFs** and ask questions
        - 📊 **Track** all your appointments
        - 📧 **Get email** confirmations instantly
        """)
    with col_r:
        tab_in, tab_up = st.tabs(["🔑 Sign In", "📝 Sign Up"])
        with tab_in:
            with st.form("signin_form"):
                s_email = st.text_input("📧 Email", placeholder="you@example.com")
                s_pwd   = st.text_input("🔒 Password", type="password")
                s_btn   = st.form_submit_button("🚀 Sign In", use_container_width=True)
            if s_btn:
                if not s_email or not s_pwd:
                    st.error("⚠️ Please fill in all fields.")
                else:
                    u = login_user(s_email.strip(), s_pwd)
                    if u:
                        st.session_state.user = u
                        st.session_state.guest_count = 0
                        st.success(f"🎉 Welcome back, {u['name']}!")
                        st.rerun()
                    else:
                        st.error("❌ Invalid email or password.")
            st.divider()
            st.caption("**🧪 Demo accounts:**")
            st.code("admin@gmail.com / Admin@123  👑 Admin\nleekhithnunna369@gmail.com / User@123\ndr_rishi@gmail.com / User@123")

        with tab_up:
            with st.form("signup_form"):
                r_name  = st.text_input("👤 Full Name")
                r_email = st.text_input("📧 Email", placeholder="you@example.com")
                r_pwd   = st.text_input("🔒 Password", type="password")
                r_role  = st.selectbox("🏷️ Role", ["user", "admin"])
                r_btn   = st.form_submit_button("✅ Create Account", use_container_width=True)
            if r_btn:
                if not all([r_name, r_email, r_pwd]):
                    st.error("⚠️ Please fill in all fields.")
                elif len(r_pwd) < 6:
                    st.error("⚠️ Password must be at least 6 characters.")
                else:
                    try:
                        u = register_user(r_name.strip(), r_email.strip(), r_pwd, r_role)
                        st.session_state.user = u
                        st.success(f"🎉 Account created! Welcome, {r_name}!")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

# ── 💬 General Chat ───────────────────────────────────────────────────────────
elif page == "💬 General Chat":
    st.markdown("""
    <div class="tb-header">
        <h1>🤖 TalkBook Assistant</h1>
        <p>💬 General AI Chat &amp; 📅 Smart Booking</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.groq_api_key:
        st.info("🔑 Enter your Groq API key in the sidebar to start chatting.")
        st.stop()

    if not is_logged_in() and st.session_state.guest_count >= GUEST_CHAT_LIMIT:
        st.warning(f"🔒 You've used all {GUEST_CHAT_LIMIT} guest messages. Please sign in to continue.")
        st.stop()

    # Render history
    for msg in st.session_state.messages:
        icon = "🧑" if msg["role"] == "user" else "🤖"
        with st.chat_message(msg["role"], avatar=icon):
            st.markdown(msg["content"])

    if not is_logged_in():
        remaining = GUEST_CHAT_LIMIT - st.session_state.guest_count
        st.caption(f"💬 {remaining} guest message(s) remaining. Sign in for unlimited chat.")

    if prompt := st.chat_input("💬 Ask me anything or say 'I want to book'..."):
        if not is_logged_in():
            if st.session_state.guest_count >= GUEST_CHAT_LIMIT:
                st.warning("🔒 Please sign in to continue chatting.")
                st.stop()
            st.session_state.guest_count += 1

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🤔 Thinking..."):
                try:
                    response = process_message(prompt, st.session_state)
                except ValueError as e:
                    response = f"⚠️ {e}"
                except Exception as e:
                    response = f"❌ Something went wrong: {str(e)}"
            st.markdown(response)

        st.session_state.messages.append({"role": "assistant", "content": response})
        _persist_general()

# ── 📄 PDF Chat ───────────────────────────────────────────────────────────────
elif page == "📄 PDF Chat":
    st.markdown("""
    <div class="tb-header">
        <h1>📄 PDF Chat</h1>
        <p>🔍 Upload any document and ask questions about it</p>
    </div>""", unsafe_allow_html=True)

    if not st.session_state.groq_api_key:
        st.info("🔑 Enter your Groq API key in the sidebar.")
        st.stop()

    col_upload, col_chat = st.columns([1, 2])

    with col_upload:
        st.markdown("### 📂 Upload PDF")
        uploaded = st.file_uploader("Choose a PDF file", type=["pdf"], label_visibility="collapsed")
        if uploaded:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            with st.spinner("⚙️ Processing PDF..."):
                try:
                    count = ingest_pdf_for_chat(tmp_path)
                    st.session_state.pdf_uploaded = True
                    st.session_state.pdf_messages = []
                    st.session_state.active_pdf_session_id = None
                    st.success(f"✅ Ready! {count} chunks indexed from **{uploaded.name}**")
                except Exception as e:
                    st.error(f"❌ Failed: {e}")
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

        if st.session_state.pdf_uploaded or pdf_vs_ready():
            st.session_state.pdf_uploaded = True
            st.info("📖 PDF loaded. Ask questions →")
            st.markdown("**💡 Tips:**")
            st.caption("• Ask specific questions\n• Request summaries\n• Find key facts")

    with col_chat:
        st.markdown("### 💬 Chat with your PDF")
        if not (st.session_state.pdf_uploaded or pdf_vs_ready()):
            st.markdown("""
            <div style="text-align:center; padding: 60px 20px; opacity: 0.6;">
                <div style="font-size: 4rem;">📄</div>
                <p>Upload a PDF on the left to start chatting</p>
            </div>""", unsafe_allow_html=True)
        else:
            for msg in st.session_state.pdf_messages:
                icon = "🧑" if msg["role"] == "user" else "📖"
                with st.chat_message(msg["role"], avatar=icon):
                    st.markdown(msg["content"])

            if pdf_prompt := st.chat_input("🔍 Ask about your PDF..."):
                st.session_state.pdf_messages.append({"role": "user", "content": pdf_prompt})
                with st.chat_message("user", avatar="🧑"):
                    st.markdown(pdf_prompt)
                with st.chat_message("assistant", avatar="📖"):
                    with st.spinner("🔍 Searching document..."):
                        try:
                            resp = get_pdf_response(pdf_prompt, st.session_state.pdf_messages)
                        except Exception as e:
                            resp = f"❌ Error: {e}"
                    st.markdown(resp)
                st.session_state.pdf_messages.append({"role": "assistant", "content": resp})
                _persist_pdf()

# ── 📅 My Bookings ────────────────────────────────────────────────────────────
elif page == "📅 My Bookings":
    st.markdown("""
    <div class="tb-header">
        <h1>📅 My Bookings</h1>
        <p>🗓️ View, manage and edit your appointments</p>
    </div>""", unsafe_allow_html=True)

    bookings = get_user_bookings(st.session_state.user["id"])
    if not bookings:
        st.markdown("""
        <div style="text-align:center; padding: 60px 20px; opacity: 0.6;">
            <div style="font-size: 4rem;">📭</div>
            <p>No bookings yet. Go to <b>💬 General Chat</b> and say <i>"I want to book"</i></p>
        </div>""", unsafe_allow_html=True)
    else:
        c1, c2, c3 = st.columns(3)
        total = len(bookings)
        confirmed = sum(1 for b in bookings if b["status"] == "confirmed")
        c1.metric("📋 Total", total)
        c2.metric("✅ Confirmed", confirmed)
        c3.metric("❌ Cancelled", total - confirmed)
        st.divider()

        for b in bookings:
            icon = {"confirmed": "✅", "cancelled": "❌", "completed": "🏁"}.get(b["status"], "📋")
            type_icon = {"Doctor": "🏥", "Hotel": "🏨", "Salon": "💇", "Other": "📌"}.get(b["booking_type"], "📌")
            with st.expander(f"{icon} {type_icon} **{b['booking_ref']}** — {b['booking_type']} on {b['booking_date']} at {b['booking_time']}"):

                # Clean card layout
                st.markdown(f"""
<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:8px 0;">
  <div>
    <p style="margin:4px 0">👤 <b>Name</b><br/><span style="font-size:1.05rem">{b['name']}</span></p>
    <p style="margin:4px 0">📧 <b>Email</b><br/><span style="font-size:1.05rem">{b['email']}</span></p>
    <p style="margin:4px 0">📞 <b>Phone</b><br/><span style="font-size:1.05rem">{b['phone']}</span></p>
  </div>
  <div>
    <p style="margin:4px 0">{type_icon} <b>Type</b><br/><span style="font-size:1.05rem">{b['booking_type']}</span></p>
    <p style="margin:4px 0">📅 <b>Date</b><br/><span style="font-size:1.05rem">{b['booking_date']}</span></p>
    <p style="margin:4px 0">⏰ <b>Time</b><br/><span style="font-size:1.05rem">{b['booking_time']}</span></p>
    <p style="margin:4px 0">🏷️ <b>Status</b><br/><span style="font-size:1.05rem;color:{'#22cc44' if b['status']=='confirmed' else '#cc4444' if b['status']=='cancelled' else '#aaaaaa'}">{b['status'].capitalize()}</span></p>
  </div>
</div>
""", unsafe_allow_html=True)

                if st.button("✏️ Edit Booking", key=f"edit_{b['booking_id']}"):
                    st.session_state.edit_booking_id = (
                        None if st.session_state.edit_booking_id == b["booking_id"]
                        else b["booking_id"]
                    )
                if st.session_state.edit_booking_id == b["booking_id"]:
                    st.divider()
                    st.markdown("**✏️ Edit Details**")
                    with st.form(f"ef_{b['booking_id']}"):
                        t_opts = ["Doctor", "Hotel", "Salon", "Other"]
                        new_type   = st.selectbox("🏷️ Type", t_opts,
                                        index=t_opts.index(b["booking_type"]) if b["booking_type"] in t_opts else 3)
                        new_date   = st.text_input("📅 Date (YYYY-MM-DD)", value=b["booking_date"])
                        new_time   = st.text_input("⏰ Time (e.g. 10:00 AM)", value=b["booking_time"])
                        s_opts     = ["confirmed", "cancelled", "completed"]
                        new_status = st.selectbox("🏷️ Status", s_opts,
                                        index=s_opts.index(b["status"]) if b["status"] in s_opts else 0)
                        if st.form_submit_button("💾 Save Changes", use_container_width=True):
                            if update_booking(b["booking_id"], new_type, new_date, new_time, new_status):
                                st.success("✅ Booking updated!")
                                st.session_state.edit_booking_id = None
                                st.rerun()
                            else:
                                st.error("❌ Update failed.")

# ── 📊 Admin Dashboard ────────────────────────────────────────────────────────
elif page == "📊 Admin Dashboard":
    if not is_admin():
        st.error("🚫 Access denied. Admin only.")
        st.stop()

    st.markdown("""
    <div class="tb-header">
        <h1>📊 Admin Dashboard</h1>
        <p>👑 Manage all bookings and monitor activity</p>
    </div>""", unsafe_allow_html=True)

    stats    = get_booking_stats()
    bookings = get_all_bookings()

    c1, c2, c3 = st.columns(3)
    c1.metric("📋 Total Bookings", stats["total"])
    c2.metric("✅ Confirmed",      stats["confirmed"])
    c3.metric("🏷️ Booking Types",  len(stats["by_type"]))

    if stats["by_type"]:
        st.divider()
        st.subheader("📈 Bookings by Type")
        st.bar_chart(pd.DataFrame(stats["by_type"]).set_index("booking_type")["c"])

    st.divider()
    st.subheader("📋 All Bookings")
    if not bookings:
        st.info("📭 No bookings yet.")
    else:
        df = pd.DataFrame(bookings)
        col1, col2, col3 = st.columns(3)
        with col1:
            search = st.text_input("🔍 Search name/email", "")
        with col2:
            t_filt = st.selectbox("🏷️ Type", ["All"] + sorted(df["booking_type"].unique().tolist()))
        with col3:
            s_filt = st.selectbox("📌 Status", ["All"] + sorted(df["status"].unique().tolist()))
        if search:
            df = df[df["name"].str.contains(search, case=False, na=False) |
                    df["email"].str.contains(search, case=False, na=False)]
        if t_filt != "All":
            df = df[df["booking_type"] == t_filt]
        if s_filt != "All":
            df = df[df["status"] == s_filt]
        st.caption(f"📊 Showing {len(df)} booking(s)")
        st.dataframe(df, use_container_width=True)

# ── ⚙️ Settings ───────────────────────────────────────────────────────────────
elif page == "⚙️ Settings":
    st.markdown("""
    <div class="tb-header">
        <h1>⚙️ Settings</h1>
        <p>🔧 Configure your TalkBook experience</p>
    </div>""", unsafe_allow_html=True)

    # API Key
    st.subheader("🔑 Groq API Key")
    st.caption("A default key is pre-loaded. Replace it if you have your own.")
    api_key = st.text_input("API Key", value=st.session_state.groq_api_key,
                             type="password", placeholder="gsk_...")
    if st.button("💾 Save API Key"):
        st.session_state.groq_api_key = api_key
        set_api_key(api_key)
        st.success("✅ API key saved!")

    st.divider()

    # Email / SMTP
    st.subheader("📧 Email (SMTP) Settings")
    st.caption("Confirmation emails are sent to the **signed-in user's email address** after each booking.")

    smtp_db = get_smtp_settings()
    with st.form("smtp_form"):
        col1, col2 = st.columns(2)
        with col1:
            smtp_host = st.text_input("🌐 SMTP Host", value=smtp_db.get("smtp_host", "smtp.gmail.com"))
        with col2:
            smtp_port = st.number_input("🔌 SMTP Port", value=int(smtp_db.get("smtp_port", 587)), step=1)
        smtp_user = st.text_input("📧 Sender Email", value=smtp_db.get("smtp_user", ""),
                                   placeholder="your-app@gmail.com")
        smtp_pass = st.text_input("🔒 App Password", value=smtp_db.get("smtp_password", ""),
                                   type="password",
                                   help="Gmail: myaccount.google.com → Security → App Passwords → Create")
        st.caption("💡 **Gmail setup:** Enable 2FA → App Passwords → Select 'Mail' → Copy 16-char password")
        if st.form_submit_button("💾 Save Email Settings", use_container_width=True):
            update_smtp_settings(smtp_host, int(smtp_port), smtp_user, smtp_pass)
            st.success("✅ Email settings saved! Confirmation emails will now be sent to users after booking.")

    st.divider()

    # Knowledge base
    st.subheader("📚 Knowledge Base")
    st.caption("Upload PDFs to enhance General Chat with domain knowledge (services, FAQs, policies).")
    kb_pdf = st.file_uploader("📂 Choose PDF", type=["pdf"])
    if kb_pdf:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(kb_pdf.read())
            tmp_path = tmp.name
        with st.spinner("⚙️ Indexing..."):
            try:
                count = ingest_pdf(tmp_path)
                st.success(f"✅ Knowledge base updated — {count} chunks from **{kb_pdf.name}**")
            except Exception as e:
                st.error(f"❌ Failed: {e}")
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

    st.divider()

    # Account
    st.subheader("👤 Account")
    u = st.session_state.user
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"👤 **Name:** {u['name']}")
        st.write(f"📧 **Email:** {u['email']}")
    with col2:
        st.write(f"🏷️ **Role:** {u['role'].capitalize()}")
    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        logout()
