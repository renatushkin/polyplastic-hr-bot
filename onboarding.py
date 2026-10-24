import json
from pathlib import Path
from database import connect, employee, add_message
STEPS=json.loads(Path(__file__).with_name("data").joinpath("demo/scenario.json").read_text(encoding="utf-8"))
def applicable(step, person):
    return not step["tags"] or bool(set(step["tags"]) & set(person["tags"]))

def get_current_step(employee_id):
    p=employee(employee_id)
    for index in range(p["step"],len(STEPS)):
        if applicable(STEPS[index],p):
            return {**STEPS[index],"index":index,"done":False}
    return {"done":True,"text":"Демонстрационный блок адаптации завершён.","buttons":[]}

def submit_step_answer(employee_id, answer):
    # The transaction prevents a concurrent double click from advancing twice.
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row=c.execute("SELECT * FROM employees WHERE id=?",(employee_id,)).fetchone()
        if not row: raise ValueError("Сотрудник не найден")
        p=dict(row); p["tags"]=json.loads(p["tags"])
        selected=next(((i,STEPS[i]) for i in range(p["step"],len(STEPS)) if applicable(STEPS[i],p)),None)
        if selected is None: return get_current_step(employee_id)
        index,step=selected
        if answer not in step["buttons"]: raise ValueError("Выберите один из ответов текущего шага")
        c.execute("INSERT OR IGNORE INTO answers(employee_id,step_id,answer) VALUES(?,?,?)",(employee_id,step["id"],answer))
        c.execute("UPDATE employees SET step=? WHERE id=?",(index+1,employee_id))
        c.execute("INSERT INTO messages(employee_id,author,text) VALUES(?,?,?)",(employee_id,"employee",answer))
    return get_current_step(employee_id)
