import os
import re
import logging
from fastapi import FastAPI, HTTPException, Request
import bibtexparser
import anthropic
import traceback

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(root_path="/api")

# Initialize Anthropic client
client = anthropic.Anthropic()

def log_env_variables():
    logger.info("Logging all environment variable keys:")
    for key in os.environ.keys():
        logger.info(f"Environment variable present: {key}")

log_env_variables()

def process_citation(text, start, end):
    logger.info(f"Entering process_citation function with start={start}, end={end}")
    logger.debug(f"Input text: {text}")
    
    if text[start:end][:4] != 'cite' or start == 0:
        logger.info("No citation found or invalid start position. Returning original text.")
        return text
    else:
        start = start - 1
        end = min(end + 3,len(text))
        logger.debug(f"Adjusted start={start}, end={end}")

    slice = text[start:end]
    logger.debug(f"Slice to process: {slice}")
    
    patterns = [
        (r'\\cite\{', r'\cite{<CITATION/>,'),
        (r'\\citet\{', r'\citet{<CITATION/>,'),
        (r'\\citep\{', r'\citep{<CITATION/>,'),
    ]
    
    for pattern, replacement in patterns:
        match = re.search(pattern, slice)
        if match:
            logger.info(f"Found matching pattern: {pattern}")
            slice = slice[:match.start()] + replacement + slice[match.end():]
            logger.debug(f"Replaced slice: {slice}")
            break
    
    text = text[:start] + slice + text[end:]
    logger.info("Citation processing completed")
    logger.debug(f"Processed text: {text}")
    return text

def parse_bibtex(bibtex_str):
    logger.info("Parsing BibTeX entry")
    try:
        bib_database = bibtexparser.loads(bibtex_str)
        if bib_database.entries:
            parsed_entry = bib_database.entries[0]
            logger.debug(f"Parsed BibTeX entry: {parsed_entry}")
            return parsed_entry
        else:
            logger.warning("No entries found in BibTeX string")
            return None
    except Exception as e:
        logger.error(f"Error parsing BibTeX: {str(e)}")
        return None

def suggest_citations(latex_fragment):
    logger.info("Entering suggest_citations function")
    logger.debug(f"Input latex_fragment: {latex_fragment}")

    def parse_suggestions(suggestions):
        logger.info("Parsing suggestions")
        bibtex_pattern = r'\[BibTeX START\]\n(.*?)\n\[BibTeX END\]'
        explanation_pattern = r'\[EXPLANATION\]\n(.*?)\n\[EXPLANATION END\]'
        
        bibtex_entries = re.findall(bibtex_pattern, suggestions, re.DOTALL)
        explanations = re.findall(explanation_pattern, suggestions, re.DOTALL)
        
        logger.debug(f"Found {len(bibtex_entries)} BibTeX entries and {len(explanations)} explanations")
        
        parsed_list = []
        for bibtex, explanation in zip(bibtex_entries, explanations):
            parsed_bibtex = parse_bibtex(bibtex.strip())
            parsed_list.append({
                "bibtex": bibtex.strip(),
                "explanation": explanation.strip(),
                "parsed_paper": parsed_bibtex
            })
        return parsed_list

    if '<CITATION/>' not in latex_fragment:
        logger.info("No <CITATION/> tag found in latex_fragment. Returning empty list.")
        return []

    try:
        logger.info("Sending request to Anthropic API")
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
                            "text": """
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

                            """ + latex_fragment
                        }
                    ]
                }
            ]
        )
        logger.info("Received response from Anthropic API")
        suggestions = message.content[0].text
        logger.debug(f"Raw suggestions: {suggestions}")
        
        papers = parse_suggestions(suggestions)
        logger.info(f"Parsed {len(papers)} paper suggestions")
        return papers
    except Exception as e:
        logger.error(f"Error in suggest_citations: {str(e)}")
        logger.error(traceback.format_exc())
        raise

@app.post("/process-selection")
async def process_selection(request: Request):
    logger.info("Received POST request to /process-selection")
    try:
        data = await request.json()
        logger.debug(f"Request data: {data}")
        
        text = data['selection']['text']
        start = data['selection']['start']
        end = data['selection']['end']
        selected_text = text[start:end]
        
        logger.info(f"Processing selection: start={start}, end={end}")
        logger.debug(f"Selected text: {selected_text}")

        processed_text = process_citation(text, start, end)
        logger.info("Citation processing completed")

        logger.info("Suggesting citations")
        papers = suggest_citations(processed_text)
        
        response = {
            "selected_text": selected_text,
            "processed_text": processed_text,
            "processed_start_end": [start, end],
            "suggested_papers": papers,
            "message": "Selection processed successfully"
        }
        logger.info("Sending response")
        logger.debug(f"Response: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in process_selection: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parse-bibtex")
async def parse_bibtex_endpoint(request: Request):
    logger.info("Received POST request to /parse-bibtex")
    try:
        data = await request.json()
        bibtex_str = data['bibtex']
        logger.debug(f"Input BibTeX: {bibtex_str}")
        
        parsed_entry = parse_bibtex(bibtex_str)
        
        if parsed_entry:
            logger.info("Successfully parsed BibTeX entry")
            logger.debug(f"Parsed entry: {parsed_entry}")
            return parsed_entry
        else:
            logger.warning("Failed to parse BibTeX entry")
            return {"error": "Failed to parse BibTeX"}
    except Exception as e:
        logger.error(f"Error parsing BibTeX: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Failed to parse BibTeX: {str(e)}"}

if __name__ == "__main__":
    logger.info("Starting FastAPI server")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)