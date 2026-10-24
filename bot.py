from database import employee,history,add_message
from onboarding import get_current_step, submit_step_answer
from rag import answer_question
from hr import create_ticket

def state(employee_id):
    p=employee(employee_id)
    return {"employee":p,"step":get_current_step(employee_id),"messages":history(employee_id)}

def handle(employee_id,action,text):
    employee(employee_id)
    if action=="step":
        submit_step_answer(employee_id,text)
        return state(employee_id)
    if action=="question":
        add_message(employee_id,"employee",text)
        result=answer_question(employee_id,text)
        source_text="; ".join(s["source"]+" — "+s["location"] for s in result["sources"])
        add_message(employee_id,"bot",result["answer"]+("\nИсточники: "+source_text if source_text else ""))
        return {**state(employee_id),"result":result}
    if action=="ticket":
        return {**state(employee_id),"ticket_id":create_ticket(employee_id,text)}
    raise ValueError("Неизвестное действие")

# MAX adapter is intentionally not implemented. Connect actual authenticated
# MAX updates to handle(), and send its results through the official channel API.
