from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path


class LocalKnowledgeService:
    """Small transparent TF-IDF retriever; replace this interface with SharePoint later."""
    def __init__(self, directory: str | Path="knowledge_base"):
        self.directory=Path(directory); self.directory.mkdir(parents=True,exist_ok=True)

    @staticmethod
    def tokens(text): return re.findall(r"[a-z][a-z0-9-]{2,}",text.lower())

    def documents(self):
        return [(p,p.read_text(encoding="utf-8",errors="ignore")) for p in self.directory.glob("**/*") if p.is_file() and p.suffix.lower() in {".txt",".md"}]

    def retrieve(self,query: str,limit=3):
        docs=self.documents(); q=Counter(self.tokens(query)); results=[]
        for path,text in docs:
            d=Counter(self.tokens(text)); common=set(q)&set(d)
            score=sum((1+math.log(q[t]))*(1+math.log(d[t])) for t in common)/(math.sqrt(sum(v*v for v in q.values()) or 1)*math.sqrt(sum(v*v for v in d.values()) or 1))
            if score: results.append({"source":path.name,"score":round(score,3),"excerpt":text[:500].strip()})
        return sorted(results,key=lambda x:x["score"],reverse=True)[:limit]

