# RFC-001 — Evidence Package Specification

**Version:** 1.0  
**Status:** Draft / Architecture Baseline  
**Layer:** Shura / Knowledge Governance Loop  
**Date:** 2026-08-19  
**Scope:** Contract between Evidence Builder and Knowledge Council

---

## 1. Abstract

`Evidence Package` قرارداد رسمی بین لایه‌ی جمع‌آوری و نرمال‌سازی شواهد و لایه‌ی شورای دانش است.

هدف آن این است که شورا به‌جای دریافت لاگ‌ها، KPIها، فیدبک‌ها و سیگنال‌های ناهمگون، یک بسته‌ی استاندارد، قابل‌اعتبارسنجی، نسخه‌پذیر و قابل‌ممیزی دریافت کند.

Evidence Package **تصمیم نمی‌گیرد** و **تغییر ایجاد نمی‌کند**. فقط شواهد را در قالبی استاندارد ارائه می‌کند تا مراحل بعدی بتوانند بر مبنای آن فرضیه بسازند، نقد کنند و در نهایت یک Knowledge Change Proposal تولید کنند.

اصل کلیدی:

> **Evidence is not a decision. Evidence is the auditable basis on which a decision may be proposed.**

---

## 2. جایگاه در معماری

```text
                    ┌─────────────────────────────┐
                    │       Production System     │
                    │ Text-to-SQL / Agents / KPI │
                    └──────────────┬──────────────┘
                                   │ signals
                                   ▼
                    ┌─────────────────────────────┐
                    │      Evidence Collectors    │
                    │ logs / KPI / feedback / DQ  │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │       Evidence Builder      │
                    │ normalize / correlate /     │
                    │ aggregate / summarize       │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
              ┌──────────────────────────────────────────┐
              │           EVIDENCE PACKAGE               │
              │          ← RFC-001 CONTRACT →             │
              └────────────────────┬─────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │      Evidence Validator     │
                    └──────────────┬──────────────┘
                                   │ accepted package
                                   ▼
                    ┌─────────────────────────────┐
                    │    Hypothesis Generator     │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │   Council / Debate Engine   │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    Knowledge Change Proposal
```

---

## 3. مسئولیت

### 3.1 مسئولیت Evidence Package

Evidence Package باید:

- شواهد را استاندارد کند.
- منشأ هر شاهد را حفظ کند.
- ارتباط شواهد با مسئله را مشخص کند.
- بازه‌ی زمانی و context را حفظ کند.
- سطح اطمینان و کیفیت شواهد را ثبت کند.
- امکان audit و replay را فراهم کند.
- از تغییر ناخواسته‌ی شواهد پس از تولید جلوگیری کند.
- مستقل از مدل AI و فناوری تولیدکننده باشد.

### 3.2 خارج از مسئولیت

Evidence Package نباید:

- فرضیه‌ی نهایی تولید کند.
- علت ریشه‌ای را قطعی اعلام کند.
- رأی بدهد.
- SQL تولید یا اصلاح کند.
- دانش دامنه را تغییر دهد.
- GitHub PR ایجاد کند.
- CI/CD را اجرا کند.
- Deploy انجام دهد.
- تصمیم کسب‌وکاری یا ریسک نهایی بگیرد.

---

## 4. منابع ورودی

Evidence Builder می‌تواند از منابع زیر شواهد دریافت کند:

1. User Query Logs
2. Intent / Semantic Parsing Results
3. Generated SQL
4. SQL Rewrite / Correction Logs
5. User Feedback
6. KPI Monitoring
7. Sidecar / Anomaly Detection
8. Data Quality Gates
9. Model Evaluation Results
10. Golden Question Test Results
11. Security Test Results
12. Domain Knowledge / Dictionary Changes
13. Human Analyst Corrections
14. Operational / System Metrics

منابع جدید باید بدون تغییر در قرارداد شورا قابل اضافه شدن باشند.

---

## 5. Evidence Package Contract

نمونه‌ی canonical:

