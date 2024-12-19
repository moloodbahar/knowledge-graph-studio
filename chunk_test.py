from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List
from utils.schema_creation import get_allowed_nodes
import pymupdf
import asyncio
from langchain_openai import ChatOpenAI
from langchain.schema import Document
from langchain_core.documents import Document
from whyhow.schemas import Chunk, GraphChunk, Triple, Node, Relation
from langchain_experimental.graph_transformers import LLMGraphTransformer
from dotenv import find_dotenv, load_dotenv
import os
import warnings
import asyncio
import re
from difflib import SequenceMatcher


from whyhow import WhyHow, Node, Relation, Triple

from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())

# Disable SSL verification warnings if using VPN
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Add workspace configuration
workspace_id = "67629b0dee7b240a35b97963"  # workspace ID for "Analysis_Regs"
user_id = "674868d49a8e3a1ab2d8cad8"      # my user ID

# File path configuration
filepath = "regs/fatf_sanctions.pdf"
name_of_document = "FATF Sanctions"
graph_name = f"Graph merge_nodes_test_1_{name_of_document}"

# API keys and configuration with VPN considerations
whyhow_api_key = 'NrdEeP3zwltR9WlZ72nuWs972E1c6StdXZzBKaXu'
base_url = "http://localhost:8000"  # Try localhost instead of 127.0.0.1

# Debug: Check API key and set it properly
api_key = os.getenv("WHYHOW__GENERATIVE__OPENAI__API_KEY")
if not api_key:
    raise ValueError("WHYHOW__GENERATIVE__OPENAI__API_KEY is not set or could not be loaded!")

# Set OpenAI API key explicitly
os.environ["OPENAI_API_KEY"] = api_key

# Initialize ChatOpenAI with the correct model name
llm = ChatOpenAI(
    model="gpt-4o-mini",  # Changed from "gpt-4o-mini" to "gpt-4"
    temperature=0.1
)

# Configure WhyHow client
client = WhyHow(
    api_key=whyhow_api_key, 
    base_url=base_url
)



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
    
async def split_and_process_pdf(filepath, chunk_size=10):
    # Split PDF into 10-page chunks and process each chunk
    doc = pymupdf.open(filepath)
    num_pages = doc.page_count
    batch_chunks = []

    for start_page in range(0, num_pages, chunk_size):
        batch = []
        page_numbers = []
        for page_num in range(start_page, min(start_page + chunk_size, num_pages)):
            page = doc.load_page(page_num)
            batch.append(page.get_text("text"))
            page_numbers.append(page_num + 1)  # Store actual page numbers (1-indexed)

        # Process each 10-page batch and pass page numbers
        split_docs = await process_documents(batch, page_numbers)
        batch_chunks.extend(split_docs)

    doc.close()
    return batch_chunks

