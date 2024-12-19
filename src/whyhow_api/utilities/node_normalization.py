"""Node name normalization utilities."""

import re
from typing import Optional, Tuple
import inflect
from thefuzz import fuzz
from bson import ObjectId

# Initialize the inflect engine for handling plurals
p = inflect.engine()

def normalize_node_name(name: str) -> str:
    """Normalize node name by standardizing format and handling plurals."""
    # Convert to lowercase for consistent comparison
    name = name.lower()
    
    # Remove special characters and replace with spaces
    name = re.sub(r'[_-]', ' ', name)
    
    # Remove extra whitespace
    name = ' '.join(name.split())
    
    # Try to get singular form if it's plural
    if p.singular_noun(name):
        name = p.singular_noun(name)
    
    # Capitalize each word
    name = name.title()
    
    return name

def find_similar_node(
    name: str, 
    node_type: str,
    existing_nodes: list[dict], 
    similarity_threshold: int = 85
) -> Optional[Tuple[str, ObjectId]]:
    """
    Find if a similar node name already exists with the same type.
    
    Parameters
    ----------
    name : str
        The node name to check
    node_type : str
        The type/label of the node
    existing_nodes : list[dict]
        List of existing nodes
    similarity_threshold : int
        Minimum similarity score to consider nodes as similar
        
    Returns
    -------
    Optional[Tuple[str, ObjectId]]
        Returns tuple of (existing_name, node_id) if found, None otherwise
    """
    normalized_name = normalize_node_name(name)
    
    for node in existing_nodes:
        # Only consider nodes of the same type
        if node['type'] != node_type:
            continue
            
        existing_name = node['name']
        # Calculate similarity ratio
        similarity = fuzz.ratio(normalized_name.lower(), existing_name.lower())
        if similarity >= similarity_threshold:
            return (existing_name, node['_id'])
            
    return None 