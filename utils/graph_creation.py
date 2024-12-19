# Async version to create graph
async def create_graph_async(client, workspace_id, schema_id, graph_name, document_id):
    graph = await client.graphs.create(
        workspace_id=workspace_id,
        schema_id=schema_id,
        name=graph_name,
        document_ids=[document_id],  # Specify the doc to use
    )
    print(f"Graph '{graph_name}' created successfully.")
    return graph

# Async version to export graph as Cypher
async def export_graph_cypher_async(client, graph_id, output_path):
    cypher = await client.graphs.export_cypher(graph_id=graph_id)
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(cypher)
    print(f"The graph has been exported as '{output_path}'.")