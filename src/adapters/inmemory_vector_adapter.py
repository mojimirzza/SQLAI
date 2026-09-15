import yaml
from ports.vector_store_port import VectorStorePort, Document

class InMemoryVectorAdapter(VectorStorePort):
    def __init__(self, docs_path):
        with open(docs_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self.doc_list = []
        if isinstance(data, dict):
            for name, content in data.items():
                self.doc_list.append(Document(str(content), {"name": name}, 0.0))
        elif isinstance(data, list):
            for doc in data:
                self.doc_list.append(Document(doc.get("content", ""), doc.get("metadata", {}), 0.0))

    def search(self, query, top_k=3):
        q = set(query.lower().split())
        scored = []
        for doc in self.doc_list:
            words = set(doc.content.lower().split())
            score = len(q & words) / max(len(q), 1)
            if score > 0:
                scored.append(Document(doc.content, doc.metadata, score))
        return sorted(scored, key=lambda x: x.score, reverse=True)[:top_k]
