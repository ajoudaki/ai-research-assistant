import re
import logging
from fastapi import FastAPI, HTTPException
import bibtexparser
import anthropic
from pydantic import BaseModel
from typing import List, Dict
import traceback

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(root_path="/api")

# Initialize Anthropic client
client = anthropic.Anthropic()

class CitationProcessor:
    def __init__(self, anthropic_client):
        self.anthropic_client = anthropic_client

    def process_citation(self, text: str, start: int, end: int) -> str:
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

    def parse_bibtex(self, bibtex_str: str) -> Dict:
        logger.info("Parsing BibTeX entry")
        try:
            bib_database = bibtexparser.loads(bibtex_str)
            if bib_database.entries:
                return bib_database.entries[0]
            else:
                logger.warning("No entries found in BibTeX string")
                return {}
        except Exception as e:
            logger.error(f"Error parsing BibTeX: {str(e)}")
            return {}

    def suggest_citations(self, latex_fragment: str) -> List[dict]:
        logger.info("Suggesting citations")

        if '<CITATION/>' not in latex_fragment:
            logger.info("No <CITATION/> tag found in latex_fragment. Returning empty list.")
            return []

        try:
            message = self.anthropic_client.messages.create(
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
            return self._parse_suggestions(suggestions)
        except Exception as e:
            logger.error(f"Error in suggest_citations: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def suggest_citations_from_bibliography(self, latex_fragment: str, bibliography: str) -> List[dict]:
        logger.info("Suggesting citations from provided bibliography")

        if '<CITATION/>' not in latex_fragment:
            logger.info("No <CITATION/> tag found in latex_fragment. Returning empty list.")
            return []

        try:
            message = self.anthropic_client.messages.create(
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
Please suggest appropriate papers to be cited in the area marked <CITATION/> using only the provided bibliography. 
Avoid papers that are already cited right after the <CITATION/> mark.

For each suggested paper, provide its BibTeX entry from the bibliography and a brief explanation of why it's relevant. 
Format your response as follows for each suggestion:

[BibTeX START]
(BibTeX entry)
[BibTeX END]

[EXPLANATION]
(Explanation)
[EXPLANATION END]

LaTeX Fragment:
{latex_fragment}

Bibliography:
{bibliography}
                                """
                            }
                        ]
                    }
                ]
            )
            suggestions = message.content[0].text
            return self._parse_suggestions(suggestions)
        except Exception as e:
            logger.error(f"Error in suggest_citations_from_bibliography: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _parse_suggestions(self, suggestions: str) -> List[dict]:
        logger.info("Parsing suggestions")
        bibtex_pattern = r'\[BibTeX START\]\n(.*?)\n\[BibTeX END\]'
        explanation_pattern = r'\[EXPLANATION\]\n(.*?)\n\[EXPLANATION END\]'

        bibtex_entries = re.findall(bibtex_pattern, suggestions, re.DOTALL)
        explanations = re.findall(explanation_pattern, suggestions, re.DOTALL)

        return [
            {
                "bibtex": bibtex.strip(),
                "explanation": explanation.strip(),
                "parsed_paper": self.parse_bibtex(bibtex.strip())
            }
            for bibtex, explanation in zip(bibtex_entries, explanations)
        ]

    def process_selection(self, text: str, start: int, end: int) -> Dict:
        logger.info("Processing selection")
        try:
            selected_text = text[start:end]
            processed_text = self.process_citation(text, start, end)
            papers = self.suggest_citations(processed_text)

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
            raise

# Initialize CitationProcessor
citation_processor = CitationProcessor(client)

class SelectionRequest(BaseModel):
    selection: dict

class BibliographySelectionRequest(BaseModel):
    selection: dict
    bibliography: str

class BibtexRequest(BaseModel):
    bibtex: str

@app.post("/process-selection")
async def process_selection_api(request: SelectionRequest):
    try:
        result = citation_processor.process_selection(
            request.selection['text'],
            request.selection['start'],
            request.selection['end']
        )
        return result
    except Exception as e:
        logger.error(f"Error in process_selection_api: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-selection-with-bibliography")
async def process_selection_with_bibliography_api(request: BibliographySelectionRequest):
    try:
        selected_text = request.selection['text'][request.selection['start']:request.selection['end']]
        processed_text = citation_processor.process_citation(
            request.selection['text'],
            request.selection['start'],
            request.selection['end']
        )
        papers = citation_processor.suggest_citations_from_bibliography(processed_text, request.bibliography)

        return {
            "selected_text": selected_text,
            "processed_text": processed_text,
            "processed_start_end": [request.selection['start'], request.selection['end']],
            "suggested_papers": papers,
            "message": "Selection processed successfully with provided bibliography"
        }
    except Exception as e:
        logger.error(f"Error in process_selection_with_bibliography_api: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/parse-bibtex")
async def parse_bibtex_api(request: BibtexRequest):
    logger.info("Parsing BibTeX")
    try:
        parsed_entry = citation_processor.parse_bibtex(request.bibtex)

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