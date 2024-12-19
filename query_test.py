import itertools
import os
import pickle
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI

from whyhow import WhyHow, Node, Relation, Triple

from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())

# API keys and configuration
whyhow_api_key = 'NrdEeP3zwltR9WlZ72nuWs972E1c6StdXZzBKaXu'
base_url = "http://127.0.0.1:8000"

# Configure WhyHow client
client = WhyHow(
    api_key=whyhow_api_key, 
    base_url=base_url
)
# graph_id = "67602d3d7c3f884bc55e29bf"
# graph_id = "6761ae50eb63df05fa281c66"
# graph_id = "6762905e4b58f456960e7478"
# graph_id = "67629e0b91747e9cdaf1bf1e" Mica

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def get_graph_with_retry(client, graph_id):
    try:
        return client.graphs.get(graph_id=graph_id)
    except Exception as e:
        print(f"Error getting graph: {str(e)}")
        raise

# Use the retry function and handle the case where graph isn't found
try:
    # First get the graph
    graph = get_graph_with_retry(client, graph_id="676307615496017d6b4a356e")
    
    if not graph:
        print("Graph not found")
        exit(1)
        
    print(f"Successfully retrieved graph with ID: {graph.graph_id}")
    
    # Now query the graph
    query = client.graphs.query_unstructured(
        graph_id=graph.graph_id,
        query="What is the purpose of the AMLD6 directive? more details?",
        include_chunks=True
    )
    print(f"Query response: {query.answer}")
    
except Exception as e:
    print(f"Failed to get graph after retries: {str(e)}")
    exit(1)
