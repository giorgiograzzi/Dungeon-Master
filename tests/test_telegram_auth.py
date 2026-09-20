from __future__ import annotations

import time

import pytest

from app.security.telegram_auth import InitDataError, validate_init_data
from tests._helpers import BOT_TOKEN, build_init_data


def test_validate_init_data_ok():
    fields = {
        "auth_date": str(int(time.time())),
        "user": '{"id": 42, "first_name": "Prova", "username": "prova"}',
        "query_id": "abc123",
    }
    data = validate_init_data(build_init_data(fields), BOT_TOKEN)
    assert data["user"]["id"] == 42
    assert data["user"]["first_name"] == "Prova"


def test_validate_init_data_bad_hash():
    fields = {"auth_date": str(int(time.time())), "user": '{"id": 42}'}
    tampered = build_init_data(fields) + "0"
    with pytest.raises(InitDataError):
        validate_init_data(tampered, BOT_TOKEN)


def test_validate_init_data_wrong_token():
    fields = {"auth_date": str(int(time.time())), "user": '{"id": 42}'}
    init_data = build_init_data(fields, bot_token="999:OTHER-TOKEN")
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN)


def test_validate_init_data_expired():
    old_auth_date = int(time.time()) - 100_000
    fields = {"auth_date": str(old_auth_date), "user": '{"id": 42}'}
    init_data = build_init_data(fields)
    with pytest.raises(InitDataError):
        validate_init_data(init_data, BOT_TOKEN, max_age=86400)


def test_validate_init_data_no_max_age_skips_expiry_check():
    old_auth_date = int(time.time()) - 100_000
    fields = {"auth_date": str(old_auth_date), "user": '{"id": 42}'}
    init_data = build_init_data(fields)
    data = validate_init_data(init_data, BOT_TOKEN, max_age=None)
    assert data["user"]["id"] == 42


def test_validate_init_data_missing_bot_token():
    with pytest.raises(InitDataError):
        validate_init_data("hash=x&auth_date=1", "")


def test_validate_init_data_missing_hash():
    with pytest.raises(InitDataError):
        validate_init_data("auth_date=1&user=%7B%7D", BOT_TOKEN)
