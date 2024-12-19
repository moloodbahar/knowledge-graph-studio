# schema_creation.py
from typing import Dict, List, Optional
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from bson import ObjectId
from whyhow.schemas import Triple, Node, Relation

# Schema configurations
ALLOWED_NODES_CONFIG = allowed_nodes_dict = {
        "FATF Sanctions": [
            "Individual", "Organization", "Sanction", "Terrorist Activity", "Asset", 
            "Regulatory Body", "Government Agency", "Intelligence Agency", "Process", 
            "Policy", "Responsibility", "Obligation", "Legal Phrase", "Step", 'Year', 'Recommendation'
        ],
        "AMLD5": [
            "Person", "Organization", "Terrorist Activity", "Financial Institution", 
            "Obligation", "Corporate Structure", "Legal Arrangement", "Beneficial Owner", 
            "Virtual Currency", "Custodian Wallet Provider", "Transaction", "Regime", 
            "Criminal Organization", "Intelligence Unit", "Authority", "Sanction", 
            "Customer", "Business Relationship", "Payment Method", "Process", 
            "Reporting Mechanism", "Audit Requirement", "Directive", "Date"
        ],
        "AMLD6": [
            "Person", "Organization", "Terrorist Activity", "Financial Institution", 
            "Obligation", "Corporate Structure", "Legal Arrangement", "Beneficial Owner", 
            "Virtual Currency", "Custodian Wallet Provider", "Transaction", "Regime", 
            "Criminal Organization", "Intelligence Unit", "Authority", "Sanction", 
            "Customer", "Business Relationship", "Payment Method", "Process", 
            "Reporting Mechanism", "Audit Requirement", "Legal Document", "Risk Assessment", 
            "Ownership Structure", "Asset", "Financial Control", "Penalty", "Directive"
        ],
        "EU Sanctions": [
            "Person", "Organization", "Terrorist Activity", "Financial Institution", 
            "Obligation", "Authority", "Asset", "Customs", "Criminal Investigation Unit", 
            "Penalty", "Government Agency", "Export Control", "Legal Arrangement", 
            "Economic Resource", "Embargo", "Financial Service", "Government Bond", 
            "Country", "Process", "Action", "Sanction", "Government Agency", "Email","Date", "Phone","Address"
        ],
        "FATF Rec": [
            "Person", "Organization", "Financial Institution", "Obligation", "Terrorist Financing", 
            "Competent Authority", "Law Enforcement Authority", "Supervisory Authority", 
            "Asset", "Criminal Organization", "Penalty", "Government Agency", "Beneficial Owner", 
            "Legal Arrangement", "Regime", "Money Laundering Offense", "Suspicious Transaction", 
            "Transaction", "Financial Service", "Business Relationship", "Process", 
            "Audit Requirement", "Country", "Risk Assessment", "Politically Exposed Person", 
            "Designated Non-Financial Business and Professions", "Date"
        ],
        "MICA": [
            "Individual", "Organization", "Financial Institution", "Obligation", "Custodian", 
            "Service Provider", "Virtual Currency", "Beneficial Owner", "Token", "Asset", 
            "Transaction", "Authority", "Sanction", "White Paper", "Audit Requirement", 
            "Business Relationship", "Payment Method", "Process", "Reporting Mechanism", 
            "Legal Document", "Risk Assessment", "Ownership Structure", "Financial Control", 
            "Regime", "Compliance", "Penalty"
        ]
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def generate_schema_async(client, workspace_id: str, schema_name: str, questions: List[str]) -> Dict:
    """Generate a schema for the workspace."""
    try:
        # First check if schema exists
        existing_schema = await schema_exists_async(client, workspace_id, schema_name)
        if existing_schema:
            print(f"Using existing schema for {schema_name}")
            return existing_schema

        # Get allowed nodes for this schema
        allowed_nodes = ALLOWED_NODES_CONFIG.get(schema_name, [])
        if not allowed_nodes:
            print(f"Warning: No predefined nodes found for schema {schema_name}")

        # Convert questions to proper triple format
        triples = [
            {
                "subject": "FATF Sanctions",
                "predicate": "has_entity",
                "object": "Entity",
                "question": q
            } for q in questions
        ]

        # Create graph with schema using the correct endpoint structure
        graph_response = await client._make_request(
            'POST', 
            '/graphs/from_triples',
            json={
                "workspace_id": workspace_id,
                "name": schema_name,
                "type": "schema",
                "triples": triples,
                "allowed_nodes": allowed_nodes,
                "status": "active"
            }
        )
        
        print(f"Graph creation response: {graph_response}")
        
        graph_id = graph_response.get('id') or graph_response.get('_id')
        if not graph_id:
            raise ValueError("No graph ID in response")
            
        # Get the created graph's schema
        schema = await client._make_request(
            'GET',
            f'/graphs/{graph_id}/schema'
        )
        
        print(f"Schema details: {schema}")
        return schema
        
    except Exception as e:
        print(f"[ERROR] Failed to generate schema: {str(e)}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def schema_exists_async(client, workspace_id: str, schema_name: str) -> Optional[Dict]:
    """Check if schema exists."""
    try:
        graphs = await client._make_request('GET', '/graphs')

        print(f"Available graphs: {graphs}")

        for graph in graphs.get('graphs', []):
            if graph.get('name') == schema_name and graph.get('workspace', {}).get('_id') == workspace_id:
                graph_id = graph.get('_id')
                schema = await client._make_request('GET', f'/graphs/{graph_id}/schema')
                print(f"Found existing schema: {schema}")
                return schema

        return None

    except Exception as e:
        print(f"[ERROR] Failed to check schema existence: {str(e)}")
        raise


def get_allowed_nodes(schema_name: str) -> List[str]:
    """Get allowed nodes for the schema."""
    nodes = ALLOWED_NODES_CONFIG.get(schema_name, [])
    if not nodes:
        logging.warning(f"No predefined nodes found for schema {schema_name}. Using default fallback.")
        return ["Generic Node"]
    return nodes



