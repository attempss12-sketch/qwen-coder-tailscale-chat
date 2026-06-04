import argparse
import json
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

OLLAMA_HOST = "http://localhost:11434"
MODEL = "qwen2.5-coder:7b"

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Qwen2.5-Coder Chat</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#c9d1d9;height:100vh;display:flex;flex-direction:column}
  header{background:#161b22;padding:16px 24px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:12px}
  header h1{font-size:18px;font-weight:600}
  header span{color:#8b949e;font-size:13px}
  #chat{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:16px}
  .msg{max-width:80%;padding:12px 16px;border-radius:8px;line-height:1.5;font-size:14px;white-space:pre-wrap;word-break:break-word}
  .user{background:#1f6feb;color:#fff;align-self:flex-end;border-bottom-right-radius:2px}
  .bot{background:#21262d;color:#c9d1d9;align-self:flex-start;border-bottom-left-radius:2px;border:1px solid #30363d}
  .bot.loading{opacity:.7}
  .typing::after{content:'\u25CF';animation:blink 1.2s steps(1) infinite;margin-left:4px}
  @keyframes blink{50%{opacity:0}}
  #input-area{display:flex;padding:16px 24px;gap:12px;background:#161b22;border-top:1px solid #30363d}
  #input{flex:1;padding:10px 14px;border-radius:6px;border:1px solid #30363d;background:#0d1117;color:#c9d1d9;font-size:14px;outline:none;resize:none}
  #input:focus{border-color:#1f6feb}
  #send{padding:10px 20px;border:none;border-radius:6px;background:#1f6feb;color:#fff;font-size:14px;font-weight:600;cursor:pointer;transition:background .2s}
  #send:hover{background:#388bfd}
  #send:disabled{opacity:.5;cursor:not-allowed}
  .info{text-align:center;font-size:12px;color:#484f58;padding:8px}
  .info a{color:#58a6ff}
</style>
</head>
<body>
<header>
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#58a6ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
  <h1>Qwen2.5-Coder 7B</h1>
  <span>Ollama &middot; Tailscale</span>
</header>
<div id="chat"></div>
<div id="input-area">
  <textarea id="input" rows="1" placeholder="Type your message..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea>
  <button id="send" onclick="send()">Send</button>
</div>
<div class="info">Accessible via Tailscale &middot; Auto-shutdown in progress</div>
<script>
const chat=document.getElementById('chat');
const input=document.getElementById('input');
const sendBtn=document.getElementById('send');

function addMsg(content,role){
  const div=document.createElement('div');
  div.className='msg '+(role==='user'?'user':'bot');
  div.textContent=content;
  chat.appendChild(div);
  chat.scrollTop=chat.scrollHeight;
  return div;
}

async function send(){
  const text=input.value.trim();
  if(!text)return;
  input.value='';
  input.style.height='auto';
  addMsg(text,'user');
  sendBtn.disabled=true;
  const botDiv=addMsg('\u200B','bot loading');
  botDiv.classList.add('typing');
  try{
    const res=await fetch('/api/chat',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text})
    });
    const reader=res.body.getReader();
    const decoder=new TextDecoder();
    let full='';
    while(true){
      const {done,value}=await reader.read();
      if(done)break;
      const chunk=decoder.decode(value);
      for(const line of chunk.split('\n').filter(l=>l.trim())){
        try{
          const data=JSON.parse(line);
          if(data.done)break;
          full+=data.content||'';
          botDiv.textContent=full;
          botDiv.classList.remove('typing');
          chat.scrollTop=chat.scrollHeight;
        }catch(e){}
      }
    }
    if(!full)botDiv.textContent='(no response)';
    botDiv.classList.remove('loading');
  }catch(e){
    botDiv.textContent='Error: '+e.message;
    botDiv.classList.remove('typing','loading');
  }
  sendBtn.disabled=false;
}

function autoResize(){
  this.style.height='auto';
  this.style.height=Math.min(this.scrollHeight,200)+'px';
}
input.addEventListener('input',autoResize);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            message = body.get("message", "")

            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            payload = json.dumps({
                "model": MODEL,
                "prompt": message,
                "stream": True,
            })

            try:
                proc = subprocess.Popen(
                    ["curl", "-s", "-N", "-X", "POST",
                     f"{OLLAMA_HOST}/api/generate",
                     "-d", payload],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                for line in iter(proc.stdout.readline, b""):
                    self.wfile.write(line)
                    self.wfile.flush()
                proc.wait()
            except Exception as e:
                err = json.dumps({"error": str(e), "done": True})
                self.wfile.write(f"{err}\n".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"Chat UI running on http://0.0.0.0:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
