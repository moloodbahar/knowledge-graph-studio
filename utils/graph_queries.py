# graph_queries.py

# Sync version to query_graph
def query_graph(client, graph_id, question):
    query = client.graphs.query_unstructured(
        graph_id=graph_id,
        query=question,
        include_chunks=True
    )
    print("Query answer:", query.answer)
    return query

# Asyc version to query graph
async def query_graph_async(client, graph_id, question):
    query = await client.graphs.query_unstructured(
        graph_id=graph_id,
        query=question,
        include_chunks=True
    )
    print("Query answer:", query.answer)
    return query

# Sync version to get all triples
def get_all_triples(client, graph_id):
    print("Retrieves all the triplets in the graph:")
    all_triples = list(client.graphs.get_all_triples(graph_id=graph_id))

    for triple in all_triples:
        print(f"Head: {triple.head}, Relation: {triple.relation}, Tail: {triple.tail}")
    return all_triples

# Async version to get all triples
async def get_all_triples_async(client, graph_id):
    """Retrieves all the triplets in the graph asynchronously."""
    print("[INFO] Retrieving all triplets from the graph...")
    all_triples = []
    
    try:
        async for triple in client.graphs.get_all_triples(graph_id=graph_id):
            if triple:  # Check if triple is not None
                all_triples.append(triple)
                # Optional: print for debugging
                # print(f"Head: {triple.head}, Relation: {triple.relation}, Tail: {triple.tail}")
    except Exception as e:
        print(f"[ERROR] Error retrieving triples: {str(e)}")
        return None
        
    print(f"[INFO] Retrieved {len(all_triples)} triples")
    return all_triples
