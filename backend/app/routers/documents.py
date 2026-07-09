import os
import shutil
import tempfile
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.ingestion.pdf_reader import extract_text
from app.embeddings.chunker import chunk_text
from app.embeddings.embedder import get_embedding
from app.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Initialize router for document ingestion
router = APIRouter()

@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint to upload and ingest documents (PDFs or text files) into the vector store.
    
    This splits documents into semantic chunks and indexes their vector representations,
    acting as Phase 3 & 4 of the RAG ingestion pipeline.
    """
    # 1. Validate file extension
    filename = file.filename
    _, ext = os.path.splitext(filename.lower())
    if ext not in [".pdf", ".txt"]:
        raise HTTPException(status_code=400, detail="Only PDF (.pdf) and plain text (.txt) files are supported.")

    # 2. Save uploaded file to a temporary location
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Temporarily saved uploaded file to {temp_path}")
        
        # 3. Process ingestion pipeline based on file type
        vector_store = VectorStore()
        all_chunks = []
        all_embeddings = []
        all_metadata = []

        if ext == ".pdf":
            # Extract text page-by-page to preserve citations
            pages = extract_text(temp_path)
            for page in pages:
                page_num = page["page_number"]
                text = page["text"]
                if not text:
                    continue
                
                # Chunk this page's text
                chunks = chunk_text(text, chunk_size=500, overlap=50)
                for chunk in chunks:
                    # Generate embedding vector
                    embedding = await get_embedding(chunk, task_type="retrieval_document")
                    if embedding:
                        all_chunks.append(chunk)
                        all_embeddings.append(embedding)
                        all_metadata.append({
                            "pdf_id": filename,
                            "page_number": page_num
                        })
        else:
            # Text file ingestion
            with open(temp_path, "r", encoding="utf-8", errors="ignore") as txt_file:
                text_content = txt_file.read()
                
            chunks = chunk_text(text_content, chunk_size=500, overlap=50)
            for chunk in chunks:
                embedding = await get_embedding(chunk, task_type="retrieval_document")
                if embedding:
                    all_chunks.append(chunk)
                    all_embeddings.append(embedding)
                    all_metadata.append({
                        "pdf_id": filename,
                        "page_number": 1
                    })

        # 4. Insert chunks into the vector store database
        if all_chunks:
            # We call store_chunks synchronously (it utilizes blocking psycopg2)
            vector_store.store_chunks(all_chunks, all_embeddings, all_metadata)
            logger.info(f"Ingested {len(all_chunks)} chunks for document '{filename}' successfully.")
        else:
            raise HTTPException(status_code=400, detail="No readable text found in the uploaded file.")

        # 5. Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {
            "status": "success",
            "message": f"Successfully ingested '{filename}' into the vector store.",
            "chunks_count": len(all_chunks)
        }

    except Exception as e:
        logger.error(f"Ingestion pipeline failed for {filename}: {e}")
        # Clean up temp file in case of crash
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Ingestion pipeline failed: {str(e)}")
