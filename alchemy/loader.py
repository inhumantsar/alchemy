from enum import Enum, auto
import json
import os
import pickle
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from logging import getLogger

from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from llama_index import Document, GPTListIndex, GPTSimpleVectorIndex, LLMPredictor, PromptHelper, ServiceContext, download_loader
from llama_index.indices.knowledge_graph import GPTKnowledgeGraphIndex

download_loader("GithubRepositoryReader")
from llama_index.readers.llamahub_modules.github_repo import GithubClient, GithubRepositoryReader

DEFAULT_DIRECTORY_FILTERS = ([".git", ".yarn", "node_modules"], GithubRepositoryReader.FilterType.EXCLUDE)
DEFAULT_FILE_EXT_FILTERS = ([".zip"], GithubRepositoryReader.FilterType.EXCLUDE)

load_dotenv()

assert os.environ["GITHUB_TOKEN"] and os.environ["OPENAI_API_KEY"]

logger = getLogger(__name__)


class IndexType(Enum):
    SIMPLE_VECTOR = auto()
    KNOWLEDGE_GRAPH = auto()


@dataclass
class ModelOptions:
    """
    See the upstream class for documentation on these options.

    https://github.com/hwchase17/langchain/blob/master/langchain/chat_models/openai.py#L94-L127
    """

    cache: bool | None = None
    verbose: bool = False
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    n: int | None = None
    best_of: int | None = None
    model_kwargs: Dict[str, Any] | None = None
    openai_api_key: str | None = None
    batch_size: int | None = None
    request_timeout: float | Tuple[float, float] | None = None
    logit_bias: Dict[str, float] | None = None
    max_retries: int | None = None
    streaming: bool = False


@dataclass
class RepoOptions:
    owner: str
    repo: str
    branch: str = "main"
    commit_sha: str | None = None
    filter_directories: Tuple[List[str], GithubRepositoryReader.FilterType] | None = DEFAULT_DIRECTORY_FILTERS
    filter_file_extensions: Tuple[List[str], GithubRepositoryReader.FilterType] | None = DEFAULT_FILE_EXT_FILTERS
    verbose: bool = True
    concurrent_requests: int = 10


@dataclass
class CacheOptions:
    path: str | Path = "~/.alchemy"
    force_update: bool = False
    max_age: int = 60


def _get_cache_name(repo_opts: RepoOptions) -> str:
    name = f"{repo_opts.owner}-{repo_opts.repo}"
    name += f"-{repo_opts.commit_sha if repo_opts.commit_sha else repo_opts.branch}"
    return name


def _get_cache_path(repo_opts: RepoOptions, cache_opts: CacheOptions, ext: str | None = None) -> Path:
    cache_path = Path(cache_opts.path).expanduser()
    name = _get_cache_name(repo_opts)
    name += f".{ext}" if ext else ""
    cache_path = cache_path / name
    return cache_path


def _cache_is_usable(path: Path, cache_opts: CacheOptions) -> bool:
    return (time.time() - path.stat().st_mtime) < cache_opts.max_age or not cache_opts.force_update


def _get_cache(ext: str, repo_opts: RepoOptions, cache_opts: CacheOptions) -> Any:
    cache_path = _get_cache_path(repo_opts, cache_opts, ext)
    if cache_path.exists() and _cache_is_usable(cache_path, cache_opts):
        with open(cache_path, "rb") as f:
            return f.read()


def _put_cache(data: Any, ext: str, repo_opts: RepoOptions, cache_opts: CacheOptions):
    cache_path = _get_cache_path(repo_opts, cache_opts, ext)
    os.makedirs(cache_path.parent, exist_ok=True)

    mode = "wb" if isinstance(data, bytes) else "w"
    with open(cache_path, mode) as f:
        f.write(data)


def _load_documents(repo_opts: RepoOptions, cache_opts: CacheOptions) -> Sequence[Document]:
    EXT = "docs.pkl"
    if cache := _get_cache(EXT, repo_opts, cache_opts):
        return pickle.loads(cache)

    # not all repo options are valid for the github reader
    github_opts = asdict(repo_opts)
    github_opts.pop("commit_sha")
    github_opts.pop("branch")

    loader = GithubRepositoryReader(GithubClient(os.environ["GITHUB_TOKEN"]), **github_opts)
    docs = loader.load_data(repo_opts.commit_sha, repo_opts.branch)
    _put_cache(pickle.dumps(docs), EXT, repo_opts, cache_opts)

    return docs


