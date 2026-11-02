# Documents Directory

Place your personal knowledge base documents (`.txt` or `.md`) in this folder.

To index these documents into ChromaDB for local Retrieval-Augmented Generation (RAG):

```bash
python scripts/rag_index.py
```

The embeddings and index will be stored in `chroma_store/`. When running TashuBot, queries asking about personal documents will automatically use the `search_docs` tool to retrieve relevant snippets.
