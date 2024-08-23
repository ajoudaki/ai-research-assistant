from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import bibtexparser

app = FastAPI()

class BibEntry(BaseModel):
    key: str
    title: str
    authors: str
    year: str
    journal: str = ""

@app.post("/parse_bibtex")
async def parse_bibtex(bibtex_content: str):
    bib_database = bibtexparser.loads(bibtex_content)
    entries = {}
    for entry in bib_database.entries:
        key = entry.get('ID', '')
        entries[key] = BibEntry(
            key=key,
            title=entry.get('title', ''),
            authors=entry.get('author', ''),
            year=entry.get('year', ''),
            journal=entry.get('journal', '')
        )
    return entries

@app.get("/citation/{cite_key}")
async def get_citation(cite_key: str):
    # In a real application, you would fetch this from a database
    # For this example, we'll use a dummy database
    dummy_db = {
        "ref1": BibEntry(key="ref1", title="Example Paper", authors="John Doe", year="2023", journal="Journal of Examples"),
        # Add more entries as needed
    }
    if cite_key not in dummy_db:
        raise HTTPException(status_code=404, detail="Citation not found")
    return dummy_db[cite_key]