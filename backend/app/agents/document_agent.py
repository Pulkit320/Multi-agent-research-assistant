import logging
from app.embeddings.embedder import get_embedding
from app.retrieval.vector_store import VectorStore

logger = logging.getLogger(__name__)

class DocumentAgent:
    """
    DocumentAgent performs semantic searches on document text chunks stored
    in the database.
    
    This agent isolates database lookup queries so that document RAG context
    can be retrieved independently and executed in parallel with web research.
    """

    def __init__(self):
        """
        Initializes the agent and the database vector store wrapper.
        """
        self.store = VectorStore()

    async def run(self, sub_question: str) -> dict:
        """
        Runs semantic search retrieval for a given sub-question.
        
        Args:
            sub_question: The query string to search for in documents.
            
        Returns:
            A dictionary containing:
            - 'chunks': List of matching text snippets with metadata (pdf_id, page_number).
            - 'sources': List of unique document filenames (pdf_id) matching the snippets.
        """
        logger.info(f"DocumentAgent querying: '{sub_question}'")
        try:
            # 1. Generate the query embedding vector (768 dimensions, retrieval_query task type)
            query_embedding = await get_embedding(sub_question, task_type="retrieval_query")
            if not query_embedding:
                return {"chunks": [], "sources": []}

            # 2. Search the vector database for top 3 matching chunks
            raw_results = self.store.search(query_embedding, top_k=3)
            
            # 3. Format results into structured dict chunks
            formatted_chunks = []
            unique_sources = set()
            for row in raw_results:
                filename = row.get("pdf_id", "unknown_document")
                page_num = row.get("page_number", 1)
                content = row.get("content", "")
                
                formatted_chunks.append({
                    "content": content,
                    "filename": filename,
                    "page": page_num,
                    "similarity": row.get("similarity", 0.0)
                })
                unique_sources.add(filename)

            return {
                "chunks": formatted_chunks,
                "sources": list(unique_sources)
            }
        except Exception as e:
            logger.error(f"DocumentAgent failed for query '{sub_question}': {e}")
            # Return empty structure rather than crashing the parallel execution loop
            return {"chunks": [], "sources": []}
