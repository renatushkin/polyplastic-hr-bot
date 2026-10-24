import os,tempfile,unittest
from datetime import date,timedelta
os.environ['DATABASE_PATH']=tempfile.mktemp(suffix='.db')
from database import init_db,connect
from onboarding import STEPS,get_current_step,submit_step_answer,set_tag,set_schedule,reset_progress,due_date
from max_handlers import ensure_employee,handle_message
class TestKorsik(unittest.TestCase):
 @classmethod
 def setUpClass(cls):init_db()
 def test_scenario(self):
  self.assertEqual(len(STEPS),68)
  self.assertTrue(any(s['conditional'] for s in STEPS))
 def test_tags_and_progress(self):
  eid=ensure_employee('test1');self.assertEqual(get_current_step(eid)['id'],'excel-3')
  submit_step_answer(eid,'Далее');self.assertEqual(get_current_step(eid)['id'],'excel-4')
  set_tag(eid,'Luzhniki');self.assertEqual(get_current_step(eid)['id'],'excel-3')
  reset_progress(eid)
 def test_calendar(self):
  eid=ensure_employee('test2');set_schedule(eid,(date.today()+timedelta(days=30)).isoformat())
  self.assertTrue(get_current_step(eid).get('waiting'))
  set_schedule(eid,date.today().isoformat(),'demo');self.assertFalse(get_current_step(eid).get('waiting',False))
 def test_hr_ticket(self):
  eid=ensure_employee('test3');from hr import create_ticket,reply_ticket
  n=create_ticket(eid,'Вопрос');reply_ticket(n,'Ответ')
  with connect() as c:self.assertEqual(c.execute('SELECT status FROM tickets WHERE id=?',(n,)).fetchone()[0],'answered')
if __name__=='__main__':unittest.main()
