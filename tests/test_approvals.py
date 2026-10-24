import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        import database
        self.old=database.DB
        database.DB=str(Path(self.tmp.name)/'test.db')
        database.init_db()
        from accounts import init_accounts
        init_accounts()
        with database.connect() as c:
            c.execute("INSERT INTO staff_registry(phone,name,role,tags) VALUES('+79991234567','HR Test','hr','[]')")
    def tearDown(self):
        import database
        database.DB=self.old
        self.tmp.cleanup()
    def test_approval(self):
        from approvals import request_access,pending,review
        self.assertIn('Заявка №',request_access('111','+79991234567'))
        self.assertIn('Заявка №',request_access('222','+79991234567'))
        self.assertEqual(len(pending()),2)
        self.assertIn('Нельзя',review(1,'approve','111'))
        self.assertEqual(review(1,'approve','999'),'Одобрено')
        from accounts import account
        self.assertEqual(account('111')['role'],'hr')
        self.assertIsNone(account('222'))
        self.assertEqual(len(pending()),0)
    def test_reject(self):
        from approvals import request_access,review
        request_access('111','+79991234567')
        self.assertEqual(review(1,'reject','999'),'Отклонено')
        from accounts import account
        self.assertIsNone(account('111'))

if __name__=='__main__':unittest.main()
