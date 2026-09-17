from app.services.api_keys import PREFIX, ApiKeysStore, generate_key, hash_key


def test_generate_key_format() -> None:
    key = generate_key()
    assert key.startswith(PREFIX)
    assert len(key) == len(PREFIX) + 32


def test_hash_key_is_deterministic() -> None:
    assert hash_key("secret") == hash_key("secret")
    assert hash_key("secret") != hash_key("other")


def test_create_and_find(keys_store: ApiKeysStore) -> None:
    key = keys_store.create("test-key")
    assert key.startswith(PREFIX)

    found = keys_store.find(key)
    assert found is not None
    assert found["name"] == "test-key"


def test_find_unknown_key_returns_none(keys_store: ApiKeysStore) -> None:
    assert keys_store.find("ak_live_" + "f" * 32) is None


def test_revoked_key_is_not_found(keys_store: ApiKeysStore) -> None:
    key = keys_store.create("revoke-me")
    key_id = keys_store.find(key)["id"]
    keys_store.revoke(key_id)
    assert keys_store.find(key) is None


def test_list_all_exposes_fingerprint(keys_store: ApiKeysStore) -> None:
    keys_store.create("one")
    keys_store.create("two")

    rows = keys_store.list_all()
    assert len(rows) == 2
    assert rows[0]["revoked"] == 0
    assert "_" in rows[0]["fingerprint"] or len(rows[0]["fingerprint"]) == 8