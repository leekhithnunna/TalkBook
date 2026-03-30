# 🤖 TalkBook — Talk. Book. Done.

> An AI-powered booking assistant built with Streamlit, LangChain, and Groq LLM.  
> Chat naturally, book appointments, upload PDFs, and manage everything in one place.

---

## 🚀 Live Demo

```bash
streamlit run app.py
```
Open → `http://localhost:8501`

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Streamlit (Python) |
| **LLM** | Groq API — `llama-3.1-8b-instant` |
| **Embeddings** | HuggingFace `all-MiniLM-L6-v2` |
| **Vector Store** | ChromaDB (persistent, local) |
| **Database** | SQLite (via Python `sqlite3`) |
| **Email** | SMTP (Gmail App Password) |
| **RAG Framework** | LangChain (community, text-splitters, chroma) |
| **PDF Parsing** | PyPDF |

---

## 📁 Project Structure

```
AI_UseCase/
├── app.py                  ← Main Streamlit app (all pages + UI)
├── chat_logic.py           ← Chat orchestration, booking flow, RAG
├── booking_flow.py         ← Multi-turn slot filling logic
├── rag_pipeline.py         ← PDF ingestion, chunking, vector search
├── email_service.py        ← SMTP email confirmation
├── tools.py                ← LangChain tool definitions
├── config/
│   └── config.py           ← All configuration & env vars
├── db/
│   └── database.py         ← SQLite: users, bookings, chat sessions, SMTP
├── models/
│   ├── llm.py              ← Groq LLM wrapper (runtime key support)
│   └── embeddings.py       ← HuggingFace embeddings singleton
├── requirements.txt
└── .streamlit/
    └── config.toml         ← Streamlit server config (no email prompt)
```

---

## ⚙️ Setup & Installation

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables (optional — default key is pre-loaded)
```bash
# Windows
set GROQ_API_KEY=your_groq_key_here

# Linux/Mac
export GROQ_API_KEY=your_groq_key_here
```

### 3. Run the app
```bash
python -m streamlit run app.py
```

---

## 🔐 Authentication

The app has a full sign-in / sign-up system with two roles:

| Role | Access |
|---|---|
| **User** | Chat, PDF Chat, My Bookings, Settings |
| **Admin** | Everything above + Admin Dashboard |

### Pre-seeded demo accounts

| Email | Password | Role |
|---|---|---|
| `admin@gmail.com` | `Admin@123` | 👑 Admin |
| `leekhithnunna369@gmail.com` | `User@123` | 👤 User |
| `dr_rishi@gmail.com` | `User@123` | 👤 User |
| `sarah.j@gmail.com` | `User@123` | 👤 User |
| `mike.chen@gmail.com` | `User@123` | 👤 User |

**Guest users** get 5 free messages before being asked to sign in.

---

## 💬 Features

### 1. General Chat (AI Assistant + Booking)
- Powered by Groq LLM (`llama-3.1-8b-instant`)
- Detects booking intent automatically
- Multi-turn slot filling: collects Name, Email, Phone, Type, Date, Time
- Pre-fills name/email from logged-in user
- Summarizes and confirms before saving
- Sends confirmation email to the signed-in user's email
- Chat history saved per session (ChatGPT-style sidebar)
- Last 20 messages kept in context

### 2. PDF Chat (RAG-based)
- Upload any PDF document
- Text is extracted, chunked (500 chars, 50 overlap), and embedded
- Answers come **only** from the uploaded document
- Completely separate from General Chat
- Full conversation history per PDF session
- Previous sessions accessible from sidebar

### 3. Booking System
- Booking IDs in format `TB-1001`, `TB-1002`, etc.
- Stored in SQLite with full details
- Users can view, edit (type/date/time/status) their bookings
- Confirmation email sent automatically after booking

### 4. Admin Dashboard
- View all bookings across all users
- Filter by type and status
- Search by name or email
- Bar chart analytics by booking type
- Metrics: total, confirmed, types

### 5. Email Confirmation
- Sent to the **signed-in user's registered email**
- Configured via Settings → Email (SMTP)
- Uses Gmail App Password (or any SMTP provider)
- Graceful failure handling with clear error messages

---

## 🗄️ Database Schema

### `users`
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| name | TEXT | Full name |
| email | TEXT | Unique email |
| password | TEXT | SHA-256 hashed |
| role | TEXT | `user` or `admin` |
| created_at | TIMESTAMP | Registration time |

