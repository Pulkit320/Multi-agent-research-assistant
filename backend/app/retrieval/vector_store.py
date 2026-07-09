import logging
import psycopg2
from psycopg2.extras import execute_values
from app.core.config import settings

# Set up logging
logger = logging.getLogger(__name__)

class VectorStore:
    """
    A vector store wrapper for PostgreSQL with pgvector.
    
    Ported directly from the prior RAG project to preserve schema layout and SQL logic.
    """
    
    def __init__(self, database_url: str = None):
        """
        Initializes the VectorStore connection wrapper and sets up the schema.
        """
        self.db_url = database_url or settings.database_url
        if not self.db_url:
            raise ValueError(
                "database_url not found. Please provide it or define it in your .env file."
            )
        
        # Initialize schema (tables and extensions)
        self._initialize_schema()
        
    def _get_connection(self):
        """
        Creates and returns a new database connection.
        """
        try:
            return psycopg2.connect(self.db_url)
        except Exception as e:
            logger.error(f"Failed to connect to the database: {e}")
            raise ConnectionError(f"Could not connect to PostgreSQL database: {e}")

    def _initialize_schema(self):
        """
        Ensures the pgvector extension and the chunks table exist.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                logger.info("Ensuring pgvector extension is enabled...")
                try:
                    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"Could not enable pgvector extension: {e}")
                
                logger.info("Ensuring 'chunks' table exists...")
                create_table_query = """
                CREATE TABLE IF NOT EXISTS chunks (
                    id SERIAL PRIMARY KEY,
                    pdf_id VARCHAR(255) NOT NULL,
                    page_number INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(768)
                );
                """
                cur.execute(create_table_query)
                
                try:
                    cur.execute("""
                    CREATE INDEX IF NOT EXISTS chunks_embedding_cosine_idx 
                    ON chunks USING hnsw (embedding vector_cosine_ops);
                    """)
                except Exception as e:
                    conn.rollback()
                    logger.debug(f"HNSW Index creation deferred: {e}")
                    
            conn.commit()
            logger.info("Database schema checked and initialized.")

    def store_chunks(self, chunks: list[str], embeddings: list[list[float]], metadata: list[dict] | dict) -> None:
        """
        Inserts document chunks, their embeddings, and metadata into the database in bulk.
        """
        if not chunks or not embeddings:
            logger.warning("Empty chunks or embeddings list provided. Skipping insertion.")
            return

        if len(chunks) != len(embeddings):
            raise ValueError(f"Mismatch: Got {len(chunks)} chunks and {len(embeddings)} embeddings.")

        # Normalize metadata format
        normalized_metadata = []
        if isinstance(metadata, dict):
            pdf_id = metadata.get("pdf_id", "unknown_pdf")
            page_numbers = metadata.get("page_numbers", [])
            for i in range(len(chunks)):
                page_num = page_numbers[i] if i < len(page_numbers) else 1
                normalized_metadata.append({"pdf_id": pdf_id, "page_number": page_num})
        elif isinstance(metadata, list):
            if len(metadata) != len(chunks):
                raise ValueError(f"Mismatch: Got {len(chunks)} chunks and {len(metadata)} metadata elements.")
            normalized_metadata = metadata
        else:
            raise TypeError("Metadata must be a dictionary or a list of dictionaries.")

        insert_data = []
        for chunk, embedding, meta in zip(chunks, embeddings, normalized_metadata):
            pdf_id = meta.get("pdf_id", "unknown")
            page_num = meta.get("page_number", 1)
            emb_str = "[" + ",".join(map(str, embedding)) + "]"
            insert_data.append((pdf_id, page_num, chunk, emb_str))

        insert_query = """
        INSERT INTO chunks (pdf_id, page_number, content, embedding)
        VALUES %s;
        """
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                logger.info(f"Inserting {len(insert_data)} chunks into the database...")
                execute_values(cur, insert_query, insert_data)
            conn.commit()
            logger.info("Successfully stored all chunks.")

    def search(self, query_embedding: list[float], top_k: int = 3) -> list[dict]:
        """
        Searches the database for the top_k most semantically similar chunks based on cosine distance.
        """
        if not query_embedding:
            return []

        query_emb_str = "[" + ",".join(map(str, query_embedding)) + "]"
        
        search_query = """
        SELECT id, pdf_id, page_number, content, 1 - (embedding <=> %s::vector) AS similarity
        FROM chunks
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        
        results = []
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(search_query, (query_emb_str, query_emb_str, top_k))
                rows = cur.fetchall()
                for row in rows:
                    results.append({
                        "id": row[0],
                        "pdf_id": row[1],
                        "page_number": row[2],
                        "content": row[3],
                        "similarity": float(row[4])
                    })
                    
        logger.info(f"Retrieved {len(results)} chunks using semantic search.")
        return results
