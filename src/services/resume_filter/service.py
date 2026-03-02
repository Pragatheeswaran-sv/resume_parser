import os
import time
import re
import json
import logging
import ollama
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from db.connection import SessionLocal
from resume_filter.models import Resume
from sqlalchemy import select, and_, cast, String, func, exists, text
from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger(__name__)

VECTORDB_PATH = "faiss_index"

def normalize_experience(exp_value) -> int:
    """Ensure experience is always integer for DB"""
    if exp_value is None:
        return 0

    # already numeric
    if isinstance(exp_value, (int, float)):
        return int(exp_value)

    text = str(exp_value).lower()

    match = re.search(r"\d+(\.\d+)?", text)
    if match:
        return int(float(match.group()))

    return 0

def save_resumes_to_db(resumes):
    db = SessionLocal()

    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    for r in resumes:
        raw_text = r["text"] 
        logger.info(f'NAv----> the raw_text {raw_text}')
        info = r["info"]            
        vector = embedding_model.embed_query(raw_text)

        row = Resume(
            file_name=info.get("file_name"),
            name=info.get("name"),
            total_experience=normalize_experience(info.get("total_experience")),
            skills=info.get("skills"),
            companies=info.get("companies"),
            education=info.get("education"),
            embedding=vector
        )
        db.add(row)

    db.commit()
    db.close()

def save_to_faiss(resumes, save_path=VECTORDB_PATH):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    docs = []
    metadatas = []

    for r in resumes:
        # Use JSON string as text to embed
        text_to_embed = json.dumps(r, ensure_ascii=False)
        chunks = splitter.split_text(text_to_embed)
        docs.extend(chunks)
        metadatas.extend([{"file_name": r.get("file_name", "")}] * len(chunks))

    embedding = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = FAISS.from_texts(docs, embedding=embedding, metadatas=metadatas)
    vectordb.save_local(save_path)
    print("[INFO] FAISS index saved")
    return vectordb

def extract_text_from_pdf(path):
    text = ""
    try:
        reader = PdfReader(path)
        for page in reader.pages:
            text += page.extract_text() or ""
    except Exception as e:
        print(f"[ERROR] PDF read failed: {path} -> {e}")
    return text

def extract_text_from_docx(path):
    text = ""
    try:
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        print(f"[ERROR] DOCX read failed: {path} -> {e}")
    return text

def extract_basic_info(resume_text):

    logger.info("This section executed -----> ")
    prompt = """
You are a resume parser.

Extract ONLY basic candidate information from the resume.

Return ONLY valid JSON.
Do NOT add explanation.
Do NOT add text before or after JSON.

JSON format:
{
    name:"",
    total_experience:"",
    skills:[]
    companies:[]
    education:[]
}


Rules:
- If data missing → empty string or empty list
- Experience must be number (years)
- Skills must be list of strings
"""

    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": "You output only JSON."},
                {"role": "user", "content": prompt + "\n\nResume:\n" + resume_text[:4000]}
            ]
        )
        logger.info(f'NAV----> before content')
        content = response["message"]["content"].strip()
        logger.info(f"NAv----> content {content}")

        # clean JSON
        start = content.find("{")
        end = content.rfind("}") + 1
        logger.info(f"NAV---> start {start}")
        logger.info(f"NAV---> end {end}")
        json_str = content[start:end]

        return json.loads(json_str)

    except Exception as e:
        print(f"[ERROR] LLM parse failed: {e}")
        return None

def process_resumes(folder_path):
    start = time.time()
    base_dir = os.getcwd() 
    folder_path =os.path.join(base_dir, "Resumes")
    results = []

    for file in os.listdir(folder_path):
        path = os.path.join(folder_path, file)
        if file.lower().endswith(".pdf"):
            text = extract_text_from_pdf(path)
        elif file.lower().endswith(".docx"):
            text = extract_text_from_docx(path)
        else:
            continue

        if not text.strip():
            print(f"[WARN] Empty: {file}")
            continue

        print(f"[LLM] Extracting: {file}")
        info = extract_basic_info(text)
        if info:
            info["file_name"] = file
            # results.append(info)cls
            results.append({
                "info": info,
                "text": text
            })

    
    if results:
        logger.info(f"NACV----> This result section executed {results}")
        save_to_faiss(results)
        save_resumes_to_db(results)

    print(f"\n[TIME] {round(time.time()-start,2)} sec")
    return os.listdir()

def search_resumes(filters: dict):
    """Search resumes based on dynamic filters."""

    query = select(Resume)
    conditions = []

    name = filters.get("name")
    if name:
        conditions.append(Resume.name.ilike(f"%{name}%"))

    file_name = filters.get("file_name")
    if file_name:
        conditions.append(Resume.file_name.ilike(f"%{file_name}%"))

    exp_min = filters.get("experience_min")
    if exp_min is not None:
        conditions.append(Resume.total_experience >= exp_min)

    exp_max = filters.get("experience_max")
    if exp_max is not None:
        conditions.append(Resume.total_experience <= exp_max)

    skills = filters.get("skills")
    if skills:
        for skill in skills:
            logger.info("NAV----> skills any %s", skill)
            conditions.append(Resume.skills.any(skill))

    companies = filters.get("companies")
    if companies:
        for comp in companies:
            conditions.append(Resume.companies.any(comp))

    education = filters.get("education")
    if education:
        for edu in education:
            conditions.append(
                cast(Resume.education, String).ilike(f"%{edu}%")
            )

    if conditions:
        query = query.where(and_(*conditions))

    with SessionLocal() as db:
        results = db.execute(query).scalars().all()

    return results

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


def get_query_embedding(query: str):
    return embedding_model.embed_query(query)


def semantic_search_resumes(query: str, top_k: int = 5):
    db = SessionLocal()
    try:
        query_embedding = get_query_embedding(query)

        sql = text("""
            SELECT id, file_name, name, total_experience, skills, companies, education
            FROM resumes
            ORDER BY embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
        """)

        results = db.execute(
            sql,
            {
                "query_embedding": query_embedding,
                "top_k": top_k
            }
        ).fetchall()

        return results

    finally:
        db.close()
