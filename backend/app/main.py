import os
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(root_path="/api")


class Selection(BaseModel):
    selectedText: str

@app.post("/process-selection")
async def process_selection(selection: Selection):
    return {"processed": selection.selectedText}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)