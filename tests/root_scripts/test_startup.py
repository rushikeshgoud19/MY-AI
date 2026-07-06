import sys
import logging
logging.basicConfig(level=logging.INFO)

try:
    print("1. Testing TokenJuice...")
    from server.tokenjuice import token_juice
    compressed = token_juice.compress("<p>Test</p> http://example.com/verylongpath?q=12345678901234567890123")
    print(f"TokenJuice output: {compressed}")

    print("2. Testing ContextManager...")
    from server.context_manager import ContextManager
    cfg = {"ai_model": "gemini"}
    cm = ContextManager(cfg)
    # create a mock chronicle
    mock_chron = [
        {"role": "user", "parts": [{"text": "Hello"}]},
        {"role": "model", "parts": [{"text": "Hi"}]},
    ]
    prep, was_comp = cm.prepare_context(mock_chron)
    print(f"ContextManager success. Was compressed: {was_comp}")

    print("3. Testing MemoryTreeDB...")
    from server.memory_tree import memory_tree_db
    memory_tree_db.insert_chunk("test_chunk_1", "system", "This is a test chunk", 5, {"test": True})
    print("MemoryTreeDB inserted chunk successfully.")

    print("4. Testing VaultSync initialization...")
    config = {"ai_model": "gemini", "vault_path": "./MizuneVault"}
    from server.vault_sync import init_vault_sync
    init_vault_sync(config)
    print("VaultSync initialized.")

    print("5. Testing Subconscious Engine...")
    from server.subconscious import SubconsciousEngine
    import threading
    lock = threading.Lock()
    engine = SubconsciousEngine(config, lambda **kwargs: None, lock)
    print("SubconsciousEngine initialized.")

    print("6. Testing Auto-Fetch...")
    from server.auto_fetch import init_auto_fetch
    init_auto_fetch(config)
    print("AutoFetch initialized.")

    print("7. Testing Model Router...")
    from server.model_router import get_model_router
    router = get_model_router(config)
    route = router.route("Hello", [])
    print(f"Model Router default route: {route}")

    print("8. Testing Security Scanner...")
    from server.security import SecurityScanner, validate_api_keys
    safe, msg = SecurityScanner.scan_code("import os; os.remove('test.txt')")
    print(f"Security Scanner block working: {not safe} (Msg: {msg})")
    validate_api_keys(config)

    print("\n[SUCCESS] All core systems loaded and initialized successfully!")
    sys.exit(0)
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"\n[ERROR] ERROR: {e}")
    sys.exit(1)