```yaml
evidence_package:
  schema_version: "1.0"

  package_id: "EP-2026-08-19-000001"
  created_at: "2026-08-19T20:00:00+03:30"

  trigger:
    type: "accuracy_degradation"
    severity: "medium"
    detected_at: "2026-08-18T10:30:00+03:30"

  context:
    system: "text-to-sql"
    environment: "production"
    domain: "banking"
    affected_capability: "transaction_analytics"
    time_window:
      from: "2026-08-11T00:00:00+03:30"
      to: "2026-08-18T23:59:59+03:30"

  evidence:
    - evidence_id: "EV-001"
      type: "user_feedback"
      source: "feedback_service"
      observed_at: "2026-08-17T14:22:00+03:30"
      observation: "User marked generated answer as incorrect"
      value:
        feedback_type: "incorrect"
      confidence: 0.94
      trace:
        request_id: "REQ-..."
        source_ref: "..."

    - evidence_id: "EV-002"
      type: "sql_correction"
      source: "sql_monitor"
      observed_at: "2026-08-17T14:24:00+03:30"
      observation: "Analyst manually corrected generated SQL"
      value:
        correction_type: "column_mapping"
      confidence: 0.98
      trace:
        request_id: "REQ-..."
        source_ref: "..."

  impact:
    affected_queries: 127
    failed_queries: 43
    estimated_accuracy_drop: 0.18
    business_impact: "medium"

  package_confidence: 0.91

  summary:
    title: "Repeated semantic mapping failures"
    description: >
      Multiple independent signals indicate repeated failures
      in mapping a business concept to the current domain model.

  traceability:
    source_count: 4
    independent_source_count: 3
    immutable_snapshot: true
    evidence_hash: "sha256:..."
```

---

## 6. فیلدهای الزامی

| Field | Required | Description |
|---|---:|---|
| `schema_version` | Yes | نسخه قرارداد |
| `package_id` | Yes | شناسه یکتا |
| `created_at` | Yes | زمان ایجاد |
| `trigger` | Yes | دلیل تشکیل بسته |
| `context` | Yes | زمینه و scope |
| `evidence` | Yes | فهرست شواهد |
| `impact` | Yes | اثر مشاهده‌شده |
| `package_confidence` | Yes | اطمینان کلی |
| `summary` | Yes | خلاصه قابل فهم |
| `traceability` | Yes | اطلاعات audit |

---

## 7. Trigger Contract

Trigger توضیح می‌دهد چرا این Evidence Package ساخته شده است.

نمونه انواع:

- `accuracy_degradation`
- `repeated_user_correction`
- `golden_test_failure`
- `data_quality_regression`
- `schema_change`
- `new_domain_term`
- `security_signal`
- `anomaly_detected`
- `manual_escalation`

Trigger به‌تنهایی اثبات مشکل نیست؛ فقط آغاز فرایند جمع‌آوری شواهد است.

---

## 8. Evidence Contract

هر Evidence حداقل باید شامل موارد زیر باشد:

```yaml
evidence_id:
type:
source:
observed_at:
observation:
value:
confidence:
trace:
```

### اصل مهم

`observation` باید تا حد امکان توصیفی باشد، نه تفسیری.

بد:

```text
The domain dictionary is wrong.
```

خوب:

```text
43 of 127 affected queries required manual correction
in semantic-to-column mapping.
```

دلیل: تفسیر باید در مرحله Hypothesis Generation انجام شود، نه در Evidence Layer.

---

## 9. استقلال منابع

برای جلوگیری از self-confirmation، Evidence Package باید بین:

- تعداد کل منابع
- تعداد منابع مستقل

تفاوت قائل شود.

مثلاً:

```yaml
source_count: 4
independent_source_count: 3
```

چهار log از یک pipeline واحد لزوماً چهار شاهد مستقل محسوب نمی‌شوند.

### Baseline Rule

نسخه 1.0 پیشنهاد می‌کند:

- حداقل 2 منبع مستقل برای ورود به شورا.
- اگر فقط یک منبع وجود دارد، package می‌تواند ذخیره شود اما باید با وضعیت `insufficient_evidence` علامت‌گذاری شود.
- شواهد کم‌اعتماد باید صریحاً مشخص شوند.

---

## 10. Confidence

