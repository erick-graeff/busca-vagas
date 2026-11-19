import os

import pytest
import requests


def test_no_credentials_or_network_in_tests():
    assert "TELEGRAM_BOT_TOKEN" not in os.environ and "TELEGRAM_CHAT_ID" not in os.environ
    with pytest.raises(RuntimeError, match="acessar a rede"):
        requests.post("https://api.telegram.org/botX/sendMessage", json={})
