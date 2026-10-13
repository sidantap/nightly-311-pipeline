"""Export the numbers the dashboard needs to site/data.json."""
from __future__ import annotations

import json

from ml.common import ARTIFACTS
from .warehouse import ROOT, connect, log

OUT = ROOT / "site" / "data.json"


def rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def run() -> dict:
    con = connect()
    data = {
        "generated_at": con.execute("select strftime(now(), '%Y-%m-%d %H:%M UTC')").fetchone()[0],
        "runs": rows(con, """select run_id, strftime(started_at, '%Y-%m-%d %H:%M') as started,
                                    status, round(epoch(finished_at - started_at)) as seconds
                             from meta.runs where finished_at is not null
                             order by started_at desc limit 14"""),
        "watermarks": rows(con, "select source, watermark from meta.watermarks order by source"),
        "kpis": rows(con, """select
                 count(*) filter (where created_date_key >= current_date - 30) as requests_30d,
                 count(*) filter (where is_open) as open_now,
                 round(median(days_to_close) filter (where created_date_key >= current_date - 90), 1) as median_days_to_close_90d
               from gold.fct_service_requests""")[0],
        "daily": rows(con, """select strftime(day, '%Y-%m-%d') as day, sum(requests) as requests,
                                     any_value(precip_in) as precip_in, any_value(temp_max_f) as temp_max_f
                              from gold.fct_daily_requests_weather
                              where day >= current_date - 90 and day < current_date
                              group by day order by day"""),
        "categories": rows(con, """select t.category, count(*) as requests,
                                          round(median(f.days_to_close), 1) as median_days_to_close
                                   from gold.fct_service_requests f join gold.dim_request_type t using (request_type_key)
                                   where f.created_date_key >= current_date - 30
                                   group by 1 order by 2 desc"""),
        "quarantine": rows(con, """select dq_reason, count(*) as rows
                                   from quarantine.svc_requests_quarantine group by 1 order by 2 desc"""),
        "quarantine_total": con.execute("select count(*) from quarantine.svc_requests_quarantine").fetchone()[0],
        "live_metrics": rows(con, """select strftime(scored_on, '%Y-%m-%d') as day, rows, accuracy,
                                            macro_precision, macro_recall, macro_f1
                                     from ml.live_metrics order by scored_on"""),
        "predictions": rows(con, """select c.complaint_id, strftime(c.received_date, '%Y-%m-%d') as received,
                                           c.make, c.model, c.model_year, left(c.description, 220) as text,
                                           c.component_group as actual, p.predicted_group as predicted,
                                           p.confidence
                                    from ml.predictions p join silver.complaints c using (complaint_id)
                                    where c.component_group is not null
                                    order by c.received_date desc, c.complaint_id desc limit 12"""),
    }
    offline = ARTIFACTS / "offline_metrics.json"
    data["offline_metrics"] = json.loads(offline.read_text()) if offline.exists() else None
    con.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, default=str, indent=1))
    log("export", "dashboard data written", path=str(OUT.relative_to(ROOT)))
    return {"days": len(data["daily"])}


if __name__ == "__main__":
    run()
