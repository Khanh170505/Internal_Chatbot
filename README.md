# Internal Chatbot (Enterprise Knowledge Copilot)

## Problem

In many companies, internal knowledge is spread across PDFs and operational documents. Employees spend too much time searching for answers, and responses are often inconsistent.

## Solution

This project provides an internal AI chatbot using a hybrid RAG architecture:

- Admin uploads global company documents.
- Users can upload personal documents.
- Users ask questions in natural language.
- The system retrieves relevant context and returns answers with citations.

## Install Dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## Configure Environment

1. Create `.env` from `.env.example`.
2. Update Ollama settings if needed.

Example `.env`:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3.5:4b
OLLAMA_TIMEOUT_SEC=180
```

Where to configure in code:

- Env loading: `app/core/config.py`
- Ollama call: `app/llm/service.py`

## Run Ollama Model (Example)

Make sure Ollama is installed and running, then pull/run model:

```powershell
ollama pull qwen3.5:4b
ollama run qwen3.5:4b
```

Check model list:

```powershell
ollama list
```

## Run Project

1. Start backend API:

```powershell
.\.venv\Scripts\python main.py
```

API will run at `http://127.0.0.1:8000`.

2. Start Streamlit UI (new terminal):

```powershell
.\.venv\Scripts\python -m streamlit run app/ui/app.py --server.port 8501
```

UI will run at `http://localhost:8501`.

3. Use app:

- Open UI and set API Base URL to `http://127.0.0.1:8000`.
- Login with role `admin` to upload global docs.
- Login with role `user` to upload personal docs and chat.
