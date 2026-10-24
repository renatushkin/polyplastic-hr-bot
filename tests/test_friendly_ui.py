import os,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
class UITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'DATABASE_PATH':str(Path(self.tmp.name)/'test.db')})
        self.env.start()
    def tearDown(self):self.env.stop();self.tmp.cleanup()
    def test_menu(self):
        from friendly_ui import menu
        self.assertIn('Обращения',menu('hr'))
        self.assertIn('Заявки',menu('admin'))
    def test_state(self):
        from friendly_ui import set_state,get_state
        set_state(42,'phone');self.assertEqual(get_state(42),'phone')
        set_state(42,None);self.assertIsNone(get_state(42))
    def test_keyboard(self):
        from max_adapter import make_keyboard
        k=make_keyboard('1. 📱 Указать номер телефона\n2. 🆔 Мой MAX ID')
        self.assertEqual(len(k[0]['payload']['buttons']), 3)
        labels = [
            row[0]["text"]
            for row in k[0]["payload"]["buttons"]
        ]
        self.assertEqual(labels, [
            "📱 Указать номер телефона",
            "🆔 Мой MAX ID",
            "🏠 Главное меню",
        ])
    def test_phone(self):
        from friendly_ui import phone_like
        self.assertTrue(phone_like('+7 999 123-45-67'))
        self.assertFalse(phone_like('привет'))
if __name__=='__main__':unittest.main()
