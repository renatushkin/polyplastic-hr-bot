import unittest
from unittest.mock import patch
from registry_upload import attachment_url
from accounts import phone
class RegistryTests(unittest.TestCase):
    def test_phone(self):
        self.assertEqual(phone('79083462819'),phone('89083462819'))
    def test_attachment(self):
        self.assertEqual(attachment_url({'attachments':[{'type':'file','payload':{'filename':'staff.xlsx','url':'https://files.max.ru/file'}}]}),'https://files.max.ru/file')
    def test_no_pdf(self):
        self.assertIsNone(attachment_url({'attachments':[{'type':'file','payload':{'filename':'x.pdf','url':'https://files.max.ru/x'}}]}))
if __name__=='__main__':unittest.main()
