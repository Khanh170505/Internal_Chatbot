import requests
import streamlit as st

API_BASE = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8000")

st.title("Hybrid AI Knowledge Copilot")
st.caption("Admin docs + user docs with scope-aware retrieval")

if "token" not in st.session_state:
    st.session_state.token = ""
if "last_job_id" not in st.session_state:
    st.session_state.last_job_id = ""

with st.sidebar:
    st.subheader("Login")
    email = st.text_input("Email", value="admin@example.com")
    name = st.text_input("Name", value="Admin User")
    role = st.selectbox("Role", ["admin", "user"])
    if st.button("Login"):
        resp = requests.post(f"{API_BASE}/api/auth/login", json={"email": email, "name": name, "role": role}, timeout=10)
        if resp.status_code == 200:
            payload = resp.json()
            st.session_state.token = payload["token"]
            st.success(f"Logged in as {payload['role']}")
        else:
            st.error(resp.text)

headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

if not st.session_state.token:
    st.info("Login before using upload/chat.")
    st.stop()

upload_tab, docs_tab, chat_tab = st.tabs(["Upload", "Documents", "Chat"])

with upload_tab:
    st.subheader("Upload Document")
    scope = st.selectbox("Scope", ["global", "user"])
    uploaded = st.file_uploader("Choose file", type=["pdf", "txt", "docx", "csv", "xlsx"])
    if st.button("Upload and Index") and uploaded is not None:
        files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type or "application/octet-stream")}
        resp = requests.post(f"{API_BASE}/api/documents/upload", params={"scope": scope}, files=files, headers=headers, timeout=60)
        if resp.status_code == 200:
            payload = resp.json()
            st.session_state.last_job_id = payload["job_id"]
            st.success(payload)
        else:
            st.error(resp.text)

    st.markdown("### Job Status")
    job_id = st.text_input("Job ID", value=st.session_state.last_job_id)
    if st.button("Check Job Status") and job_id:
        resp = requests.get(f"{API_BASE}/api/jobs/{job_id}", headers=headers, timeout=20)
        if resp.status_code == 200:
            st.json(resp.json())
        else:
            st.error(resp.text)

with docs_tab:
    st.subheader("Document Manager")
    resp = requests.get(f"{API_BASE}/api/documents", headers=headers, timeout=20)
    if resp.status_code == 200:
        data = resp.json()
        company_docs = [d for d in data if d["owner_type"] == "global"]
        my_docs = [d for d in data if d["owner_type"] == "user"]

        st.markdown("### Company Knowledge")
        st.dataframe(company_docs, use_container_width=True)

        st.markdown("### My Documents")
        st.dataframe(my_docs, use_container_width=True)
    else:
        st.error(resp.text)

with chat_tab:
    st.subheader("Ask Knowledge Base")
    scope_mode = st.selectbox("Search Scope", ["global", "user", "both"])
    question = st.text_area("Question", height=120)
    if st.button("Ask"):
        resp = requests.post(
            f"{API_BASE}/api/chat",
            json={"question": question, "scope_mode": scope_mode},
            headers=headers,
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            st.markdown("### Answer")
            st.write(data["answer"])
            st.markdown("### Citations")
            st.json(data["citations"])
        else:
            st.error(resp.text)

st.markdown("---")
st.caption("Tip: Login as admin to upload global docs, user role for personal docs.")
