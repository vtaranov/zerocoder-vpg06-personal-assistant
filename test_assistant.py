"""Offline tests; all external calls replaced explicitly."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from io import BytesIO
from config import Config
from external_tools import Weather, ExternalTools
from assistant import Assistant
from memory import Memory
from bot import build_bot, deliver

class Checks(unittest.TestCase):
    def test_weather_success_and_missing_city(self):
        with patch("external_tools.get_json", side_effect=[{"results": [{"name": "Москва", "latitude": 55, "longitude": 37}]},
            {"current": {"temperature_2m": 5}, "current_units": {"temperature_2m": "°C"}, "timezone": "Europe/Moscow"}]):
            self.assertTrue(Weather().run("Москва")["result"]["ok"])
        with patch("external_tools.get_json", return_value={}):
            self.assertEqual(Weather().run("несуществующий")["result"]["error"], "city_not_found")
    def test_api_failure_not_success(self):
        tools = ExternalTools(Config("test", "test", "test"))
        with patch("external_tools.get_json", side_effect=ValueError("bad response")):
            self.assertFalse(tools.cat_fact()["ok"])
            self.assertFalse(tools.analyze_dog()["ok"])
            self.assertEqual(tools.attachments, [])
    def test_image_host_is_restricted(self):
        tools = ExternalTools(Config("test", "test", "test"))
        with patch("external_tools.get_json", return_value={"message": "http://127.0.0.1/private"}), patch("external_tools.httpx.stream") as request:
            self.assertFalse(tools.analyze_dog()["ok"])
            request.assert_not_called()
    def test_owner_namespaces_and_invalid_input(self):
        m = Memory.__new__(Memory); m.config = Config("test", "test", "test")
        self.assertNotEqual(m.namespace("alice"), m.namespace("bob"))
        self.assertTrue(m.namespace("alice").startswith("vpg06-"))
        with self.assertRaises(ValueError):m.namespace("")
        a = Assistant(m.config, memory=Mock())
        for text in ["", "/clear", "x"*4001]:
            with self.assertRaises(ValueError):a.handle("alice", text)
        a.memory.save_user.assert_not_called()
    def test_only_user_text_written(self):
        m = Memory.__new__(Memory);m.config = Config("test", "test", "test")
        m.embed = Mock(return_value=[0.0]*1536)
        store = Mock();m.store = Mock(return_value=store)
        m.index = Mock()
        def write(docs, **kwargs):
            self.assertEqual(docs[0].content, "  Оригинальное сообщение  ")
            self.assertEqual(set(docs[0].meta), {"type", "created_at"})
            m.index.fetch.return_value = NS(vectors={docs[0].id: NS()})
            m.search = Mock(return_value=[{"id": docs[0].id}])
        store.write_documents.side_effect = write
        m.save_user("alice", "  Оригинальное сообщение  ")
        store.write_documents.assert_called_once()
    def test_pinecone_list_item_sdk_compatibility(self):
        m = Memory.__new__(Memory); m.config = Config("test", "test", "test")
        m.index = Mock()
        m.index.list.return_value = [[NS(id="id-new"), "id-old"]]
        m.index.fetch.return_value = NS(vectors={"id-new": NS(metadata={"content":"original"})})
        self.assertEqual(m.rows("alice")[0]["metadata"]["content"], "original")
        self.assertEqual(m.index.fetch.call_args.kwargs["ids"], ["id-new", "id-old"])
    def test_telegram_access_commands_and_image_caption(self):
        import telebot
        bot = telebot.TeleBot("123456:dummy", threaded=False)
        bot.send_message = Mock();bot.send_photo = Mock()
        svc = Mock();svc.handle.return_value = {"answer": "Ответ", "attachments": []}
        cfg = Config("test", "test", "test", allowed_users=(7,))
        build_bot(cfg, svc, bot)
        handler = bot.message_handlers[0]["function"]
        msg = NS(from_user=NS(id=8), chat=NS(id=7, type="private"), text="Привет")
        handler(msg);svc.handle.assert_not_called()
        msg.from_user.id = 7;msg.text = "/help";handler(msg);svc.handle.assert_not_called()
        msg.text = "Привет";handler(msg);svc.handle.assert_called_once_with("telegram:7:7", "Привет")
        deliver(bot,7,{"answer":"Готово", "attachments":[{"bytes":b"exact-image", "caption":"Описание"}]})
        args,kw = bot.send_photo.call_args
        self.assertEqual(args[1].getvalue(),b"exact-image")
        self.assertEqual(kw["caption"],"Описание")
if __name__ == "__main__":unittest.main()