### `bookings`
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| booking_ref | TEXT | e.g. `TB-1001` |
| user_id | INTEGER | FK → users |
| name, email, phone | TEXT | Contact details |
| booking_type | TEXT | Doctor/Hotel/Salon/Other |
| booking_date | TEXT | e.g. `2024-04-15` |
| booking_time | TEXT | e.g. `10:00 AM` |
| status | TEXT | confirmed/cancelled/completed |
| created_at | TIMESTAMP | Booking time |

### `chat_sessions`
| Column | Type | Description |
|---|---|---|
| id | INTEGER | Primary key |
| user_id | INTEGER | FK → users |
| title | TEXT | Auto-generated from first message |
| chat_type | TEXT | `general` or `pdf` |
| messages | TEXT | JSON array of messages |
| updated_at | TIMESTAMP | Last activity |

### `app_settings`
| Column | Type | Description |
|---|---|---|
| key | TEXT | Setting name (e.g. `smtp_user`) |
| value | TEXT | Setting value |

---

## 📧 Email Setup (Gmail)

1. Enable **2-Factor Authentication** on your Google account
2. Go to `myaccount.google.com` → **Security** → **App Passwords**
3. Select **Mail** → **Windows Computer** → **Generate**
4. Copy the 16-character password
5. In TalkBook → **⚙️ Settings** → **Email (SMTP) Settings**:
   - Host: `smtp.gmail.com`
   - Port: `587`
   - Email: `your-gmail@gmail.com`
   - App Password: *(paste the 16-char password)*
6. Click **Save Email Settings**

After this, every confirmed booking sends an email to the user's registered address.

---

## 🔄 How It Works — Full Flow

```
User types "I want to book a doctor"
        ↓
Intent detected → Booking flow starts
        ↓
Bot asks: Phone? → Type? → Date? → Time?
(Name & Email pre-filled from login)
        ↓
Summary shown → User confirms "yes"
        ↓
Booking saved to SQLite (TB-1001)
        ↓
Email sent to user's registered email
        ↓
Booking visible in "My Bookings"
Admin sees it in "Admin Dashboard"
```

---

## 🎨 UI Design

- **Theme**: Red accent color (`#cc0000`) on Streamlit's native dark/light mode
- **Logo**: Gradient TalkBook wordmark in sidebar
- **Chat bubbles**: Rounded with red border accent
- **Sidebar**: ChatGPT-style chat history list with delete option
- **Responsive**: Works on desktop and tablet

---

## 🧠 RAG Architecture

```
PDF Upload
    ↓
PyPDFLoader → extract text
    ↓
RecursiveCharacterTextSplitter (500 chars, 50 overlap)
    ↓
HuggingFace Embeddings (all-MiniLM-L6-v2, 384-dim)
    ↓
ChromaDB (persistent vector store)
    ↓
User query → similarity_search(k=4)
    ↓
Top chunks → LLM context → Answer
```

Two separate vector stores:
- `./chroma_db` — General knowledge base (uploaded via Settings)
- `./pdf_chroma_db` — PDF Chat (per-upload, separate)

---

## 🛠️ Error Handling

| Scenario | Behavior |
|---|---|
| No API key | Warning shown, chat disabled |
| Invalid email in booking | Regex validation, re-asks |
| Email send fails | Booking still saved, clear error shown |
| PDF empty/unreadable | Error message, no crash |
| DB error | Exception caught, user-friendly message |
| Wrong password | "Invalid email or password" (no info leak) |

---

## 📦 Requirements

```
streamlit>=1.35.0
langchain>=0.2.0
langchain-core>=0.2.0
langchain-community>=0.2.0
langchain-text-splitters>=0.2.0
langchain-groq>=0.1.6
langchain-huggingface>=0.0.3
langchain-chroma>=0.1.2
chromadb>=0.5.0
sentence-transformers>=3.0.0
pypdf>=4.0.0
pandas>=2.0.0
```

---

## 👤 User Perspective

**As a new visitor:**
1. Land on the Sign In page
2. Use a demo account or create your own
3. Start chatting immediately (API key pre-loaded)

**As a user booking an appointment:**
1. Type "I want to book a doctor appointment"
2. Answer 4 quick questions (phone, type, date, time)
3. Confirm the summary
4. Receive booking ID + email confirmation

**As a user with a PDF:**
1. Go to PDF Chat
2. Upload any PDF (manual, report, policy doc)
3. Ask questions — answers come only from that document
4. Previous conversations saved in sidebar

**As an admin:**
1. Sign in with `admin@gmail.com`
2. See all bookings in the dashboard
3. Filter, search, and monitor activity

---

*Built for NeoStats AI Engineer Assignment — Production-level AI Booking Assistant*