class CustomGraphTransformer(LLMGraphTransformer):
    def __init__(self, llm, allowed_nodes):
        super().__init__(llm=llm, allowed_nodes=allowed_nodes)
        self.allowed_nodes = allowed_nodes
        print(f"[DEBUG] Initialized transformer with allowed nodes: {self.allowed_nodes}")

    async def aconvert_to_graph_documents(self, documents: List[Document]):
        print("[DEBUG] Starting document transformation")
        # Get the original graph documents
        graph_documents = await super().aconvert_to_graph_documents(documents)
        print(f"[DEBUG] Generated {len(graph_documents)} initial documents")
        
        # Process each document for merging
        merged_documents = []
        for doc in graph_documents:
            if not doc.relationships:
                continue
                
            print(f"\n[DEBUG] Processing document with {len(doc.relationships)} relationships")
            # Get all unique nodes from relationships
            nodes = set()
            for rel in doc.relationships:
                nodes.add(rel.source)
                nodes.add(rel.target)
            
            # Check for node merging
            nodes = list(nodes)
            merged_nodes = {}
            for i, node1 in enumerate(nodes):
                if node1.id in merged_nodes:
                    continue
                    
                for node2 in nodes[i+1:]:
                    if node2.id in merged_nodes:
                        continue
                        
                    if self._should_merge_nodes(node1, node2):
                        print(f"[MERGE] Merging {node1.id} into {node2.id}")
                        merged_nodes[node1.id] = node2.id
            
            # If we found merges, create new relationships
            if merged_nodes:
                new_relationships = []
                for rel in doc.relationships:
                    source_id = merged_nodes.get(rel.source.id, rel.source.id)
                    target_id = merged_nodes.get(rel.target.id, rel.target.id)
                    source = next(n for n in nodes if n.id == source_id)
                    target = next(n for n in nodes if n.id == target_id)
                    new_relationships.append(type(rel)(
                        source=source,
                        target=target,
                        type=rel.type
                    ))
                doc.relationships = new_relationships
            
            merged_documents.append(doc)
            
        print(f"[DEBUG] Returning {len(merged_documents)} merged documents")
        return merged_documents

    def _should_merge_nodes(self, node1, node2) -> bool:
        """Custom merger that checks for node similarity"""
        print("\n" + "="*50)
        print(f"[MERGE] Checking merge for:")
        print(f"[MERGE] Node 1: {node1.id} (Type: {node1.type})")
        print(f"[MERGE] Node 2: {node2.id} (Type: {node2.type})")
        
        # First check if types match
        if node1.type != node2.type:
            print(f"[MERGE] ❌ Types don't match: {node1.type} != {node2.type}")
            return False
            
        # Check if the type is in allowed nodes (case-insensitive comparison)
        node_type = node1.type
        if not any(allowed.lower() == node_type.lower() for allowed in self.allowed_nodes):
            print(f"[MERGE] ❌ Type {node_type} not in allowed nodes")
            return False
        
        # Normalize both node names
        name1 = self.normalize_node_name(node1.id)
        name2 = self.normalize_node_name(node2.id)
        
        print(f"[MERGE] Normalized names: '{name1}' and '{name2}'")
        
        # If names are identical after normalization, merge them
        if name1 == name2:
            print(f"[MERGE] ✅ Merging nodes (exact match)")
            return True
        
        # If not identical, check similarity for possible typos
        similarity = SequenceMatcher(None, name1, name2).ratio()
        print(f"[MERGE] Similarity score: {similarity}")
        
        if similarity >= 0.85:
            print(f"[MERGE] ✅ Merging nodes (similarity: {similarity})")
            return True
        
        print("[MERGE] ❌ No merge - similarity too low")
        print("="*50)
        return False

async def process_documents(pages_text: List[str], page_numbers: List[int]):
    global name_of_document
    load_dotenv(find_dotenv())

    llm = ChatOpenAI(model="gpt-4o-mini")
    
    # Get allowed nodes once
    allowed_nodes = get_allowed_nodes(name_of_document)
    if page_numbers[0] == 1:  # Only print for first batch
        print(f"[INFO] Using allowed nodes for {name_of_document}:", allowed_nodes)

    text_splitter = SentenceAwareSplitter(chunk_size=1000, chunk_overlap=0)
    split_docs = []
    
    for i, text in enumerate(pages_text):
        chunks = text_splitter.split_text(text)
        page_num = page_numbers[i]
        split_docs.extend([
            Document(page_content=chunk, metadata={"source": name_of_document, "page": page_num})
            for chunk in chunks
        ])
    
    # Initialize our custom transformer with allowed nodes
    transformer = CustomGraphTransformer(llm=llm, allowed_nodes=allowed_nodes)
    print("[DEBUG] Starting document transformation with custom transformer")
    
    # Process documents in smaller batches to avoid timeouts
    BATCH_SIZE = 5
    all_chunks = []
    
    for i in range(0, len(split_docs), BATCH_SIZE):
        batch = split_docs[i:i + BATCH_SIZE]
        lc_graph_documents = await transformer.aconvert_to_graph_documents(batch)
        
        # Convert LangChain graph documents to WhyHow graph chunks
        for doc in lc_graph_documents:
            if not doc.relationships:  # Skip if no relationships found
                continue
                
            # Create chunk from document
            chunk = Chunk(
                content=doc.source.page_content[:1024],
                user_metadata=doc.source.metadata
            )
            
            # Convert relationships to triples
            triples = []
            for rel in doc.relationships:
                head_node = Node(
                    name=rel.source.id,
                    label=rel.source.type,
                    properties=rel.source.properties,
                    chunk_ids=[chunk.chunk_id] if chunk.chunk_id else []
                )
                tail_node = Node(
                    name=rel.target.id,
                    label=rel.target.type,
                    properties=rel.target.properties,
                    chunk_ids=[chunk.chunk_id] if chunk.chunk_id else []
                )
                relation = Relation(
                    name=rel.type,
                    properties=rel.properties if hasattr(rel, 'properties') else {}
                )
                triples.append(Triple(head=head_node, tail=tail_node, relation=relation))
            
            if triples:  # Only add if we have valid triples
                all_chunks.append(GraphChunk(chunk=chunk, triples=triples))
        
        print(f"[DEBUG] Processed batch {i//BATCH_SIZE + 1} with {len(lc_graph_documents)} chunks")
    
    print(f"[INFO] Processed {len(split_docs)} chunks for pages {page_numbers}")
    print(f"[INFO] Created {len(all_chunks)} graph chunks for pages {page_numbers}")
    
    return all_chunks
    