`package_confidence` نشان‌دهنده‌ی اطمینان به **کیفیت و کفایت شواهد** است، نه احتمال درست بودن یک فرضیه.

این دو نباید با هم قاطی شوند.

### Evidence Confidence

```text
How reliable is this observation?
```

### Package Confidence

```text
How strong and sufficient is the complete evidence package?
```

### Hypothesis Confidence

```text
How strongly does the evidence support a proposed explanation?
```

این سه مقدار در سه مرحله‌ی متفاوت زندگی می‌کنند.

---

## 11. Validation Rules

Evidence Validator حداقل باید موارد زیر را بررسی کند:

### V-001 — Schema

Package باید مطابق schema نسخه‌ی اعلام‌شده باشد.

### V-002 — Identity

`package_id` باید unique باشد.

### V-003 — Trigger

Trigger معتبر و دارای timestamp باشد.

### V-004 — Evidence Minimum

حداقل یک Evidence معتبر وجود داشته باشد.

### V-005 — Independent Sources

برای `council_ready` حداقل دو منبع مستقل لازم است.

### V-006 — Traceability

هر Evidence باید trace قابل بررسی داشته باشد.

### V-007 — Temporal Consistency

زمان Evidenceها باید با time window سازگار باشد، مگر اینکه صراحتاً خارج از window تعریف شده باشند.

### V-008 — Confidence

برای ورود عادی به شورا، baseline نسخه 1.0:

```text
package_confidence >= 0.60
```

اما این threshold باید configurable باشد.

### V-009 — Immutability

پس از پذیرش، Evidence Package نباید درجا mutate شود.

هر اصلاح باید package جدید یا version جدید ایجاد کند.

### V-010 — No Decision Leakage

Evidence نباید شامل تصمیم نهایی یا تغییر پیشنهادی به‌عنوان fact باشد.

---

## 12. وضعیت‌های چرخه عمر

```text
RAW
 │
 ▼
COLLECTING
 │
 ▼
BUILT
 │
 ▼
VALIDATING
 ├──────────────► REJECTED
 │
 ▼
ACCEPTED
 │
 ▼
COUNCIL_READY
 │
 ▼
CONSUMED
```

`REJECTED` باید علت رد را ذخیره کند.

نمونه:

```yaml
validation:
  status: "rejected"
  reasons:
    - "Only one independent evidence source"
    - "Missing trace reference"
```

---

## 13. Evidence Summary

Summary برای خوانایی انسانی و مصرف سریع مدل است؛ اما جای Evidence را نمی‌گیرد.

نمونه:

```yaml
summary:
  title: "Repeated semantic mapping failures"

  description: >
    A statistically significant increase in manual SQL corrections
    was observed for a subset of transaction analytics queries.

  key_findings:
    - "127 queries affected"
    - "43 required manual correction"
    - "3 independent evidence sources"
```

اصل:

> Summary is a view over evidence, not a replacement for evidence.

---

## 14. Impact Contract

Impact باید تا حد امکان observation-based باشد.

موارد پیشنهادی:

- تعداد درخواست‌های تحت تأثیر
- نرخ خطا
- تغییر KPI
- شدت اثر
- تعداد کاربران تحت تأثیر
- business impact
- operational impact
- security impact
- data quality impact

Evidence Package نباید business impact را بدون evidence به‌صورت قطعی اعلام کند.

---

## 15. Traceability

هر بسته باید قابلیت برگشت به منبع اصلی را داشته باشد.

مسیر مورد انتظار:

```text
Council Proposal
      ↓
Winning Hypothesis
      ↓
Evidence Package
      ↓
Evidence ID
      ↓
Source Reference
      ↓
Original Event / Request / Metric
```

این مسیر برای Audit حیاتی است.

---

## 16. Immutability و Hash

پس از `ACCEPTED` شدن بسته، پیشنهاد می‌شود snapshot آن immutable شود.

نمونه:

```yaml
traceability:
  immutable_snapshot: true
  evidence_hash: "sha256:..."
```

هدف hash:

- تشخیص تغییر
- audit
- reproducibility
- مقایسه نسخه‌ها

Hash به‌تنهایی امنیت کامل ایجاد نمی‌کند و باید همراه با کنترل دسترسی و storage مناسب استفاده شود.

