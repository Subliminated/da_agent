from app.core import config


def test_llm_model_has_default() -> None:
    assert config.LLM_MODEL


def test_storage_root_is_under_backend_root() -> None:
    assert config.STORAGE_ROOT.parent == config.BACKEND_ROOT
