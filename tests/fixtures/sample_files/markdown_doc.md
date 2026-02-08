# RAG System Documentation

## What is RAG?

RAG (Retrieval-Augmented Generation) combines information retrieval with large language model generation. The system retrieves relevant context from a knowledge base and uses it to generate accurate, grounded responses.

## Key Components

### Vector Store
A vector store maintains embeddings of text chunks. When a query comes in, the system:
1. Converts the query to an embedding vector
2. Performs similarity search to find relevant chunks
3. Returns the top-k most similar results

### LLM Synthesis
The retrieved chunks are passed to a local LLM along with the user's question. The LLM synthesizes a coherent answer based on the provided context.

## Performance Considerations

Embedding generation should be batched for efficiency. A typical batch size of 32-64 chunks provides good throughput without excessive memory usage.
