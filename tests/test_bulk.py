from app.services.batching import chunked

def test_bulk_sizes():
    for n in (1, 10, 100, 1000):
        items = list(range(n))
        batches = list(chunked(items, 100))
        assert sum(map(len, batches)) == n
        assert all(1 <= len(b) <= 100 for b in batches)
