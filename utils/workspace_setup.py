import os
from whyhow import AsyncWhyHow
from typing import Optional, Dict, Any
import aiohttp
import asyncio
from botocore.exceptions import ClientError
import boto3

async def upload_document_async(client, workspace_id: str, filepath: str, bucket_name: str) -> Dict:
    """Upload document to workspace."""
    try:
        document_name = os.path.basename(filepath)
        
        # Get presigned URL for upload
        presigned_response = await client._make_request(
            'POST',
            '/documents/generate_presigned',
            json={
                "workspace_id": workspace_id,
                "filename": document_name
            }
        )
        
        if not presigned_response:
            raise ValueError("No presigned response received")
            
        print(f"[DEBUG] Presigned response: {presigned_response}")
        document_id = presigned_response['fields']['x-amz-meta-document-id']
        
        # Read and upload file
        with open(filepath, 'rb') as f:
            file_content = f.read()
        
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            for key, value in presigned_response['fields'].items():
                form.add_field(key, value)
            form.add_field('file', 
                         file_content,
                         filename=document_name,
                         content_type='application/pdf')
            
            async with session.post(presigned_response['url'], data=form) as response:
                print(f"Upload response status: {response.status}")
                if response.status not in (200, 204):
                    text = await response.text()
                    print(f"Upload response text: {text}")
                    raise ValueError(f"Upload failed with status {response.status}")
                
                # After successful S3 upload
                if response.status == 204:
                    # Wait a bit for S3 propagation
                    await asyncio.sleep(2)
                    
                    try:
                        # Update document status
                        status_update = await client._make_request(
                            'PUT',
                            f'/documents/{document_id}/status',
                            params={"status": "uploaded"}
                        )
                        print(f"[INFO] Document status updated: {status_update}")
                    except Exception as e:
                        print(f"[WARNING] Failed to update document status: {str(e)}")
                        # Continue anyway as the file is uploaded
        
        return {
            "document_id": document_id,
            "name": document_name,
            "workspace_id": workspace_id,
            "status": "uploaded"
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to upload document: {str(e)}")
        raise

async def document_exists_async(client, workspace_id: str, document_name: str) -> Optional[Dict]:
    """Check if a document exists in the workspace."""
    try:
        documents = await client._make_request('GET', f'/documents?workspace_id={workspace_id}')
        print(f"[DEBUG] Documents response: {documents}")
        for doc in documents.get('documents', []):
            if doc.get('name') == document_name:
                return doc
        return None
    except Exception as e:
        print(f"[ERROR] Failed to check document existence: {str(e)}")
        raise

async def get_or_create_workspace(client, workspace_name: str) -> str:
    """Get or create a workspace."""
    try:
        # Check if workspace exists
        workspaces = await client._make_request('GET', '/workspaces')
        for ws in workspaces.get('workspaces', []):
            if ws.get('name') == workspace_name:
                print(f"[INFO] Workspace '{workspace_name}' found.")
                return ws['_id']
        
        # Create workspace if not found
        workspace = await client._make_request(
            'POST',
            '/workspaces',
            json={"name": workspace_name}
        )
        print(f"[INFO] Created new workspace: {workspace}")
        return workspace['_id']
    except Exception as e:
        print(f"[ERROR] Failed to get or create workspace: {str(e)}")
        raise

# Async version to get workspace id by name
async def get_workspace_id_by_name_async(client, workspace_name: str) -> Optional[str]:
    """Get workspace ID by name using async client."""
    try:
        workspaces = await client.get_workspaces()
        
        for workspace in workspaces.get('workspaces', []):
            if workspace.get('name') == workspace_name:
                return str(workspace.get('_id'))
                
        print(f"[WARNING] Workspace '{workspace_name}' not found")
        return None
        
    except Exception as e:
        print(f"[ERROR] Failed to get workspace ID: {str(e)}")
        raise

# Async version to get existing workspace by id
async def get_existing_workspace_async(client, workspace_id: str) -> Dict[str, Any]:
    """Get existing workspace by ID using async client."""
    try:
        workspace = await client.get_workspace(workspace_id)
        if not workspace:
            raise ValueError(f"Workspace with ID {workspace_id} not found")
        return workspace
    except Exception as e:
        print(f"[ERROR] Failed to get workspace: {str(e)}")
        raise

import boto3
from botocore.exceptions import ClientError

async def upload_and_verify_document(client, workspace_id: str, filepath: str) -> Optional[Dict]:
    """Upload a document and verify its existence."""
    try:
        document_name = os.path.basename(filepath)
        user_id = "674868d49a8e3a1ab2d8cad8"
        s3_path = f"{user_id}/{document_name}"
        bucket_name = os.getenv('WHYHOW__AWS__S3__BUCKET', 'knowledge-graphs-655291442696-dev')
        
        # Check for existing document
        documents = await client._make_request('GET', f'/documents?workspace_id={workspace_id}')
        print(f"[DEBUG] Initial documents query response: {documents}")
        
        matching_docs = [
            doc for doc in documents.get('documents', []) 
            if (doc.get('name') == document_name or 
                doc.get('metadata', {}).get('key') == s3_path or
                doc.get('metadata', {}).get('filename') == document_name)
        ]
        
        if matching_docs:
            print(f"[INFO] Document {document_name} already exists in database")
            return matching_docs[0]
            
        max_retries = 3
        retry_delay = 15
        
        for attempt in range(max_retries):
            try:
                # Upload document
                document = await upload_document_async(client, workspace_id, filepath, bucket_name)
                if document:
                    print(f"[INFO] Document upload response: {document}")
                    document_id = document.get('document_id')
                    
                    if not document_id:
                        print("[ERROR] No document_id in upload response")
                        continue
                    
                    # Wait for processing
                    await asyncio.sleep(retry_delay)
                    
                    # Try to process the document
                    try:
                        process_response = await client._make_request(
                            'POST',
                            f'/documents/{document_id}/process',
                            json={"workspace_id": workspace_id}
                        )
                        if process_response:
                            print(f"[INFO] Document processing started: {process_response}")
                            await asyncio.sleep(retry_delay)
                    except Exception as e:
                        print(f"[WARNING] Failed to process document: {str(e)}")
                        continue
                    
                    # Final verification
                    documents = await client._make_request('GET', f'/documents?workspace_id={workspace_id}')
                    print(f"[DEBUG] Final documents query: {documents}")
                    
                    matching_docs = [
                        doc for doc in documents.get('documents', []) 
                        if (doc.get('name') == document_name or 
                            doc.get('metadata', {}).get('key') == s3_path or
                            doc.get('metadata', {}).get('filename') == document_name or
                            doc.get('id') == document_id)
                    ]
                    
                    if matching_docs:
                        return matching_docs[0]
                        
            except Exception as e:
                if "Document already exists" in str(e):
                    print(f"[INFO] Document exists in S3, waiting for processing... (attempt {attempt + 1})")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    raise
                    
        print(f"[ERROR] Document {document_name} not found after {max_retries} attempts")
        return None

    except Exception as e:
        print(f"[ERROR] Failed to upload and verify document: {str(e)}")
        return None
    
    