---

## 17. Separation of Concerns

### Evidence Collector

سیگنال می‌گیرد.

### Evidence Builder

سیگنال‌ها را correlate، normalize و package می‌کند.

### Evidence Validator

بررسی می‌کند package برای مصرف شورا معتبر هست یا نه.

### Hypothesis Generator

از Evidence Package فرضیه تولید می‌کند.

### Council / Debate Engine

فرضیه‌ها را نقد و ارزیابی می‌کند.

### Proposal Builder

نتیجه را به Knowledge Change Proposal تبدیل می‌کند.

### Governance Layer

تأیید انسانی، PR، CI/CD و انتشار را مدیریت می‌کند.

---

## 18. سناریوی واقعی

فرض کنید کاربران درباره یک مفهوم بانکی مشخص سؤال می‌پرسند.

در یک بازه هفت‌روزه:

- 127 query مرتبط شناسایی شده.
- 43 query توسط تحلیلگر اصلاح شده.
- KPI دقت برای این دسته کاهش یافته.
- Sidecar anomaly detector افزایش خطا را گزارش کرده.
- چند feedback کاربر نیز پاسخ‌ها را incorrect علامت زده‌اند.

Evidence Builder این سیگنال‌ها را به یک Evidence Package تبدیل می‌کند.

شورا هنوز حق ندارد بگوید:

> «مشکل قطعاً از dictionary است.»

بلکه Hypothesis Generator می‌تواند فرضیه‌هایی مانند این بسازد:

1. Domain Dictionary Coverage Gap
2. Semantic Mapping Failure
3. Data Quality Regression
4. SQL Generation Failure

سپس ایجنت‌ها این فرضیه‌ها را بررسی می‌کنند.

در نهایت یک فرضیه برنده می‌شود و Proposal Builder پیشنهاد تغییر را می‌سازد.

---

## 19. اصل بسیار مهم معماری

```text
Evidence
   ≠
Hypothesis
   ≠
Decision
   ≠
Change
```

این چهار مفهوم باید جدا باقی بمانند.

### Evidence

چه چیزی مشاهده شد؟

### Hypothesis

چرا ممکن است اتفاق افتاده باشد؟

### Decision

کدام فرضیه و چه اقدامی ارزش پیگیری دارد؟

### Change

چه چیزی واقعاً در سیستم تغییر می‌کند؟

این جداسازی یکی از مهم‌ترین کنترل‌های معماری برای محیط‌های حساس است.

---

## 20. Anti-Patterns

### A-001 — AI Opinion as Evidence

مدل نباید نظر خودش را به‌عنوان evidence ثبت کند.

### A-002 — Evidence Contamination

Evidence نباید با hypothesis مخلوط شود.

### A-003 — Single-Source Certainty

یک منبع نباید بدون qualification باعث تصمیم قطعی شود.

### A-004 — Mutable Evidence

بسته پذیرفته‌شده نباید silently تغییر کند.

### A-005 — Direct Production Mutation

Evidence Package نباید مستقیماً باعث تغییر production شود.

### A-006 — Confidence Confusion

Confidence مربوط به evidence نباید به‌عنوان probability of hypothesis تفسیر شود.

---

## 21. Non-Functional Requirements

### Auditability

هر نتیجه باید قابل برگشت به شواهد باشد.

### Reproducibility

با همان snapshot باید بتوان package را دوباره بررسی کرد.

### Model Independence

تعویض LLM نباید contract را تغییر دهد.

### Source Independence

اضافه شدن Jira، Splunk یا ابزار جدید نباید شورا را مجبور به تغییر کند.

### Versionability

Schema باید version داشته باشد.

### Extensibility

Evidence typeهای جدید باید بدون breaking change قابل اضافه شدن باشند.

### Security

اطلاعات حساس باید قبل از ورود به شورا طبق سیاست‌های امنیتی sanitize یا redact شوند.

### Privacy

Evidence Package نباید بیش از نیاز، داده‌ی شخصی یا حساس نگه دارد.

---

## 22. Security Boundary

قبل از Council:

