import asyncio
import httpx
from bson import ObjectId
from dotenv import find_dotenv, load_dotenv

async def main():
    # Load environment variables
    load_dotenv(find_dotenv())

    # API keys and configuration
    api_key = 'NrdEeP3zwltR9WlZ72nuWs972E1c6StdXZzBKaXu'
    base_url = "http://127.0.0.1:8000"

    # Create HTTP client with proper auth header format
    headers = {
        "X-API-Key": api_key,
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(
        base_url=base_url,
        headers=headers
    ) as http:
        try:
            # Get list of graphs
            response = await http.get("/graphs")
            response.raise_for_status()
            graphs = response.json()['graphs']
            
            if not graphs:
                print("No graphs found in the system")
                return
                
            print("\nAvailable Graphs:")
            print("----------------")
            for graph in graphs:
                print(f"Name: {graph['name']}")
                print(f"ID: {graph['_id']}")
                print(f"Schema ID: {graph['schema']['_id']}")
                print(f"Status: {graph['status']}")
                print("----------------")
            
            # Find graphs with "MICA" in the name
            mica_graphs = [g for g in graphs if 'MICA' in g['name']]
            
            if not mica_graphs:
                print("\nNo graphs with 'MICA' in the name found")
                return
                
            for graph in mica_graphs:
                graph_id = graph['_id']
                schema_id = graph['schema']['_id']
                
                print(f"\nDeleting graph: {graph['name']} ({graph_id})")
                print("----------------")
                
                # Delete the graph
                response = await http.delete(f"/graphs/{graph_id}")
                response.raise_for_status()
                response_data = response.json()
                
                # Parse the deletion results
                print(f"Chunks deleted: {response_data.get('chunks_deleted', 0)}")
                print(f"Nodes deleted: {response_data.get('nodes_deleted', 0)}")
                print(f"Triples deleted: {response_data.get('triples_deleted', 0)}")
                print(f"Queries deleted: {response_data.get('queries_deleted', 0)}")
                
                # Delete the schema
                try:
                    schema_response = await http.delete(f"/schemas/{schema_id}")
                    if schema_response.status_code == 200:
                        print(f"Schema {schema_id} deleted successfully")
                except Exception as e:
                    print(f"Warning: Could not delete schema {schema_id}: {e}")
                
                print("Graph and schema deleted successfully")

        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
        except Exception as e:
            print(f"Error: {e}")
            if hasattr(e, 'response'):
                print(f"Response text: {e.response.text}")

if __name__ == "__main__":
    asyncio.run(main())