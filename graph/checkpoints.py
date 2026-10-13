"""명시적으로 등록한 State 타입만 복원하는 SQLite 체크포인터이다."""

from contextlib import contextmanager
import inspect
from pathlib import Path
import sqlite3

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from schemas import analysis, evaluation, evidence, state, supervisor


@contextmanager
def sqlite_checkpointer(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    allowed = []
    for module in (analysis, evaluation, evidence, state, supervisor):
        allowed.extend((cls.__module__, cls.__name__) for _, cls in inspect.getmembers(module, inspect.isclass)
                       if cls.__module__ == module.__name__)
    serializer = JsonPlusSerializer(allowed_msgpack_modules=allowed)
    connection = sqlite3.connect(path, check_same_thread=False)
    try:
        yield SqliteSaver(connection, serde=serializer)
    finally:
        connection.close()