def create_simple_vector_index(
    repo_opts: RepoOptions,
    cache_opts: CacheOptions,
    model_opts: ModelOptions,
) -> GPTSimpleVectorIndex:
    logger.info("loading simple vector index...")
    logger.info(f"repo_opts: {asdict(repo_opts)}")
    logger.info(f"cache_opts: {asdict(cache_opts)}")
    logger.info(f"model_opts: {asdict(model_opts)}")

    EXT = "sv.idx.json"
    index: GPTSimpleVectorIndex

    openai_opts = {k: v for k, v in asdict(model_opts).items() if v}
    context = ServiceContext.from_defaults(llm_predictor=LLMPredictor(llm=ChatOpenAI(**openai_opts)))
    # prompt_helper = PromptHelper(max_input_size=8164, num_output=1024, max_chunk_overlap=20)

    if cache := _get_cache(EXT, repo_opts, cache_opts):
        index = GPTSimpleVectorIndex.load_from_string(cache)  # type: ignore
    else:
        index = GPTSimpleVectorIndex.from_documents(_load_documents(repo_opts, cache_opts), service_context=context)  # type: ignore
        _put_cache(json.dumps(index.save_to_dict()), EXT, repo_opts, cache_opts)

    return index


def create_list_index(
    repo_opts: RepoOptions,
    cache_opts: CacheOptions,
    model_opts: ModelOptions,
) -> GPTListIndex:
    logger.info("loading simple vector index...")
    logger.info(f"repo_opts: {asdict(repo_opts)}")
    logger.info(f"cache_opts: {asdict(cache_opts)}")
    logger.info(f"model_opts: {asdict(model_opts)}")

    EXT = "l.idx.json"
    index: GPTListIndex

    openai_opts = {k: v for k, v in asdict(model_opts).items() if v}
    context = ServiceContext.from_defaults(llm_predictor=LLMPredictor(llm=ChatOpenAI(**openai_opts)))
    # prompt_helper = PromptHelper(max_input_size=8164, num_output=1024, max_chunk_overlap=20)

    if 0 == 1:  # cache := _get_cache(EXT, repo_opts, cache_opts):
        index = GPTListIndex.load_from_string(cache)  # type: ignore
    else:
        index = GPTListIndex.from_documents(_load_documents(repo_opts, cache_opts), service_context=context)  # type: ignore
        _put_cache(json.dumps(index.save_to_dict()), EXT, repo_opts, cache_opts)

    return index


def create_knowledge_graph_index(
    repo_opts: RepoOptions,
    cache_opts: CacheOptions,
    model_opts: ModelOptions,
) -> GPTKnowledgeGraphIndex:
    cache_opts = cache_opts or CacheOptions()
    model_opts = model_opts or ModelOptions()
    logger.info("loading simple vector index...")
    logger.info(f"repo_opts: {asdict(repo_opts)}")
    logger.info(f"cache_opts: {asdict(cache_opts)}")
    logger.info(f"model_opts: {asdict(model_opts)}")

    EXT = "kg.idx.json"
    index: GPTKnowledgeGraphIndex

    openai_opts = {k: v for k, v in asdict(model_opts).items() if v}
    context = ServiceContext.from_defaults(llm_predictor=LLMPredictor(llm=ChatOpenAI(**openai_opts)))
    # prompt_helper = PromptHelper(max_input_size=8164, num_output=1024, max_chunk_overlap=20)

    if 0 == 1:  # cache := _get_cache(EXT, repo_opts, cache_opts):
        index = GPTKnowledgeGraphIndex.load_from_string(cache)  # type: ignore
    else:
        index = GPTKnowledgeGraphIndex.from_documents(_load_documents(repo_opts, cache_opts), service_context=context)  # type: ignore
        _put_cache(json.dumps(index.save_to_dict()), EXT, repo_opts, cache_opts)

    return index
