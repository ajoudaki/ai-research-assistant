from fastapi import FastAPI, Request
import bibtexparser


app = FastAPI(root_path="/api")

@app.post("/process-selection")
async def process_selection(request: Request):
    data = await request.json()
    text = data['selection']['text']
    start = data['selection']['start']
    end = (data['selection']['end'])
    selected_text = text[start:end]
    
    # Process the selected text and context here
    # For now, we'll just return them as part of the response
    
    return {
        "processed_text": selected_text,
        "processed_start_end": [start, end],
        "message": "Selection processed successfully"
    }

@app.post("/parse-bibtex")
async def parse_bibtex(request: Request):
    data = await request.json()
    bibtex_str = data['bibtex']
    
    try:
        bib_database = bibtexparser.loads(bibtex_str)
        parsed_entries = {}
        for entry in bib_database.entries:
            key = entry.get('ID', 'unknown')
            parsed_entries[key] = entry
        return parsed_entries
    except Exception as e:
        return {"error": f"Failed to parse BibTeX: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)