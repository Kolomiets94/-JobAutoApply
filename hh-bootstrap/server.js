import express from "express";
import { chromium } from "playwright";

const app = express();
app.use(express.json({ limit: "32kb" }));
app.use(express.urlencoded({ extended: false }));

const TOKEN = process.env.BOOTSTRAP_TOKEN;
if (!TOKEN) throw new Error("BOOTSTRAP_TOKEN is required");

let context;
let page;

function ok(req) {
  return req.query.t === TOKEN || req.body?.t === TOKEN || req.get("x-bootstrap-token") === TOKEN;
}
function guard(req, res, next) {
  if (!ok(req)) return res.status(403).send("Forbidden");
  next();
}
async function ensureBrowser() {
  if (page && !page.isClosed()) return page;
  context = await chromium.launchPersistentContext("/tmp/hh-profile", {
    headless: true,
    viewport: { width: 390, height: 844 },
    locale: "ru-RU",
  });
  page = context.pages()[0] || await context.newPage();
  await page.goto("https://hh.ru/applicant/profile/me", { waitUntil: "domcontentloaded", timeout: 60000 });
  return page;
}

app.get("/health", (_req, res) => res.send("ok"));

app.get("/", guard, async (req, res) => {
  await ensureBrowser();
  const t = encodeURIComponent(TOKEN);
  res.type("html").send(`<!doctype html>
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>HH Session Bootstrap</title>
<style>
body{font-family:-apple-system,sans-serif;margin:0;background:#111;color:#fff}#bar{position:sticky;top:0;background:#222;padding:8px;z-index:2}
button,input{font-size:16px;padding:10px;margin:3px}#shot{width:100%;display:block;touch-action:manipulation}#txt{width:55%}.hint{font-size:13px;color:#bbb;padding:6px}
</style>
<div id="bar">
<button onclick="nav()">HH</button><button onclick="back()">←</button><button onclick="key('Enter')">Enter</button>
<input id="txt" autocomplete="off" placeholder="Текст для выбранного поля"><button onclick="typeText()">Ввести</button>
<a href="/state?t=${t}"><button>Скачать сессию</button></a>
<div class="hint">Нажми нужное поле на снимке, введи текст сверху и нажми «Ввести».</div>
</div>
<img id="shot" src="/shot?t=${t}&n=0">
<script>
const T=${JSON.stringify(TOKEN)}; let n=1;
const shot=document.getElementById('shot');
async function post(path,data={}){await fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({...data,t:T})}); refresh()}
function refresh(){shot.src='/shot?t='+encodeURIComponent(T)+'&n='+(n++)}
shot.onclick=async e=>{const r=shot.getBoundingClientRect(); const x=(e.clientX-r.left)*390/r.width; const y=(e.clientY-r.top)*844/r.height; await post('/click',{x,y})}
async function typeText(){const el=document.getElementById('txt'); await post('/type',{text:el.value}); el.value=''}
async function key(k){await post('/key',{key:k})}
async function nav(){await post('/nav')}
async function back(){await post('/back')}
setInterval(refresh,2500);
</script>`);
});

app.get("/shot", guard, async (_req, res) => {
  const p = await ensureBrowser();
  const buf = await p.screenshot({ type: "jpeg", quality: 72 });
  res.type("jpg").send(buf);
});
app.post("/click", guard, async (req, res) => {
  const p = await ensureBrowser();
  await p.mouse.click(Number(req.body.x), Number(req.body.y));
  res.json({ ok: true });
});
app.post("/type", guard, async (req, res) => {
  const p = await ensureBrowser();
  await p.keyboard.type(String(req.body.text || ""), { delay: 25 });
  res.json({ ok: true });
});
app.post("/key", guard, async (req, res) => {
  const p = await ensureBrowser();
  await p.keyboard.press(String(req.body.key || "Enter"));
  res.json({ ok: true });
});
app.post("/nav", guard, async (_req, res) => {
  const p = await ensureBrowser();
  await p.goto("https://hh.ru/applicant/profile/me", { waitUntil: "domcontentloaded", timeout: 60000 });
  res.json({ ok: true });
});
app.post("/back", guard, async (_req, res) => {
  const p = await ensureBrowser(); await p.goBack({ waitUntil: "domcontentloaded", timeout: 30000 }).catch(()=>{});
  res.json({ ok: true });
});
app.get("/state", guard, async (_req, res) => {
  await ensureBrowser();
  const state = await context.storageState();
  res.setHeader("Content-Disposition", 'attachment; filename="hh-state.json"');
  res.type("application/json").send(JSON.stringify(state));
});

app.listen(process.env.PORT || 10000, "0.0.0.0", () => console.log("HH bootstrap ready"));
