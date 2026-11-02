import os
import pathlib
import chromadb
import ollama

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "documents"
CHROMA_STORE = PROJECT_ROOT / "chroma_store"

client = chromadb.PersistentClient(path=str(CHROMA_STORE))
collection = client.get_or_create_collection("personal_docs")


def chunk(text, size=800, overlap=100):
    """Split text into overlapping chunks for embedding."""
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size - overlap
    return chunks


def embed(text):
    """Generate an embedding vector using Ollama (local, free)."""
    return ollama.embeddings(model="nomic-embed-text", prompt=text)["embedding"]


def index_folder():
    """Walk DOCS_DIR, chunk every .txt/.md file, and add to ChromaDB."""
    doc_id = 0
    for path in pathlib.Path(DOCS_DIR).rglob("*"):
        if path.suffix.lower() not in (".txt", ".md"):
            continue  # extend with pdf/docx extraction as needed
        text = path.read_text(errors="ignore")
        for c in chunk(text):
            collection.add(
                ids=[f"doc-{doc_id}"],
                embeddings=[embed(c)],
                documents=[c],
                metadatas=[{"source": str(path)}],
            )
            doc_id += 1
    print(f"Indexed {doc_id} chunks.")


if __name__ == "__main__":
    index_folder()
