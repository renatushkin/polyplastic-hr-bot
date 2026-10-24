import json,re
from pathlib import Path
from database import employee
from llm import generate
CHUNKS=json.loads(Path(__file__).with_name("data").joinpath("demo/knowledge.json").read_text(encoding="utf-8"))
def tokens(text):
    return set(re.findall(r"[а-яёa-z0-9]{3,}",text.lower()))-{"как","что","для","или","это","мне","где","можно"}

def search_knowledge(question, employee_tags):
    q=tokens(question)
    ranked=[]
    for chunk in CHUNKS:
        if chunk.get("tags") and not set(chunk["tags"]) & set(employee_tags): continue
        score=len(q & tokens(chunk["text"]+" "+chunk.get("keywords","")))
        if score: ranked.append((score,chunk))
    return [c for _,c in sorted(ranked,key=lambda x:x[0],reverse=True)[:3]]

def answer_question(employee_id,question):
    fragments=search_knowledge(question,employee(employee_id)["tags"])
    fallback={"answer":"Нет подтверждённого ответа. Можно передать вопрос закреплённому HR.","sources":[],"needs_hr":True}
    if not fragments: return fallback
    try:
        text=generate(question,fragments)
        if not text or "NO_ANSWER" in text: return fallback
        return {"answer":text,"sources":[{"source":f["source"],"location":f["location"]} for f in fragments],"needs_hr":False}
    except Exception:
        return {**fallback,"answer":"Модуль ответов сейчас недоступен. Можно обратиться к HR."}
