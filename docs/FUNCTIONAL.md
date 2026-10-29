# alphaview — Functional Document

## 1. Product purpose

alphaview is a **Market Intelligence & Trend Discovery Agent**. It scouts the web for **structural market imbalances** — topics where consumer demand is high or accelerating while existing supply is weak, outdated or absent — and turns them into investor-grade startup theses backed by quantitative metrics.

**Primary users:** founders searching for what to build, VCs/angels validating theses, product strategists and corporate innovation teams.

## 2. Core capabilities

| # | Capability | What the user gets |
|---|---|---|
| F1 | **Targeted web crawling** | Signals from Reddit, Hacker News and Stack Exchange (questions, complaints, wishes), expanded with demand-intent phrases |
| F2 | **Gap identification** | Pain-point clusters scored 0–100 on demand vs. supply asymmetry |
| F3 | **Strategic feasibility** | Per-gap startup concept: thesis, value proposition, ICP, wedge, execution, GTM, moat, risks, kill criteria |
| F4 | **External data integration** | Hard metrics (search volume, CPC, trend growth, SERP density, owned-site data) attached to each gap |
| F5 | **Analytics-tool connectors** | Plug-in integrations: Google Analytics 4, Google Search Console, DataForSEO, SerpApi (Google Trends + SERP), Semrush |
| F6 | **User accounts & self-service integrations** | Register/login, connect own tools (OAuth or API key), test, query and disconnect them |

## 3. User journeys

### 3.1 Sign up / sign in
1. User registers with name, email, password (≥10 chars). A personal **workspace** is created automatically.
2. Login issues a session (12 h). Protected pages redirect to `/login?next=...`.

### 3.2 Connect analytics tools (F5, F6)
1. **Integrations** page lists available tools with capabilities (search volume, trend, SERP competition, owned site).
2. **API-key tools** (DataForSEO, SerpApi, Semrush): user enters credentials + optional config → alphaview **tests the credentials live** → saved encrypted.
3. **OAuth tools** (GA4, Search Console): user enters property ID / site URL → redirected to Google consent → back to Integrations with a success banner.
4. For each connection the user can **Test** (re-validate), **Query** (ad-hoc keyword lookup — "search for the details"), or **Disconnect**.

### 3.3 Run a discovery (F1–F4)
1. On **Discovery**, the user enters a niche/persona/problem (e.g. *"small accounting firms"*) and selects sources.
2. A run is created and progresses through: `queued → crawling → analyzing → enriching → synthesizing → completed` (or `failed`). The run page shows a live stepper.
3. On completion the run page shows ranked **opportunity cards** (gap score, mentions, velocity, demand-intent %, supply %, search volume, confidence).

### 3.4 Review an opportunity (F3)
The opportunity page shows:
- **Key takeaways** (bolded metrics), gap score and confidence.
- **Metric panel:** mentions, engagement, velocity, negative sentiment, demand intent, complaint, supply, unanswered ratios, plus external metrics from connectors.
- **Gap-score components** chart (demand volume, velocity, pain intensity, supply density, supply quality).
- **Strategy:** thesis, value proposition, target audience, wedge, execution strategy, go-to-market, moat, risks, kill criteria.
- **Evidence:** top source threads with links, source, intent and engagement.

## 4. Business rules

| Rule | Detail |
|---|---|
| BR1 Intent taxonomy | Each signal is classified (first match wins): **wish** ("is there a tool", "I'd pay"), **alternative** ("alternative to", "switched from"), **complaint** ("frustrating", "too expensive"), **solution** ("I built", "Show HN"), else **discussion** |
| BR2 Demand intent | wish + alternative + complaint |
| BR3 Supply proxy | share of *solution* posts, ad competition, SERP result count; unanswered Stack Exchange questions count as unmet supply |
| BR4 Incumbent weakness | higher complaint ratio lowers the supply-quality term (weak incumbents widen the gap) |
| BR5 Velocity | ratio of signals in the recent half of the window vs. the older half, multiplied by (1 + Google-Trends growth) when available |
| BR6 Confidence | 60 % sample size (saturates at 60 mentions) + 40 % connector coverage (saturates at 2 connectors) |
| BR7 Ranking | Top `LLM_MAX_OPPORTUNITIES` (default 6) clusters by gap score are synthesized and persisted |
| BR8 Quotas | 20 discovery runs / workspace / hour; 10 registrations / IP / hour; 10 login attempts / IP+email / 15 min |
| BR9 Graceful degradation | A failing connector never fails a run — its error is stored on the connection. Without an LLM key, heuristic synthesis is used and labelled |
| BR10 Data retention | Raw signals expire after 180 days (ClickHouse TTL); opportunities persist |

## 5. Gap score definition

$$
\text{raw} = \frac{D_{volume}\cdot D_{velocity}\cdot I_{intensity}}{S_{density}\cdot S_{quality}}, \qquad
\text{GapScore} = 100\,(1 - e^{-\text{raw}/2.5})
$$

| Term | Formula |
|---|---|
| $D_{volume}$ | $\log_{10}(1 + 10\cdot mentions + engagement/10 + search\_volume + gsc\_impressions/10)$ |
| $D_{velocity}$ | $\text{clamp}(velocity \cdot (1 + \text{clamp}(trend\_growth, -0.9, 3)), 0.25, 6)$ |
| $I_{intensity}$ | $0.1 + 0.35\cdot neg\_sentiment + 0.45\cdot demand\_ratio + 0.2\cdot unanswered\_ratio$ |
| $S_{density}$ | $0.3 + 1.5\cdot supply\_ratio + competition + \log_{10}(1+serp\_results)/10$ |
| $S_{quality}$ | $1 - 0.5\cdot complaint\_ratio$ |

Interpretation: **≥70** strong asymmetry, **45–70** worth validating, **<45** crowded or weak demand.

## 6. Output style (strategist)

- Analytical, precise, objective; written for founders and investors.
- Every claim grounded in provided metrics/evidence; metrics in **bold**.
- No generic business advice; focus on data-driven asymmetries.
- Thin data must be acknowledged in risks.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | API p95 < 200 ms for reads; discovery run typically 1–3 min |
| Scalability | Stateless API and workers scale horizontally; target millions of users (see HLD) |
| Availability | Runs survive worker crashes (Temporal durable execution, 3 retries per stage) |
| Security | See TECHNOLOGY §6 |
| Compliance | Prefer official/public APIs; identifiable user handles are not stored; respect source rate limits |

## 8. Out of scope (current release)

Team invites/RBAC, SSO, billing, scheduled/recurring runs, alerts, PDF/Notion export, Playwright crawling of JS-heavy sites, embeddings-based clustering. See roadmap in TECHNOLOGY §7.
