import unittest
from datetime import date
from scheduler import is_workday, scheduled_at, sendable

class CalendarTests(unittest.TestCase):
    def test_holiday(self):
        self.assertFalse(is_workday(date(2026,11,4)))
        self.assertEqual(scheduled_at({'time':'В третий рабочий день в 09.00','text':'Привет','conditional':False},date(2026,11,1)).date(),date(2026,11,5))
    def test_service(self):
        self.assertFalse(sendable({'text':'# Приложить Открытку к сообщению'}))
        self.assertFalse(sendable({'text':'Варианты ответов:\n1) На ТЫ'}))
    def test_no_unknown_date(self):
        self.assertIsNone(scheduled_at({'time':'В 09.01','text':'Вопрос','conditional':False},date(2026,11,1)))

if __name__=='__main__': unittest.main()
