# 🛍️ ShoppingMindAI

ShoppingMindAI is an AI-powered conversational shopping assistant designed to simplify product discovery and comparison across multiple e-commerce platforms. The system understands natural language queries, extracts product information using Google's Gemini AI, searches products from Amazon and Flipkart, and presents relevant comparison results to the user.

The backend is built using FastAPI with a modular architecture and PostgreSQL for persistent conversation storage.

---

# ✨ Features

- AI-powered conversational shopping assistant
- Natural language product search
- Intelligent product information extraction using Gemini AI
- Amazon product scraping
- Flipkart product scraping
- Product comparison across multiple platforms
- Session-based conversation management
- PostgreSQL integration
- Modular FastAPI architecture
- RESTful API design

---

# 🏗️ Backend Architecture

```
backend/
│
├── app/
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── search.py
│   │   └── session.py
│   │
│   ├── core/
│   │   └── __init__.py
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── crud.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── requests.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chatbot.py
│   │   ├── parser.py
│   │   ├── scraper.py
│   │   └── normalizer.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   └── helpers.py
│   │
│   ├── __init__.py
│   └── main.py
│
├── scripts/
│   ├── check.py
│   ├── debug_amazon.py
│   ├── debug_flipkart.py
│   ├── find_title.py
│   ├── migrate_json_to_postgres.py
│   ├── mock_parser.py
│   ├── run_pipeline.py
│   └── run_scrapers.py
│
├── tests/
│   ├── test.py
│   ├── test_db.py
│   └── test_crud.py
│
├── .env
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
└── prompt.txt

# ⚙️ Technology Stack

### Backend

- FastAPI
- Python
- SQLAlchemy
- PostgreSQL
- Pydantic

### Artificial Intelligence

- Google Gemini API

### Frontend

- Next.js
- React
- TypeScript

### Web Scraping

- Playwright
- BeautifulSoup

---

# 🔄 System Workflow

```
User
   │
   ▼
Next.js Frontend
   │
   ▼
FastAPI Backend
   │
   ▼
Search API
   │
   ▼
Load Conversation History
(PostgreSQL)
   │
   ▼
Gemini AI
(Intent Analysis)
   │
   ▼
Amazon & Flipkart Scrapers
   │
   ▼
Product Normalization
   │
   ▼
Product Comparison
   │
   ▼
Store Conversation
(PostgreSQL)
   │
   ▼
Response to User
---

# 🗄️ Database

The application currently maintains the following tables:

- **Sessions** – Stores user chat sessions.
- **Messages** – Stores conversation history for each session.

---

# 🚀 Running the Backend

### 1. Create a virtual environment

```bash
python -m venv venv
```

### 2. Activate the virtual environment

Windows

```bash
venv\Scripts\activate
```

Linux / macOS

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file and configure:

```env
GEMINI_API_KEY=

DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=
```

### 5. Start the backend server

```bash
python -m uvicorn app.main:app --reload
```

Backend will be available at:

```
http://127.0.0.1:8000
```

Swagger Documentation:

```
http://127.0.0.1:8000/docs
```

---

# 📌 Future Enhancements

- Redis-based Context Cache
- Price History Tracking
- Product Recommendation Engine
- Personalized Shopping Recommendations
- User Authentication
- Wishlist Management
- Multi-platform Product Support

---



