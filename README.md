# MAIA (Multi-Agent Intelligent Assistant)

MAIA is an enterprise-grade AI system for domain-specific query handling, retrieval-augmented generation (RAG), and continuous learning. It leverages a base large language model fine-tuned with LoRA adapters for specialized experts across sectors.

## Architecture

MAIA uses a microservices architecture with the following components:

- **LoRAX**: Inference server for the base LLM with dynamic adapter loading
- **Qdrant**: Vector database for document embeddings and retrieval
- **Redis**: Task queue for asynchronous processing
- **MAIA Controller**: Main FastAPI application handling queries, routing, and orchestration
- **OCR Service**: Image text extraction using PaddleOCR
- **Embeddings Service**: Embedding generation and reranking using SentenceTransformers
- **Trainer**: Continuous learning worker for adapter updates

## Features

- **Semantic Routing**: Intelligent query routing to domain-specific experts
- **Hybrid RAG**: Combination of vector search, BM25, and cross-encoder reranking
- **Vision Support**: OCR integration for image-based queries
- **Continuous Learning**: Automated adapter retraining on user feedback
- **Response Auditing**: Self-correction using general knowledge adapter
- **GPU Optimization**: Efficient VRAM management across services

## Quick Start

### Prerequisites

- Docker and Docker Compose
- NVIDIA GPU (optional, for GPU acceleration)
- OpenAI API key (for data augmentation)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd maia
   ```

2. Create environment file:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configurations
   ```

3. Build and start services:
   ```bash
   docker compose up --build
   ```

4. The API will be available at `http://localhost:8000`

### Configuration

Key environment variables:

- `MAIA_API_KEY`: API key for authentication
- `LORAX_URL`: LoRAX service URL
- `QDRANT_URL`: Qdrant database URL
- `OPENAI_API_KEY`: OpenAI API key for training data generation

## API Usage

### Text Query

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -H "x-maia-key: your-api-key" \
  -d '{"query": "What are the legal implications of factory fires?"}'
```

### Image Query

```bash
curl -X POST "http://localhost:8000/query_image" \
  -H "x-maia-key: your-api-key" \
  -F "file=@document.jpg"
```

### Thumbs Up Feedback

```bash
curl -X POST "http://localhost:8000/thumbs_up" \
  -H "Content-Type: application/json" \
  -H "x-maia-key: your-api-key" \
  -d '{
    "query": "Legal question",
    "response": "AI response",
    "context": "Retrieved context",
    "sector": "professional_services"
  }'
```

## Development

### Running Tests

```bash
pytest
```

### Code Quality

```bash
pre-commit run --all-files
```

### Training Adapters

```bash
python train_expert.py --adapter law --dataset path/to/dataset
```

## Security

- API key authentication
- Prompt injection detection via LLM-Guard
- Input sanitization and validation
- Secure dependency management

## Monitoring

- Structured logging with configurable levels
- Health checks for all services
- Performance metrics via API endpoints

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run CI checks
5. Submit a pull request

## License

[License information]

## Support

For issues and questions, please open a GitHub issue or contact the development team.