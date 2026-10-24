import json,os,secrets
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs

def load_env():
    p=Path(".env")
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line=line.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1); os.environ.setdefault(k.strip(),v.strip())
load_env()
from database import init_db
from bot import state,handle
from hr import list_tickets,reply_ticket
TOKEN=os.getenv("HR_TOKEN") or secrets.token_urlsafe(20)
class Handler(BaseHTTPRequestHandler):
    def output(self,data,status=200,kind="application/json; charset=utf-8"):
        body=(json.dumps(data,ensure_ascii=False) if kind.startswith("application/json") else data).encode()
        self.send_response(status); self.send_header("Content-Type",kind); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
    def authorized(self):
        return secrets.compare_digest(self.headers.get("X-HR-Token",""),TOKEN)
    def do_GET(self):
        path=urlparse(self.path)
        try:
            if path.path=="/": return self.output(Path(__file__).with_name("web.html").read_text(encoding="utf-8"),kind="text/html; charset=utf-8")
            if path.path=="/api/state": return self.output(state(parse_qs(path.query).get("employee_id",["demo-gtp"])[0]))
            if path.path=="/api/tickets":
                if not self.authorized(): return self.output({"error":"Неверный HR-токен"},401)
                return self.output(list_tickets())
            self.output({"error":"Не найдено"},404)
        except ValueError as e: self.output({"error":str(e)},400)
    def do_POST(self):
        try:
            size=int(self.headers.get("Content-Length","0"))
            if size<1 or size>20000: return self.output({"error":"Некорректный размер запроса"},400)
            data=json.loads(self.rfile.read(size))
            text=str(data.get("text"," ")).strip()
            if not text or len(text)>4000: raise ValueError("Введите текст до 4000 символов")
            if self.path=="/api/action": return self.output(handle(data["employee_id"],data["action"],text))
            if self.path=="/api/reply":
                if not self.authorized(): return self.output({"error":"Неверный HR-токен"},401)
                reply_ticket(int(data["ticket_id"]),text); return self.output({"ok":True})
            self.output({"error":"Не найдено"},404)
        except (ValueError,KeyError,TypeError) as e: self.output({"error":str(e)},400)
if __name__=="__main__":
    init_db()
    print("Локальное демо: http://127.0.0.1:8000")
    print("HR-токен:",TOKEN)
    ThreadingHTTPServer(("127.0.0.1",8000),Handler).serve_forever()
