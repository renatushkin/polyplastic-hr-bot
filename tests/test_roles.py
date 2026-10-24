import os
import tempfile
import unittest
from pathlib import Path

                                  
test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db.close()
os.environ["DATABASE_PATH"] = test_db.name

import database
from database import init_db
from accounts import (
    init_accounts,
    read_registry,
    import_staff,
    activate,
    account,
)
from onboarding import applicable

ROOT = Path(__file__).parent


class RolesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.old_db = database.DB
        database.DB = test_db.name
        init_db()
        init_accounts()


        import csv

        cls.fixture = Path(test_db.name + ".csv")

        with cls.fixture.open(
            "w", encoding="utf-8-sig", newline=""
        ) as f:
            writer = csv.writer(f)
            writer.writerow([
                "ФИО", "Телефон", "Роль", "Тег"
            ])
            for i in range(4):
                writer.writerow([
                    f"Тестовый сотрудник {i + 1}",
                    f"7999000000{i}",
                    "employee",
                    "GTP",
                ])

        cls.rows = read_registry(cls.fixture)
        cls.count, cls.codes = import_staff(
            cls.fixture, allow_roles=True
        )

    @classmethod
    def tearDownClass(cls):
        database.DB = cls.old_db
        Path(test_db.name).unlink(missing_ok=True)

        cls.fixture.unlink(missing_ok=True)

    def test_a_import(self):
        self.assertEqual(len(self.rows), 4)
        self.assertEqual(self.count, 4)
        self.assertEqual(len(self.codes), 4)

    def test_b_activate(self):
        self.assertIsNone(activate("999", "wrongcode"))

        employee = next(
            c for c in self.codes
            if c["role"] == "employee"
        )

        result = activate("100", employee["code"])

        self.assertIsNotNone(result)
        self.assertEqual(result["role"], "employee")
        self.assertEqual(account("100")["role"], "employee")

                                          
        self.assertIsNone(
            activate("500", employee["code"])
        )

    def test_c_tags(self):
        self.assertTrue(
            applicable({"tags": []}, {"tags": ["GTP"]})
        )
        self.assertFalse(
            applicable({"tags": ["GrPP"]}, {"tags": ["GTP"]})
        )

    def test_d_role_lock(self):
        from max_handlers import handle_message

        self.assertIn(
            "назначаются HR",
            handle_message("100", "/tag GrPP"),
        )


if __name__ == "__main__":
    unittest.main()
