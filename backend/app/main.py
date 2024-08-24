from fastapi import FastAPI, Request

app = FastAPI(root_path="/api")

@app.post("/process-selection")
async def process_selection(request: Request):
    data = await request.json()
    selected_text = data['selection']['text']
    context = data['selection']['context']
    
    # Process the selected text and context here
    # For now, we'll just return them as part of the response
    
    return {
        "processed_text": selected_text,
        "processed_context": context,
        "message": "Selection processed successfully"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)