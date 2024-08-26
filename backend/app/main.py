import os
import re
import logging
from fastapi import FastAPI, HTTPException, Request
import bibtexparser
import anthropic
from pydantic import BaseModel
from typing import List, Optional
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(root_path="/api")


# Initialize Anthropic client
client = anthropic.Anthropic()

def log_env_variables():
    logger.info("Logging all environment variable keys:")
    for key in os.environ.keys():
        logger.info(f"Environment variable present: {key}")

log_env_variables()

def process_citation(text: str, start: int, end: int) -> str:
    logger.info(f"Processing citation: start={start}, end={end}")
    
    if text[start:end][:4] != 'cite' or start == 0:
        logger.info("No citation found or invalid start position. Returning original text.")
        return text

    start = max(0, start - 1)
    end = min(end + 3, len(text))
    slice = text[start:end]
    
    patterns = [
        (r'\\cite\{', r'\cite{<CITATION/>,'),
        (r'\\citet\{', r'\citet{<CITATION/>,'),
        (r'\\citep\{', r'\citep{<CITATION/>,'),
    ]
    
    for pattern, replacement in patterns:
        if match := re.search(pattern, slice):
            logger.info(f"Found matching pattern: {pattern}")
            slice = slice[:match.start()] + replacement + slice[match.end():]
            break
    
    return text[:start] + slice + text[end:]

def parse_bibtex(bibtex_str: str) -> Optional[dict]:
    logger.info("Parsing BibTeX entry")
    try:
        bib_database = bibtexparser.loads(bibtex_str)
        if bib_database.entries:
            return bib_database.entries[0]
        else:
            logger.warning("No entries found in BibTeX string")
            return None
    except Exception as e:
        logger.error(f"Error parsing BibTeX: {str(e)}")
        return None

def suggest_citations(latex_fragment: str) -> List[dict]:
    logger.info("Suggesting citations")

    if '<CITATION/>' not in latex_fragment:
        logger.info("No <CITATION/> tag found in latex_fragment. Returning empty list.")
        return []

    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1000,
            temperature=0.2,
            system="You are an expert in academic literature and scientific research.",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""
Please suggest appropriate papers to be cited area marked <CITATION/>. 
Avoid papers that are already cited right after <CITATION/> mark.

For each suggested paper, provide a BibTeX entry and a brief explanation of why it's relevant. 
Format your response as follows for each suggestion:

[BibTeX START]
(BibTeX entry)
[BibTeX END]

[EXPLANATION]
(Explanation)
[EXPLANATION END]

{latex_fragment}
                            """
                        }
                    ]
                }
            ]
        )
        suggestions = message.content[0].text
        return parse_suggestions(suggestions)
    except Exception as e:
        logger.error(f"Error in suggest_citations: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def parse_suggestions(suggestions: str) -> List[dict]:
    logger.info("Parsing suggestions")
    bibtex_pattern = r'\[BibTeX START\]\n(.*?)\n\[BibTeX END\]'
    explanation_pattern = r'\[EXPLANATION\]\n(.*?)\n\[EXPLANATION END\]'
    
    bibtex_entries = re.findall(bibtex_pattern, suggestions, re.DOTALL)
    explanations = re.findall(explanation_pattern, suggestions, re.DOTALL)
    
    return [
        {
            "bibtex": bibtex.strip(),
            "explanation": explanation.strip(),
            "parsed_paper": parse_bibtex(bibtex.strip())
        }
        for bibtex, explanation in zip(bibtex_entries, explanations)
    ]

class SelectionRequest(BaseModel):
    selection: dict

@app.post("/process-selection")
async def process_selection(request: SelectionRequest):
    logger.info("Processing selection")
    try:
        text = request.selection['text']
        start = request.selection['start']
        end = request.selection['end']
        selected_text = text[start:end]
        
        processed_text = process_citation(text, start, end)
        papers = suggest_citations(processed_text)
        
        return {
            "selected_text": selected_text,
            "processed_text": processed_text,
            "processed_start_end": [start, end],
            "suggested_papers": papers,
            "message": "Selection processed successfully"
        }
    except Exception as e:
        logger.error(f"Error in process_selection: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

class BibtexRequest(BaseModel):
    bibtex: str

@app.post("/parse-bibtex")
async def parse_bibtex_endpoint(request: BibtexRequest):
    logger.info("Parsing BibTeX")
    try:
        parsed_entry = parse_bibtex(request.bibtex)
        
        if parsed_entry:
            return parsed_entry
        else:
            return {"error": "Failed to parse BibTeX"}
    except Exception as e:
        logger.error(f"Error parsing BibTeX: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Failed to parse BibTeX: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)