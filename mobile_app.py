"""Mobile browser UI for the enriched Text-to-SQL API.
Run with: PYTHONPATH=src:. uvicorn mobile_app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import html
import json

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from src.api.main_enriched import app as core_app, handle_query, QueryReq

app: FastAPI = core_app

PAGE = """
<!doctype html><html lang='en'><head><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>ITXN Mobile Lab</title>
<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:auto;padding:16px;background:#f6f6f6}textarea{width:100%;box-sizing:border-box;min-height:100px;padding:12px;border-radius:12px;border:1px solid #bbb}button{margin-top:10px;padding:12px 18px;border:0;border-radius:12px;font-weight:700}pre{white-space:pre-wrap;word-break:break-word;background:white;padding:12px;border-radius:12px;overflow:auto}.hint{color:#555}</style></head>
<body><h2>ITXN · Mobile Lab</h2><p class='hint'>یک سؤال فارسی یا انگلیسی بزن. مسیر اصلی Text→SQL→Review→Validate→DuckDB→Baseline→CEO/BA را اجرا می‌کند.</p>
<textarea id='q'>میانگین latency سرور SRV-A دیروز چقدر بود؟</textarea><br><button onclick='runQ()'>Run real query</button><pre id='out'>Ready.</pre>
<script>async function runQ(){const q=document.getElementById('q').value;document.getElementById('out').textContent='Running...';try{const r=await fetch('/query',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:q,user_id:'mobile_user',user_role:'analyst'})});document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}catch(e){document.getElementById('out').textContent=String(e)}}</script>
</body></html>
"""

@app.get("/", response_class=HTMLResponse)
async def root() -> str:
    return PAGE
