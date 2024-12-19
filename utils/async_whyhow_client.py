import os
import httpx
import logging
from typing import Dict, Any, List
from whyhow.schemas import GraphChunk
from httpx import TimeoutException
from tenacity import retry, stop_after_attempt, wait_exponential
import asyncio
import aiohttp

class WhyHowAsync:
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or os.getenv("WHYHOW__API__BASE_URL", "http://127.0.0.1:8000")
        self.api_key = api_key or os.getenv("WHYHOW__API__KEY")
        if not self.api_key:
            raise ValueError("API key not found in environment variables (WHYHOW__API__KEY).")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json"
            },
            timeout=60.0
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make a request to the WhyHow API with better error handling."""
        try:
            response = await self.client.request(method, f"{self.base_url}{endpoint}", **kwargs)
            response.raise_for_status()
            return response.json()
        except TimeoutException:
            logging.error(f"Timeout connecting to WhyHow API at {endpoint}. Please ensure the server is running.")
            raise ConnectionError("Failed to connect to WhyHow API - server may not be running.")
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logging.error(f"Error making request: {str(e)}")
            raise

    async def create_graph_from_chunks(
        self,
        workspace_id: str,
        name: str,
        graph_chunks: List[GraphChunk]
    ) -> Dict[str, Any]:
        """Create a graph using graph chunks."""
        payload = {
            "workspace": workspace_id,
            "name": name,
            "graph_chunks": [chunk.dict() if hasattr(chunk, 'dict') else chunk for chunk in graph_chunks]
        }
        return await self._make_request('POST', '/graphs/from_chunks', json=payload)


    async def upload_document(self, workspace_id: str, filepath: str) -> str:
        """Upload a document to a workspace and return the document ID."""
        try:
            # Get presigned URL with document metadata
            presigned = await self._make_request(
                'POST',
                '/documents/generate_presigned',
                json={
                    "workspace_id": workspace_id,
                    "filename": os.path.basename(filepath)
                }
            )
            
            # Extract document ID from the metadata fields
            document_id = presigned.get('fields', {}).get('x-amz-meta-document-id')
            url = presigned.get('url')
            fields = presigned.get('fields', {})
            
            print(f"Got presigned URL with document ID: {document_id}")
            
            # Read file content
            with open(filepath, 'rb') as f:
                file_content = f.read()

            # Create form data in the exact order S3 expects
            form = aiohttp.FormData()
            # Add all fields from presigned URL first
            for key, value in fields.items():
                form.add_field(key, str(value))
            # Add the file last
            form.add_field('file', 
                          file_content,
                          filename=os.path.basename(filepath),
                          content_type='application/pdf')

            # Upload to S3 using aiohttp for multipart
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form) as response:
                    print(f"Upload response status: {response.status}")
                    if response.status >= 400:
                        text = await response.text()
                        print(f"Error response: {text}")
                        response.raise_for_status()

            # Wait and check document status with retries
            max_retries = 5
            for i in range(max_retries):
                await asyncio.sleep(2)  # Wait between checks
                try:
                    # Try to get document list
                    docs = await self._make_request(
                        'GET',
                        f'/documents?workspace_id={workspace_id}'
                    )
                    # Check if our document is in the list
                    for doc in docs.get('documents', []):
                        if doc.get('id') == document_id:
                            print(f"Document found and processed with ID: {document_id}")
                            return document_id
                except Exception as e:
                    print(f"Attempt {i+1}: Waiting for document to be processed...")
                    if i == max_retries - 1:
                        print(f"Warning: Could not confirm document status: {e}")
            
            return document_id
            
        except Exception as e:
            logging.error(f"Failed to upload document: {str(e)}")
            raise

    async def get_documents(self, workspace_id: str) -> Dict[Any, Any]:
        """Get all documents in a workspace."""
        return await self._make_request('GET', f'/documents?workspace_id={workspace_id}')

    async def get_document(self, document_id: str) -> Dict[Any, Any]:
        """Get a specific document by ID."""
        return await self._make_request('GET', f'/documents/{document_id}')

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def get_workspaces(self) -> Dict[str, Any]:
        """Get all workspaces."""
        try:
            response = await self._make_request('GET', '/workspaces')
            return {
                'workspaces': response.get('workspaces', [])
            }
        except Exception as e:
            logging.error(f"Failed to get workspaces: {str(e)}")
            raise

    async def get_workspace(self, workspace_id: str) -> Dict[str, Any]:
        """Get a specific workspace by ID."""
        try:
            return await self._make_request('GET', f'/workspaces/{workspace_id}')
        except Exception as e:
            logging.error(f"Failed to get workspace {workspace_id}: {str(e)}")
            raise

    async def get_graphs(self, workspace_id: str) -> Dict[str, Any]:
        """Get all graphs in a workspace."""
        try:
            response = await self._make_request(
                'GET',
                f'/graphs?workspace_id={workspace_id}'
            )
            return response
        except Exception as e:
            logging.error(f"Failed to get graphs: {str(e)}")
            raise

    async def create_graph(self, workspace_id, graph_name, triples):
        """Create a graph using the from_triples endpoint."""
        try:
            response = await self._make_request(
                'POST',
                '/graphs/from_triples',
                json={
                    "name": graph_name,
                "workspace": workspace_id,
                "triples": triples,
                },
            )
            response.raise_for_status()
            print("[INFO] Graph created successfully:", response.json())
            return response.json()
        except httpx.HTTPStatusError as e:
            logging.error(f"[HTTP ERROR] Failed to create graph: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logging.error(f"[ERROR] An error occurred: {str(e)}")
            return None
    
