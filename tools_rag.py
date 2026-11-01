import os

def search_docs(query: str, n_results: int = 5):
    """Search personal documents if available, otherwise return notice."""
    store_path = "./chroma_store"
    if not os.path.exists(store_path):
        return [{"snippet": "No personal documents indexed yet."}]
    try:
        import chromadb
        client = chromadb.PersistentClient(path=store_path)
        collection = client.get_or_create_collection("personal_docs")
        if collection.count() == 0:
            return [{"snippet": "No personal documents indexed yet."}]
        results = collection.query(query_texts=[query], n_results=n_results)
        return [
            {"text": doc, "source": meta.get("source", "")}
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]
    except Exception as e:
        return [{"snippet": f"Personal document search unavailable: {e}"}]
