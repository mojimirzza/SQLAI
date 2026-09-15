# ITXN Mobile Lab

هدف این نسخه این است که بدون لپ‌تاپ، پروژه را در یک browser-based cloud IDE اجرا کنی.

## گزینه پیشنهادی: GitHub Codespaces

GitHub برای حساب شخصی Free در حال حاضر 120 core-hours و 15 GB storage در ماه Codespaces می‌دهد و Codespace در مرورگر اجرا می‌شود. 

1. ZIP را از حالت فشرده خارج کن و محتویاتش را در یک GitHub repository شخصی بگذار.
2. در GitHub روی **Code → Codespaces → Create codespace on main** بزن.
3. در Terminal:

```bash
pip install -r requirements.txt
python scripts/init_db.py
python scripts/seed_mobile_lab.py
PYTHONPATH=src:. uvicorn mobile_app:app --host 0.0.0.0 --port 8000
```

4. از تب **Ports** پورت 8000 را **Public** کن و لینک را در Chrome موبایل باز کن.
5. در GitHub Codespaces، کلید OpenAI را داخل فایل `.env` ننویس؛ از **Repository/Codespaces secret** استفاده کن و نام آن `OPENAI_API_KEY` باشد.

## گزینه ساده‌تر: Replit

Replit در پلن Starter فعلی یک پروژه publish‌شده و استفاده رایگان روزانه ارائه می‌کند؛ برای تست سریع موبایلی مناسب است.

بعد از Import کردن پروژه، Secret با نام `OPENAI_API_KEY` بساز و Run command را این قرار بده:

```bash
python scripts/init_db.py && python scripts/seed_mobile_lab.py && PYTHONPATH=src:. uvicorn mobile_app:app --host 0.0.0.0 --port 8000
```

## تست لایه‌ها

### مسیر زنده با LLM
`/` → `POST /query`

این مسیر باید Text-to-SQL، SQL review، validation، read-only DuckDB، baseline enrichment، و دو خروجی BA/CEO را در یک درخواست اجرا کند.

### مسیرهای deterministic که بدون LLM هم قابل تست‌اند

```bash
pytest -q tests/test_evolution_layers.py tests/test_situation_memory_contract.py tests/test_situation_memory_react_integration.py tests/test_sml_ab_evaluation.py
pytest -q sidecar/tests_stage4.py tests/test_stage4.py
```

اینها SML correlation/storage، evidence package، hypothesis generation، council scoring، proposal creation، state manager، loop verification، replay و ReAct contract را تست می‌کنند.

## نکته معماری مهم

در کد فعلی، Pattern Analyzer، Evidence Builder، Hypothesis Generator و Council **دترمینیستیک هستند و LLM لازم ندارند**. بخش‌های واقعاً LLM-dependent عبارت‌اند از Text-to-SQL/OpenAI adapter، SQL Reviewer/synthesis و Agent/Sidecar LLM client.

## هشدار امنیتی

کلید API قبلی که در چت فرستاده شد را revoke/rotate کن. فقط کلید جدید را به‌عنوان secret/environment variable وارد کن.
