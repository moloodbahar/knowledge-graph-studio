from dotenv import find_dotenv, load_dotenv
import os
from whyhow import WhyHow

from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv())

whyhow_api_key = 'NrdEeP3zwltR9WlZ72nuWs972E1c6StdXZzBKaXu'
base_url = "http://localhost:8000"  # Try localhost instead of 127.0.0.1

# Configure WhyHow client
client = WhyHow(
    api_key=whyhow_api_key, 
    base_url=base_url
)


workspace = client.workspaces.create(name="Analysis_Regs")

print(workspace.workspace_id)
