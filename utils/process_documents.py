from langchain.text_splitter import TextSplitter
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from typing import List, Dict, Any, Tuple
from utils.schema_creation import get_allowed_nodes, generate_schema_async, schema_exists_async
import pymupdf
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from langchain_core.documents import Document
from whyhow.schemas import Chunk, GraphChunk, Triple, Node, Relation
from langchain_experimental.graph_transformers import LLMGraphTransformer
from dotenv import find_dotenv, load_dotenv
import os
from langchain.schema import SystemMessage, HumanMessage
import logging
from bson import ObjectId

# Load environment variables
load_dotenv()

class SentenceAwareSplitter(RecursiveCharacterTextSplitter):
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        separators = ["\n\n", "\n", ".", "!", "?"]  # Common sentence boundaries
        super().__init__(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators
        )

    def split_text(self, text: str) -> List[str]:
        splits = self.split_by_separators(text, self._separators)
        
        final_chunks = []
        current_chunk = []
        current_size = 0

        for split in splits:
            if current_size + len(split) <= 1048:  # Respect chunk size limit
                current_chunk.append(split)
                current_size += len(split)
            else:
                if current_chunk:

                    # Move the last sentence to the next chunk
                    last_sentence = current_chunk.pop()  # Take the last sentence
                    final_chunks.append(" ".join(current_chunk))
                    current_chunk = [last_sentence, split] 
                    current_size = sum(len(s) for s in current_chunk)
        
        if current_chunk:
            final_chunks.append(" ".join(current_chunk))  # Add the remaining chunk

        return final_chunks

    def split_by_separators(self, text: str, separators: List[str]) -> List[str]:
        final_chunks = [text]
        for sep in separators:
            if sep:  # Only split if separator is not empty
                temp_chunks = []
                for chunk in final_chunks:
                    temp_chunks.extend(chunk.split(sep))
                final_chunks = temp_chunks
        return [chunk.strip() for chunk in final_chunks if chunk.strip()]
    
async def split_and_process_pdf(
    filepath: str,
    chunk_size: int = 10,
    client=None,
    workspace_id: str = None,
    name_of_document: str = None
) -> List[GraphChunk]:
    """Split PDF into chunks and process them for graph creation."""
    doc = pymupdf.open(filepath)
    num_pages = doc.page_count
    graph_chunks = []

    for start_page in range(0, num_pages, chunk_size):
        batch = []
        page_numbers = []
        for page_num in range(start_page, min(start_page + chunk_size, num_pages)):
            page = doc.load_page(page_num)
            batch.append(page.get_text("text"))
            page_numbers.append(page_num + 1)  # Store 1-indexed page numbers

        # Process each batch of pages
        batch_chunks = await process_documents(
            documents=batch,
            page_numbers=page_numbers,
            client=client,
            workspace_id=workspace_id,
            name_of_document=name_of_document,
        )
        graph_chunks.extend(batch_chunks)

    doc.close()
    return graph_chunks


async def process_documents(
    documents: List[str],
    page_numbers: List[int],
    client,
    workspace_id: str,
    name_of_document: str,
) -> List[GraphChunk]:
    """Process text documents to extract triples and generate graph chunks."""
    try:
        schema_name = f"{name_of_document}_Schema"

        # Check or create schema
        schema = await schema_exists_async(client, workspace_id, schema_name)
        if not schema:
            questions = [
                f"What entities are in {name_of_document}?",
                f"What relationships exist in {name_of_document}?",
            ]
            schema = await generate_schema_async(client, workspace_id, schema_name, questions)

        allowed_nodes = {entity["name"]: entity["type"] for entity in schema.get("entities", [])}
        allowed_relations = {relation["name"] for relation in schema.relations}

        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
            api_key=os.getenv("WHYHOW__GENERATIVE__OPENAI__API_KEY"),
        )

        graph_chunks = []

        for doc_text, page_num in zip(documents, page_numbers):
            prompt = f"""
            Extract knowledge triples in the format:
            Subject | PREDICATE | Object.
            Use these entity types: {', '.join(allowed_nodes.keys())}.
            Use these relationships: {', '.join(allowed_relations)}.
            Ensure accurate classification of entities and relationships based on types.
            """
            response = await llm.ainvoke(
                [
                    SystemMessage(content=prompt),
                    HumanMessage(content=f"Text: {doc_text}"),
                ]
            )

            # Parse response into triples
            triples_text = response.content.strip().split("\n")
            valid_triples = []
            for triple_text in triples_text:
                try:
                    parts = [x.strip() for x in triple_text.split("|")]
                    if len(parts) == 3:
                        head_name, relation_name, tail_name = parts
                        if relation_name not in allowed_relations:
                            logging.warning(f"Invalid relation: {relation_name}")
                            continue

                        head_type = allowed_nodes.get(head_name, "Generic")
                        tail_type = allowed_nodes.get(tail_name, "Generic")
                        if head_type == "Generic" or tail_type == "Generic":
                            logging.warning(f"Unrecognized node types for: {head_name}, {tail_name}")
                            continue

                        valid_triples.append(
                            Triple(
                                head=Node(name=head_name, label=head_type),
                                relation=Relation(name=relation_name),
                                tail=Node(name=tail_name, label=tail_type),
                            )
                        )
                except Exception as e:
                    logging.warning(f"Failed to process triple: {triple_text}. Error: {e}")

            if valid_triples:
                chunk = Chunk(content=doc_text, metadata={"page_number": page_num})
                graph_chunk = GraphChunk(chunk=chunk, triples=valid_triples)
                graph_chunks.append(graph_chunk)

        return graph_chunks

    except Exception as e:
        logging.error(f"Error processing documents: {e}")
        raise

