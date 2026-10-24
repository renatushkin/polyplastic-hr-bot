import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from scheduler import scheduled_at, workday

class SchedulerTests(unittest.TestCase):
    def test_weekend(self):
        self.assertEqual(workday(date(2026, 10, 24), 1), date(2026, 10, 26))
        self.assertEqual(workday(date(2026, 10, 24), 3), date(2026, 10, 28))
    def test_before_start(self):
        value = scheduled_at({'time': 'За 2-3 дня до выхода на работу', 'text': 'Привет! Скоро твой первый рабочий день.'}, date(2026, 10, 28))
        self.assertEqual(value.date(), date(2026, 10, 25))
    def test_conditional(self):
        self.assertIsNone(scheduled_at({'time':'За день', 'conditional':True}, date(2026, 10, 28)))

if __name__ == '__main__':
    unittest.main()
