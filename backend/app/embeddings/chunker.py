def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Splits a single body of text into smaller, overlapping chunks.
    
    This exists to break documents into segments compatible with LLM context sizes.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer greater than 0.")
    if overlap < 0:
        raise ValueError("overlap must be a non-negative integer (0 or greater).")
    if overlap >= chunk_size:
        raise ValueError("overlap must be strictly less than chunk_size.")

    clean_text = text.strip() if text else ""
    if not clean_text:
        return []

    chunks = []
    start = 0
    text_len = len(clean_text)

    while start < text_len:
        end = start + chunk_size
        chunk = clean_text[start:end]
        chunks.append(chunk)
        
        if end >= text_len:
            break
            
        start += (chunk_size - overlap)

    return chunks
