#!/usr/bin/env python3
"""Example generator for diagram_kit: four pages about a fictional web shop.

    python example_diagrams.py --out OUTDIR        # writes 01..04 PDFs to OUTDIR
    python example_diagrams.py --list

Copy this file next to diagram_kit.py in a project (e.g. tools/), replace the content, and
keep the shape: improvement points first, one function per page, SPECS, then kit.main().
Every number and finding below is invented for the demo.
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
for folder in (HERE, HERE.parent / "scripts"):
    if (folder / "diagram_kit.py").is_file():
        sys.path.insert(0, str(folder))
        break
import diagram_kit as kit  # noqa: E402  # pyright: ignore[reportMissingImports]

M = kit.MARGIN
kit.KIND_NAMES.update(core="backend package", app="front end or worker",
                      platform="database, queue, network")

kit.register(
    kit.Improvement("N-01", "high", "storage · OrderRepository.list_for",
                    "listing orders runs one query per order line (N+1); 50 orders take 1.8 s",
                    "load the lines with selectinload and add a query-count test",
                    "N+1 queries"),
    kit.Improvement("N-02", "high", "worker · payments",
                    "Stripe calls have no timeout; a hung call holds a worker slot until restart",
                    "10 s timeout, retries with backoff, an alert on queue age",
                    "no Stripe timeout"),
    kit.Improvement("N-03", "low", "CI", "no type checking; mypy finds 40 errors locally",
                    "fix them and run mypy on domain and api in CI", "no type checks"),
    kit.Improvement("L-1", "medium", "worker · tasks",
                    "jobs are not idempotent: a retried invoice job can email twice",
                    "idempotency keys stored with each job's result", "jobs not idempotent"),
    kit.Improvement("L-2", "low", "web · build",
                    "the bundle is 2.4 MB; the catalogue loads everything up front",
                    "split routes and load checkout lazily", "2.4 MB bundle"),
)


def overview(p):
    web = p.package(100, 104, 460, 130, "app", "web", "SPA",
                    "Shop front end: catalogue, cart, checkout.", ["pages · components · client"],
                    ["TypeScript", "React"], "8.1k lines · 140 tests", [("L-2", "2.4 MB bundle")])
    api = p.package(100, 304, 460, 130, "core", "api", "HTTP",
                    "FastAPI routes, auth, validation, OpenAPI.", ["routes · auth · schemas"],
                    ["FastAPI", "pydantic"], "4.2k lines · 210 tests")
    worker = p.package(640, 304, 460, 130, "app", "worker", "jobs",
                       "Invoices, emails and stock sync off a queue.", ["tasks · schedules"],
                       ["Celery", ("redis", "platform")], "1.9k lines · 64 tests",
                       [("N-02", "no Stripe timeout"), ("L-1", "not idempotent")])
    storage = p.package(370, 504, 460, 130, "core", "storage", "adapters",
                        "SQLAlchemy repositories behind the domain's ports.",
                        ["repositories · migrations"], [("PostgreSQL", "platform"), "SQLAlchemy"],
                        "2.6k lines · 120 tests", [("N-01", "N+1 queries")])
    domain = p.package(370, 704, 460, 130, "core", "domain", "business rules",
                       "Orders, pricing, stock and the ports; no I/O.",
                       ["orders · pricing · stock · ports"], [], "3.3k lines · 380 tests")

    p.arrow((web.cx, web.b), (web.cx, api.y), label="HTTP / JSON",
            label_at=(web.cx + 8, 272), label_anchor="start")
    p.arrow((430, api.b), (430, storage.y))
    p.arrow((770, worker.b), (770, storage.y))
    p.arrow((storage.cx, storage.b), (storage.cx, domain.y), label="implements ports",
            label_at=(storage.cx + 8, 672), label_anchor="start")
    p.arrow((api.x, 370), (70, 370), (70, domain.cy), (domain.x, domain.cy))
    p.arrow((worker.r, 370), (1130, 370), (1130, domain.cy), (domain.r, domain.cy))

    p.card(1200, 104, 347, None, "Reading this page", [
        "Arrows point from a package to what it uses.",
        "domain is at the bottom: everything depends on it, it depends on nothing.",
        "storage implements the domain's ports (dependency inversion).",
    ], dot="#34d399")
    p.card(1200, 300, 347, None, "Stack and CI", [
        "Python 3.12 backend, TypeScript front end",
        "PostgreSQL 16, Redis as the job queue",
        "CI: lint, tests, migrations dry run",
        ("badge", "N-03", "no type checks in CI"),
    ], dot="#94a3b8")
    p.card(1200, 480, 347, None, "Start reading here", [
        "api/routes/orders.py: placing an order",
        "domain/orders.py: the order rules",
        "worker/tasks/invoices.py: after payment",
    ], dot="#22d3ee")
    p.cards(M, None, p.W - 2 * M, None, [
        ("Rule 1 · dependencies point down", "#34d399", [
            "web → api → domain; adapters depend on the domain, never the reverse"]),
        ("Rule 2 · no I/O in the domain", "#a78bfa", [
            "databases, queues and HTTP live behind ports"]),
        ("Rule 3 · one transaction per request", "#22d3ee", [
            "unit_of_work() wraps every write; jobs start their own"]),
    ], bottom=p.bottom)
    p.legend(M, p.legend_y, ["app", "core", "platform", "external"])


def lifecycle(p):
    lanes = [
        ("web · browser", "app", [("checkout form", ["validates fields"]),
                                  ("client.post('/orders')", ["JSON body, auth cookie"])]),
        ("api · FastAPI", "core", [("auth", ["session → user"]),
                                   ("schema check", ["pydantic model"]),
                                   ("OrderService.place", ["domain call"]),
                                   ("201 Created", ["order id + total"])]),
        ("domain + storage", "core", [("price the cart", ["PricingPolicy"]),
                                      ("reserve stock", ["StockPolicy"]),
                                      ("save the order", ["one transaction"]),
                                      ("enqueue invoice", ["after commit"])]),
        ("worker · Celery", "app", [("issue invoice", ["InvoiceService"]),
                                    ("charge card", ["Stripe API"]),
                                    ("send email", ["SMTP"])]),
    ]
    cards = p.cards(M, None, p.W - 2 * M, None, [
        ("Transactions", "#34d399", ["the order and its stock reservation commit together",
                                     "the invoice job is enqueued only after the commit"]),
        ("Failure handling", "#fb7185", ["domain errors map to 409 and 422",
                                         "Stripe failures retry in the worker, not the request"]),
        ("Observability", "#22d3ee", ["one request id from browser to worker",
                                      "queue age is not alerted on yet (N-02)"]),
    ], bottom=p.bottom)
    # The lanes share the height above the cards; boxes sit in the middle of their lane.
    lane_h = (cards.y - 20 - p.top) / len(lanes)
    boxes = []
    for i, (title, kind, steps) in enumerate(lanes):
        group = p.group(M, p.top + i * lane_h, p.W - 2 * M, lane_h - 16, title)
        y = group.y + (group.h - 92) / 2 + 6
        row, x = [], M + 30
        for name, lines in steps:
            box = p.box(x, y, 260, 92, kind, name, lines)
            if row:
                p.arrow((row[-1].r, box.cy), (box.x, box.cy))
            row.append(box)
            x += 300
        boxes.append(row)
        if title.startswith("worker"):
            p.badge(group.r - 12, group.y + 18, "N-02", "Stripe call has no timeout",
                    anchor="end")
            p.badge(group.r - 12, group.y + 40, "L-1", "a retry can email twice", anchor="end")
    # Hand-offs between lanes run down through the gap between the groups, then left.
    for (lane, step), (next_lane, next_step), label, dash in [
            ((0, 1), (1, 0), "HTTP", None), ((1, 2), (2, 0), "call", None),
            ((2, 3), (3, 0), "queue", "5,4")]:
        a, b = boxes[lane][step], boxes[next_lane][next_step]
        gap_y = p.top + next_lane * lane_h - 8
        p.arrow((a.cx, a.b), (a.cx, gap_y), (b.cx, gap_y), (b.cx, b.y), dash=dash,
                label=label, label_at=(a.cx + 8, a.b + 22), label_anchor="start")
    p.legend(M, p.legend_y, ["app", "core"])


def interfaces(p):
    rows = ["web", "api", "worker", "storage", "domain"]
    cols = ["api", "domain", "storage"]
    cells = {
        ("web", "api"): ["POST /orders · GET /orders", "POST /auth/login",
                         "client generated from OpenAPI"],
        ("api", "domain"): ["OrderService.place(cart, user)", "PricingPolicy · StockPolicy",
                            "domain errors → HTTP 409 / 422"],
        ("api", "storage"): ["unit_of_work()", "OrderRepository.list_for(user)"],
        ("worker", "domain"): ["InvoiceService.issue(order_id)"],
        ("worker", "storage"): ["OrderRepository.get(id)", "unit_of_work()"],
        ("storage", "domain"): ["implements OrderRepository and StockRepository",
                                "maps rows to entities"],
    }
    forbidden = {
        ("web", "domain"): ["× never", "business rules run on", "the server only"],
        ("web", "storage"): ["× never", "the database is private", "to the backend"],
    }
    cards = p.cards(M, None, p.W - 2 * M, None, [
        ("HTTP boundary", "#22d3ee", ["the browser sees only the OpenAPI contract"]),
        ("Ports and adapters", "#a78bfa", ["storage implements ports the domain defines"]),
        ("Jobs", "#34d399", ["the worker reuses domain services, never api routes"]),
    ], bottom=p.bottom)
    p.matrix(M, p.top, cards.y - 24, rows, cols, cells,
             kinds={"web": "app", "worker": "app"},
             layer={"web": 4, "api": 3, "worker": 3, "storage": 1, "domain": 0},
             forbidden=forbidden)
    p.legend(M, p.legend_y, ["app", "core"], badges=False)


def improvements(p):
    kit.improvement_register(p, [
        ("external", "CI · repository", ["N-03"]),
        ("app", "web", ["L-2"]),
        ("core", "api", []),
        ("app", "worker", ["N-02", "L-1"]),
        ("core", "storage", ["N-01"]),
        ("core", "domain", []),
    ], ["N-01", "N-02", "N-03", "L-1", "L-2"], [
        "N-01 first: it is the slowest page today.",
        "N-02 before the next sale weekend; L-x need plans of their own.",
    ])
    p.legend(M, p.legend_y, ["external", "app", "core"])


SPECS = [
    kit.Spec("01-overview", "System overview", "Packages and dependencies of a fictional shop.",
             overview),
    kit.Spec("02-order-lifecycle", "Placing an order", "One POST /orders, from browser to worker.",
             lifecycle),
    kit.Spec("03-interfaces", "Interfaces between packages",
             "What each row uses from each column.", interfaces),
    kit.Spec("04-improvement-points", "Improvement points",
             "The badges on pages 01 to 03, in full.", improvements),
]

if __name__ == "__main__":
    kit.main(SPECS, Path(tempfile.gettempdir()) / "diagram-kit-example",
             project="acme-shop", generator="example_diagrams.py",
             footer_right="a fictional system, drawn to demo diagram_kit")
