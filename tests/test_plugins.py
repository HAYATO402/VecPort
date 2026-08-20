from __future__ import annotations

from typing import Any

import pytest

from vecport import (
    connect,
    connect_url,
    register_driver,
)
from vecport.core.errors import (
    DriverPluginConflictError,
    DriverPluginLoadError,
)
from vecport.core.plugins import (
    DRIVER_ENTRY_POINT_GROUP,
    discover_driver_plugins,
    load_driver_plugin,
)


class DummyDriver:
    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        self.options = kwargs


class FakeEntryPoint:
    def __init__(
        self,
        *,
        name: str,
        value: str,
        loaded_object: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.name = name
        self.value = value
        self._loaded_object = loaded_object
        self._error = error

    def load(self) -> object | None:
        if self._error is not None:
            raise self._error

        return self._loaded_object


def test_discover_driver_plugins(
    monkeypatch,
) -> None:
    entry_points = (
        FakeEntryPoint(
            name="z-driver",
            value="plugin_z:Driver",
        ),
        FakeEntryPoint(
            name="a-driver",
            value="plugin_a:Driver",
        ),
    )

    def fake_entry_points(**kwargs):
        assert (
            kwargs["group"]
            == DRIVER_ENTRY_POINT_GROUP
        )
        return entry_points

    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        fake_entry_points,
    )

    plugins = discover_driver_plugins()

    assert [
        plugin.name
        for plugin in plugins
    ] == [
        "a-driver",
        "z-driver",
    ]


def test_connect_auto_loads_plugin(
    monkeypatch,
) -> None:
    entry_point = FakeEntryPoint(
        name="external-auto-test",
        value="example_driver:ExampleDriver",
        loaded_object=DummyDriver,
    )

    def fake_entry_points(**kwargs):
        if (
            kwargs.get("group")
            == DRIVER_ENTRY_POINT_GROUP
            and kwargs.get("name")
            == "external-auto-test"
        ):
            return (entry_point,)

        return ()

    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        fake_entry_points,
    )

    db = connect(
        "external-auto-test",
        example_option=123,
    )

    assert isinstance(db, DummyDriver)
    assert db.options["example_option"] == 123


def test_connect_url_auto_loads_plugin(
    monkeypatch,
) -> None:
    entry_point = FakeEntryPoint(
        name="external-url-test",
        value="example_driver:ExampleDriver",
        loaded_object=DummyDriver,
    )

    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        lambda **kwargs: (
            (entry_point,)
            if kwargs.get("name")
            == "external-url-test"
            else ()
        ),
    )

    db = connect_url(
        "vecport://external-url-test"
        "?example_option=hello"
    )

    assert isinstance(db, DummyDriver)
    assert db.options["example_option"] == "hello"


def test_built_in_driver_does_not_load_plugins(
    monkeypatch,
) -> None:
    def unexpected_discovery(**kwargs):
        raise AssertionError(
            "Built-in driver triggered plugin discovery"
        )

    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        unexpected_discovery,
    )

    db = connect("qdrant")

    assert type(db).__name__ == "QdrantDriver"


def test_manually_registered_driver_has_priority(
    monkeypatch,
) -> None:
    name = "manual-priority-test"
    register_driver(
        name,
        DummyDriver,
        replace=True,
    )

    def unexpected_discovery(**kwargs):
        raise AssertionError(
            "Manual driver triggered plugin discovery"
        )

    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        unexpected_discovery,
    )

    db = connect(name)

    assert isinstance(db, DummyDriver)


def test_missing_plugin_returns_false(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        lambda **kwargs: (),
    )

    assert not load_driver_plugin(
        "missing-external-driver"
    )


def test_plugin_load_failure(
    monkeypatch,
) -> None:
    entry_point = FakeEntryPoint(
        name="broken-external-test",
        value="broken_driver:BrokenDriver",
        error=RuntimeError(
            "plugin exploded"
        ),
    )
    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        lambda **kwargs: (entry_point,),
    )

    with pytest.raises(
        DriverPluginLoadError,
        match="broken-external-test",
    ) as captured:
        load_driver_plugin(
            "broken-external-test"
        )

    assert isinstance(
        captured.value.__cause__,
        RuntimeError,
    )


def test_non_callable_plugin_fails(
    monkeypatch,
) -> None:
    entry_point = FakeEntryPoint(
        name="non-callable-test",
        value="broken_driver:not_callable",
        loaded_object=object(),
    )
    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        lambda **kwargs: (entry_point,),
    )

    with pytest.raises(
        DriverPluginLoadError,
        match="not callable",
    ):
        load_driver_plugin(
            "non-callable-test"
        )


def test_duplicate_plugin_names_fail(
    monkeypatch,
) -> None:
    first = FakeEntryPoint(
        name="duplicate-test",
        value="plugin_a:Driver",
        loaded_object=DummyDriver,
    )
    second = FakeEntryPoint(
        name="duplicate-test",
        value="plugin_b:Driver",
        loaded_object=DummyDriver,
    )
    monkeypatch.setattr(
        "vecport.core.plugins.entry_points",
        lambda **kwargs: (
            first,
            second,
        ),
    )

    with pytest.raises(
        DriverPluginConflictError,
        match="duplicate-test",
    ):
        load_driver_plugin(
            "duplicate-test"
        )
