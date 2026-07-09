# Phase 3: Parallel Agents & RAG Integration

## What We Built

We introduced parallel multi-agent processing and database document lookup capabilities:
1. **RAG Pipeline**: Ported text extraction ([pdf_reader.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/ingestion/pdf_reader.py)), text segmentation ([chunker.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/embeddings/chunker.py)), Gemini vector embedding ([embedder.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/embeddings/embedder.py)), and PostgreSQL database storage ([vector_store.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/retrieval/vector_store.py)) from the prior PDF Chatbot project.
2. **Ingestion REST Endpoint**: Implemented `POST /documents/upload` in [documents.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/routers/documents.py) to parse uploaded PDFs or text files and populate the pgvector index.
3. **Document Agent**: Created the `DocumentAgent` class in [document_agent.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/agents/document_agent.py) to perform semantic vector searches.
4. **Analyst Agent**: Created `AnalystAgent` in [analyst_agent.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/agents/analyst_agent.py) to deduplicate findings and outputs structured JSON evidence claims.
5. **Parallel State Graph**: Updated [graph.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/graph.py) so that for each sub-question, the web `research` node and RAG `document` node run concurrently using LangGraph's map-reduce structure before merging into a `combine` node.
6. **Frontend UI**: Built a file drag-and-drop ingestion interface, a parallel node monitor, and a color-coded evidence board in [App.jsx](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/frontend/src/App.jsx).

---

## Why Run Agents in Parallel Here?

### What Parallel Execution Saves
Running the Web `research` node and RAG `document` node in parallel (concurrently) rather than sequentially provides a significant speed advantage:
- **Reduced Latency (Wall-Clock Time)**: Making a web search (Tavily request + LLM parsing) takes roughly 3 to 6 seconds. Querying the database and embedding models (Gemini REST embedding request + PostgreSQL lookup) takes 1 to 2 seconds. 
  - *Sequential*: The overall execution takes $T_{\text{web}} + T_{\text{RAG}} \approx 4\text{s} + 1.5\text{s} = 5.5\text{s}$ per question.
  - *Parallel*: Both requests fire at the same time, meaning the overall execution takes $\max(T_{\text{web}}, T_{\text{RAG}}) \approx 4\text{s}$ per question.
  For a plan containing 4 sub-questions, this saves up to 6 seconds of wait time per user request!

### What Parallel Execution Doesn't Help With
- **Token Usage / API Costs**: Parallel execution does not optimize or reduce the number of requests sent or prompt tokens consumed. It changes *when* calls are made (simultaneously) but not *what* is sent.
- **Sequential Dependence**: If the document search results were required to formulate the web query (e.g. searching the web for a document serial number), parallel execution is impossible. In our map-reduce pattern, both branches are independent sub-tasks of the same question, which makes them ideal candidates for concurrent run.

---

## Reusing the RAG Pipeline

### What Was Ported Unchanged
- **Text Segmentation**: The sliding window logic in [chunker.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/embeddings/chunker.py) was copied exactly as it has no external dependencies.
- **Database Schema & SQL Queries**: The pgvector operations and table definitions in [vector_store.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/retrieval/vector_store.py) were preserved, ensuring the data layout is fully compatible with our database.

### What Had to Be Adapted
- **Optional OCR Dependencies**: In [pdf_reader.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/ingestion/pdf_reader.py), we wrapped the `pdf2image` and `pytesseract` OCR imports in `try-except` blocks. This ensures the backend runs cleanly even if binary OCR libraries are missing from the system.
- **REST Embedding Generation**: Instead of loading the heavy `google-generativeai` SDK, we rewrote the embedder logic in [embedder.py](file:///home/pulkit/projects/multi-agent%20reseach%20assistant/backend/app/embeddings/embedder.py) to execute lightweight `httpx.post` queries against Google's standard REST API.
- **Configuration Management**: Database configuration settings in `vector_store` were updated to read `database_url` from our centralized Pydantic settings.

---

## What Does the Analyst Actually Solve?

Directly concatenating findings from two independent agents and handing them straight to a final writer LLM creates distinct synthesis issues:

1. **Information Redundancy**: If a web article states "Canada's GDP grew by 3%" and an uploaded document says "Canada's 2023 GDP expansion reached 3%", a direct concatenation forces the writer LLM to wade through redundant statements. The output would likely repeat the same facts.
2. **Noise Overwhelm**: RAG lookups fetch raw document chunks that may contain formatting elements, boilerplates, or layout artifacts. Concatenating raw chunks directly floods the prompt context.
3. **Lack of Structure**: Concatenation provides no structural separation. The model lacks a structured overview of what was retrieved from where.

### The Analyst's Role
The `AnalystAgent` filters out noise by extracting atomic claims into a validated JSON schema. By grouping claims under a uniform structure (`claim`, `source_type`, `source`), the analyst deduplicates obvious overlaps and delivers a sanitized "Evidence Board" to the final writer. This guarantees the writer model remains focused and compiles a concise, well-cited response.

---

## In My Own Words
- this phase it about making a RAG agent and architecting the final research assistant graph. The RAG agent is a research agent that can search the web and our local database for information. 
- we run the web research node and RAG node in parallel to save time. 
- Then the analyst agent combines and deduplicates the information from the web research node and RAG node. 

---

## Questions I Still Have
- **Question**: Provide me with a simple workflow diagram explaining the analyst agent.
- **Answer**: 
  Here is the workflow showing how the `AnalystAgent` intercepts findings and outputs structured, deduplicated evidence:

  ```mermaid
  graph TD
      A[Web Research Agent Results] -->|1. Raw findings list| C(AnalystAgent Node)
      B[Document RAG Agent Chunks] -->|2. Raw PDF/TXT snippets| C
      
      C -->|3. Context Merging| D{LLM Turn}
      D -->|4. Clean overlap & contradictions| E[Deduplicate Claims]
      D -->|5. Label with web vs document| F[Apply Source Types]
      D -->|6. Map URLs or pdf_id page numbers| G[Format Citations]
      
      E & F & G --> H[Validate against EvidenceList schema]
      H -->|7. Write to state.evidence| I[Consolidated Evidence Board]
  ```