```text
Raw Data
   ↓
Access Control
   ↓
PII / Sensitive Data Filtering
   ↓
Evidence Builder
   ↓
Evidence Package
```

شورا نباید دسترسی مستقیم و نامحدود به منابع خام production داشته باشد.

این تصمیم عمداً سطح blast radius را کاهش می‌دهد.

---

## 23. Versioning

Schema از Semantic Versioning استفاده می‌کند:

```text
MAJOR.MINOR
```

مثلاً:

```text
1.0
1.1
2.0
```

افزودن optional field معمولاً minor change است.

تغییر semantic فیلدهای اصلی یا حذف field اجباری major change است.

---

## 24. Decision Record

### Decision

Evidence Package به‌عنوان قرارداد رسمی بین Evidence Builder و Council تعریف می‌شود.

### Alternatives Considered

**A — ارسال مستقیم raw logs به شورا**

رد شد؛ coupling و ambiguity زیاد است.

**B — ارسال summary متنی**

رد شد؛ traceability و machine-readability ضعیف است.

**C — Evidence Package ساختاریافته**

انتخاب شد؛ قابل audit، versionable و technology-independent است.

---

## 25. Trade-offs

### مزایا

- استقلال از مدل
- auditability
- modularity
- reproducibility
- امکان اضافه کردن sourceهای جدید
- کنترل بهتر hallucination
- مرزبندی روشن بین fact و reasoning

### هزینه‌ها

- ساخت Evidence Builder
- نیاز به schema governance
- storage برای snapshotها
- پیچیدگی validation
- نیاز به مدیریت version

این هزینه‌ها در برابر ارزش governance در یک سیستم بانکی قابل توجیه‌اند.

---

## 26. Future Evolution

نسخه‌های آینده می‌توانند اضافه کنند:

- Evidence Graph
- Causal Evidence Links
- Statistical Significance
- Evidence Deduplication
- Temporal Correlation
- Evidence Quality Score
- Automated Counter-Evidence Search
- Historical Evidence Memory

اما این قابلیت‌ها نباید contract پایه را بی‌دلیل پیچیده کنند.

---

## 27. Contract Summary

```text
INPUT
  heterogeneous operational signals

        ↓

EVIDENCE BUILDER
  normalize
  correlate
  aggregate
  summarize
  trace

        ↓

EVIDENCE PACKAGE
  immutable
  versioned
  auditable
  model-independent

        ↓

VALIDATOR
  schema
  traceability
  independence
  confidence
  temporal consistency

        ↓

OUTPUT
  COUNCIL_READY Evidence Package
```

---

## 28. Definition of Done

Evidence Package زمانی آماده‌ی ادغام در معماری است که:

- [ ] Schema نسخه 1.0 تعریف شده باشد.
- [ ] JSON/YAML validation schema ساخته شده باشد.
- [ ] Trigger taxonomy تعریف شده باشد.
- [ ] Evidence types اولیه مشخص شده باشند.
- [ ] Traceability contract پیاده شود.
- [ ] Validation rules automated شوند.
- [ ] Immutable snapshot ایجاد شود.
- [ ] حداقل یک سناریوی واقعی end-to-end تست شود.
- [ ] rejected package behavior تست شود.
- [ ] schema versioning تست شود.
- [ ] security / sensitive-data filtering مشخص شود.

---

## 29. Final Architectural Position

Evidence Package «مغز» شورا نیست.

«حافظه» شورا هم نیست.

و حتی «هوش» شورا نیست.

Evidence Package **زمین بازی استاندارد و قابل اعتماد برای استدلال شورا** است.

اگر این قرارداد درست باشد، می‌توانیم:

- Hypothesis Generator را تغییر دهیم،
- LLM را عوض کنیم،
- تعداد Agentها را تغییر دهیم،
- Debate Engine را بازطراحی کنیم،
- منابع evidence جدید اضافه کنیم،

بدون اینکه هسته‌ی قرارداد شکسته شود.

و مهم‌تر از همه:

> **شورا هرگز نباید بگوید «من فکر می‌کنم». شورا باید بتواند نشان دهد «این شواهد باعث شد این فرضیه را بررسی کنم».**
