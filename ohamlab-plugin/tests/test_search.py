from storage.bucket import BucketStore


def test_save_and_retrieve_document(tmp_path):
    db = BucketStore(str(tmp_path))
    saved = db.save_document({
        "url": "https://example.com/article",
        "title": "Example article",
        "text": "A little bit of useful content.",
        "snippet": "A little bit of useful content.",
        "fetched_at": "2026-01-01T00:00:00+00:00",
    })
    assert saved["document_id"]
    assert db.get_document(saved["document_id"])["text"] == "A little bit of useful content."
    assert db.list_documents("example")[0]["title"] == "Example article"


def test_task_history(tmp_path):
    db = BucketStore(str(tmp_path))
    db.log_task("test_task", {"query": "demo"}, {"ok": True})
    history = db.task_history(1)
    assert history[0]["task_type"] == "test_task"
