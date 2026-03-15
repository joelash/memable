# Performance Tests

These tests measure throughput, storage growth, and API costs for memento-ai.

## Running Performance Tests

```bash
# Requires OPENAI_API_KEY for embedding operations
export OPENAI_API_KEY="sk-..."

# Run all performance tests with verbose output
pytest tests/performance/ -v -s

# Run specific test file
pytest tests/performance/test_throughput.py -v -s

# Skip slow scaling tests
pytest tests/performance/ -v -s -m "not slow"
```

## Test Files

### `test_throughput.py`
Measures operations per second for core operations:
- `add()` throughput
- `search()` throughput at various DB sizes
- `get()` throughput (should be fast, no embedding needed)
- `list_all()` throughput
- Scaling behavior as DB grows

### `test_storage_growth.py`
Measures storage requirements:
- Bytes per memory (SQLite and DuckDB)
- Version chain storage overhead
- Conversation simulation (realistic extraction patterns)
- Projections for various user types (light to power user)

### `test_embedding_costs.py`
Tracks API usage and estimates costs:
- Embedding calls per operation (add, search, get)
- Cost estimation for various usage patterns
- Extraction (LLM) cost estimation
- Total cost estimation for typical usage

## Interpreting Results

### Throughput Baselines
- `add()`: Should be < 2 seconds (dominated by embedding API call)
- `search()`: Should be < 1 second for small DBs (< 1000 memories)
- `get()`: Should be < 50ms (no embedding needed)
- `list_all()`: Should scale linearly with DB size

### Storage Baselines
- Bytes per memory: ~6-10 KB (mostly embedding at 1536 floats × 4 bytes)
- 1,000 memories ≈ 6-10 MB
- 10,000 memories ≈ 60-100 MB
- 100,000 memories ≈ 600 MB - 1 GB

### Cost Baselines (text-embedding-3-small)
- Embedding: $0.02 per 1M tokens
- Typical add: ~20 tokens → $0.0000004
- Typical search: ~10 tokens → $0.0000002
- 10,000 operations/day ≈ $0.006/day ≈ $0.18/month

### Cost Baselines (gpt-4.1-mini extraction)
- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens
- 100 extractions/day ≈ $0.01/day ≈ $0.30/month

## Adding New Benchmarks

When adding new performance tests:
1. Use `pytest.mark.skipif` for tests requiring API keys
2. Use `pytest.mark.slow` for tests that take > 30 seconds
3. Print results with the `📊` prefix for easy scanning
4. Include assertions with reasonable baselines
5. Document expected ranges in this README
