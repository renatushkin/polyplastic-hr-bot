from database import connect, employee

def create_ticket(employee_id,question):
    p=employee(employee_id)
    with connect() as c:
        old=c.execute("SELECT id FROM tickets WHERE employee_id=? AND question=? AND status='open'",(employee_id,question)).fetchone()
        if old: return old["id"]
        cur=c.execute("INSERT INTO tickets(employee_id,hr_id,question) VALUES(?,?,?)",(employee_id,p["hr_id"],question))
        c.execute("INSERT INTO messages(employee_id,author,text) VALUES(?,?,?)",(employee_id,"bot","Вопрос передан закреплённому HR."))
        return cur.lastrowid

def list_tickets():
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM tickets ORDER BY id DESC")]

def reply_ticket(ticket_id,answer):
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        ticket=c.execute("SELECT * FROM tickets WHERE id=?",(ticket_id,)).fetchone()
        if not ticket: raise ValueError("Обращение не найдено")
        if ticket["status"]!="open": raise ValueError("Обращение уже закрыто")
        c.execute("UPDATE tickets SET status='answered',answer=? WHERE id=?",(answer,ticket_id))
        c.execute("INSERT INTO messages(employee_id,author,text) VALUES(?,?,?)",(ticket["employee_id"],"hr",answer))
