import unittest
from datetime import datetime
from calendar_groups import groups, clean_text

class GroupTests(unittest.TestCase):
    def test_merge(self):
        due = datetime(2026, 10, 29, 9)
        items = [(due, 'max-1', {'id': f'excel-{i}', 'text': f'сообщение {i}', 'buttons': ['Далее']}) for i in range(3)]
        self.assertEqual(len(groups(items)), 1)
        self.assertEqual(len(groups(items)[0]['steps']), 3)

    def test_questions_separate(self):
        due = datetime(2026, 10, 29, 9)
        items = [(due, 'max-1', {'id': 'a', 'text': 'привет', 'buttons': ['Далее']}),
                 (due, 'max-1', {'id': 'b', 'text': 'вопрос', 'buttons': ['Да', 'Нет']}),
                 (due, 'max-1', {'id': 'c', 'text': 'дальше', 'buttons': ['Далее']})]
        self.assertEqual(len(groups(items)), 3)

    def test_attachment_instruction(self):
        self.assertEqual(clean_text({'text': 'Привет # Приложить Открытку к сообщению'}), '')

    def test_max_length(self):
        due = datetime(2026, 10, 29, 9)
        items = [(due, 'max-1', {'id': str(i), 'text': 'x'*2000}) for i in range(3)]
        self.assertEqual(len(groups(items)), 3)

if __name__ == '__main__':
    unittest.main()
