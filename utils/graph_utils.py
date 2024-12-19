# graph_utils.py

import sys
import os
import asyncio
from utils.async_whyhow_client import WhyHowAsync

# Add parent folder to the python research path 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Async version of get_graph_id_by_name
async def get_graph_id_by_name_async(client: WhyHowAsync, workspace_id: str, graph_name: str):
    graphs = await client.get_graphs(workspace_id)
    for graph in graphs.get('graphs', []):
        if graph['name'] == graph_name:
            return graph['_id']
    raise ValueError(f"The graph '{graph_name}' has not been found in the workspace.")

# Async version of graph_exists
async def graph_exists_async(client: WhyHowAsync, workspace_id: str, graph_name: str):
    graphs = await client.get_graphs(workspace_id)
    for graph in graphs.get('graphs', []):
        if graph['name'] == graph_name:
            return graph  # Return the existing graph object if it exists
    return None