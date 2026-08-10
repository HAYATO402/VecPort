import time


def wait_for_search(
    db,
    collection,
    vector,
    *,
    top_k=10,
    filters=None,
    expected_count=1,
    timeout=10.0,
    interval=0.5,
):

    deadline = time.time() + timeout
    last_results = []

    while time.time() < deadline:

        last_results = db.search(
            collection,
            vector,
            top_k=top_k,
            filters=filters,
        )

        if len(last_results) >= expected_count:
            return last_results

        time.sleep(interval)

    return last_results