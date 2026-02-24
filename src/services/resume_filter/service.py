import os
import time
import json
import logging
import ollama
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

logger = logging.getLogger(__name__)

VECTORDB_PATH = "faiss_index"

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
            results.append(info)
    
    if results:
        logger.info("This result section executed--->")
        save_to_faiss(results)

    print(f"\n[TIME] {round(time.time()-start,2)} sec")
    return os.listdir()