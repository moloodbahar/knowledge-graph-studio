import asyncio
import httpx
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
            # List all graphs
            response = await http.get("/graphs")
            response.raise_for_status()
            data = response.json()
            
            print("\nAvailable Graphs:")
            print("----------------")
            for graph in data['graphs']:
                print(f"ID: {graph['_id']}")
                print(f"Name: {graph['name']}")
                print(f"Status: {graph['status']}")
                print(f"Created: {graph['created_at']}")
                print("----------------")

        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e}")
        except Exception as e:
            print(f"Error listing graphs: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 