def create_graph(client, chunks, graph_name, workspace_id):
    """Non-async function to handle graph creation"""
    try:
        print(f"[INFO] Creating graph '{graph_name}' with {len(chunks)} chunks...")
        graph = client.graphs.create_graph_from_graph_chunks(
            name=graph_name,
            workspace_id=workspace_id,
            graph_chunks=chunks
        )
        print(f"[SUCCESS] Created graph with ID: {graph.graph_id}")
        return graph
    except Exception as e:
        print(f"[ERROR] Failed to create graph: {str(e)}")
        if hasattr(e, 'response'):
            print(f"[ERROR] Response: {e.response.text}")
        raise

async def main():
    """Main async function"""
    print("[INFO] Starting graph creation process...")
    
    # Get all chunks from PDF
    all_chunks = await split_and_process_pdf(filepath, chunk_size=10)
    
    if not all_chunks:
        print("[ERROR] No graph chunks generated. Exiting.")
        return

    try:
        # Process chunks in smaller batches to avoid connection issues
        BATCH_SIZE = 20
        current_graph = None
        
        for i in range(0, len(all_chunks), BATCH_SIZE):
            batch = all_chunks[i:i + BATCH_SIZE]
            print(f"[INFO] Processing batch {i//BATCH_SIZE + 1} of {(len(all_chunks) + BATCH_SIZE - 1)//BATCH_SIZE}")
            
            try:
                if current_graph is None:  # First batch - create new graph
                    current_graph = client.graphs.create_graph_from_graph_chunks(  # Removed await
                        name=graph_name,
                        workspace_id=workspace_id,
                        graph_chunks=batch
                    )
                    print(f"[SUCCESS] Created initial graph with ID: {current_graph.graph_id}")
                    
                    # Store graph ID
                    with open('store_id.txt', 'w') as f:
                        f.write(f"Graph ID: {current_graph.graph_id}\n")
                    print("[INFO] Graph ID stored in store_id.txt")
                else:  # Subsequent batches - append to existing graph
                    client.graphs.append_graph_chunks(  # Removed await
                        graph_id=current_graph.graph_id,
                        graph_chunks=batch
                    )
                    print(f"[INFO] Appended batch to graph {current_graph.graph_id}")
                
                await asyncio.sleep(2)  # Small delay between batches
                
            except Exception as e:
                print(f"[ERROR] Failed to process batch: {str(e)}")
                if hasattr(e, 'response'):
                    print(f"[ERROR] Response: {e.response.text}")
                raise  # Re-raise to handle in outer try-except

    except Exception as e:
        print(f"[ERROR] Failed to create/update graph: {str(e)}")
        if hasattr(e, 'response'):
            print(f"[ERROR] Response: {e.response.text}")
        raise

if __name__ == "__main__":
    asyncio.run(main())