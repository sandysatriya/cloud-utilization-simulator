from types import SimpleNamespace

import pytest

from cloudsim.db.migrate import migrate
from cloudsim.services import settings_service
from cloudsim.services.analysis_service import analyze
from tests.helpers import (
    END,
    START,
    add_server,
    add_time_batch,
    series,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "cloudsim_test.db"
    migrate(path)
    settings_service.update_thresholds(80, 50, 1, "UTC", db_path=path)
    return path


@pytest.fixture
def dataset(db_path):
    add_server(db_path, "SRV-A", name="App A", workload="web", vcpu=4, ram_gib=8)
    add_server(db_path, "SRV-B", name="DB B", workload="database", vcpu=8, ram_gib=16)
    cpu_batch, cpu_preview = add_time_batch(
        db_path,
        "cpu",
        {
            "SRV-A": series(START, [10, 20, 30, 40]),
            "SRV-B": series(START, [20, 30, 40, 50]),
        },
    )
    memory_batch, memory_preview = add_time_batch(
        db_path,
        "memory",
        {
            "SRV-A": series(START, [80, 85, 90, 95]),
            "SRV-B": series(START, [70, 75, 80, 85]),
        },
    )
    analysis = analyze(
        START, END, [cpu_batch], [memory_batch], "UTC", db_path=db_path
    )
    return SimpleNamespace(
        db_path=db_path,
        analysis=analysis,
        cpu_batch=cpu_batch,
        memory_batch=memory_batch,
        cpu_preview=cpu_preview,
        memory_preview=memory_preview,
    )
