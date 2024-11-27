from whyhow import WhyHow, Triple, Node, Chunk, Relation

# Configure WhyHow client
client = WhyHow(api_key='ArAE2s0n5vDYfTaEglPCe5vU3xh0ElzScDRUep97', base_url="http://127.0.0.1:8000")

# Create workspace
workspace = client.workspaces.get(workspace_id="6745d1a6aec0bf03b31c4eae")
# Create chunk(s)
# chunk = client.chunks.create(
#     workspace_id=workspace.workspace_id,
#     chunks=[Chunk(
#         content="preneur and visionary, Sam Altman serves as the CEO of OpenAI, leading advancements in artifici"
#     )]
# )

# # Create triple(s)
# triples = [
#     Triple(
#         head=Node(
#             name="Sam Altman",
#             label="Person",
#             properties={"title": "CEO"}
#         ),
#         relation=Relation(
#             name="runs",
#         ),
#         tail=Node(
#             name="OpenAI",
#             label="Business",
#             properties={"market cap": "$157 Billion"}
#         ),
#         chunk_ids=[c.chunk_id for c in chunk]
#     )
# ]

# # Create graph
# graph = client.graphs.create_graph_from_triples(
#     name="Demo Graph",
#     workspace_id=workspace.workspace_id,
#     triples=triples
# )

graph = client.graphs.get(graph_id="6745d1a9aec0bf03b31c4eb0")

# Query graph
query = client.graphs.query_unstructured(
    graph_id=graph.graph_id,
    query="Who runs OpenAI?"
)
print(query)