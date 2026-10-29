-- View KPI: satu sumber rumus untuk bot, dashboard, dan cek silang.
-- Definisi: yield stasiun (FPY) = ok_first_pass / input_qty; NG rate = 1 - FPY;
-- yield lini = unit OK di Packing / unit masuk Frame Welding; rework rate = unit masuk rework / input_qty.

CREATE OR REPLACE VIEW v_station_daily AS
SELECT CAST(p.date AS DATE) AS date, p.station, s.seq,
       SUM(p.input_qty) AS input_qty, SUM(p.ok_first_pass) AS ok_qty, SUM(p.ng_qty) AS ng_qty,
       SUM(p.ok_first_pass) * 1.0 / SUM(p.input_qty) AS fpy,
       SUM(p.ng_qty) * 1.0 / SUM(p.input_qty) AS ng_rate
FROM production_daily p JOIN dim_station s USING (station)
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW v_line_daily AS
SELECT date,
       MAX(CASE WHEN seq = 1 THEN input_qty END) AS start_qty,
       MAX(CASE WHEN seq = (SELECT MAX(seq) FROM dim_station) THEN ok_qty END) AS good_qty,
       MAX(CASE WHEN seq = (SELECT MAX(seq) FROM dim_station) THEN ok_qty END) * 1.0
         / MAX(CASE WHEN seq = 1 THEN input_qty END) AS line_yield,
       SUM(ng_qty) AS ng_total
FROM v_station_daily GROUP BY date;

CREATE OR REPLACE VIEW v_defect_daily AS
SELECT CAST(d.date AS DATE) AS date, d.station, d.defect_code, f.defect_name, SUM(d.qty) AS qty
FROM defect_log d JOIN dim_defect f USING (defect_code)
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW v_rework_station_daily AS
SELECT CAST(date_in AS DATE) AS date, station_origin AS station,
       SUM(qty) AS rework_qty,
       SUM(CASE WHEN result = 'lulus' THEN qty ELSE 0 END) AS rework_pass_qty,
       SUM(CASE WHEN result = 'scrap' THEN qty ELSE 0 END) AS scrap_qty
FROM rework_log GROUP BY 1, 2;

CREATE OR REPLACE VIEW v_kpi_station_daily AS
SELECT s.date, s.station, s.seq, s.input_qty, s.ok_qty, s.ng_qty, s.fpy, s.ng_rate,
       COALESCE(r.rework_qty, 0) AS rework_qty, COALESCE(r.scrap_qty, 0) AS scrap_qty,
       COALESCE(r.rework_qty, 0) * 1.0 / s.input_qty AS rework_rate
FROM v_station_daily s LEFT JOIN v_rework_station_daily r USING (date, station);
