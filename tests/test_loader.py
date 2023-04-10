import pytest

from alchemy.loader import RepoOptions, CacheOptions, ModelOptions, create_simple_vector_index, _get_cache_path
from llama_index import GPTSimpleVectorIndex, ServiceContext
from langchain.chat_models import ChatOpenAI


@pytest.fixture
def repo_opts():
    return RepoOptions(owner="inhumantsar", repo="tacostats")


@pytest.fixture
def cache_opts():
    return CacheOptions(force_update=True)  # To force a cache update for testing


@pytest.fixture
def model_opts():
    return ChatOpenAI()  # type: ignore


def test_load_simple_index_returns_correct_type(repo_opts, cache_opts, model_opts):
    index = create_simple_vector_index(repo_opts, cache_opts, model_opts)
    assert isinstance(index, GPTSimpleVectorIndex)


def test_cache_created(repo_opts, cache_opts, model_opts):
    create_simple_vector_index(repo_opts, cache_opts, model_opts)
    cache_path = _get_cache_path(repo_opts, cache_opts, "idx.json")
    assert cache_path.exists()
