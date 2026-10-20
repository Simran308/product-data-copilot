-- Product Data Copilot, step 3: trusted foundation, business meaning, and agent tools.
USE workspace.product_data;

-- 3a. Trusted foundation: cleaned SKU gold table with an owner on every row.
CREATE OR REPLACE TABLE sku_gold
COMMENT 'Cleaned SKU master. One row per SKU, with the accountable data owner from product_line_owners.'
AS
SELECT upper(trim(s.sku)) AS sku, trim(s.product_name) AS product_name, s.product_line,
       upper(s.lifecycle_status) AS lifecycle_status, to_date(s.launch_date) AS launch_date,
       s.list_price_usd, s.weight_g, s.op_temp_min_c, s.op_temp_max_c, s.ip_rating,
       o.owner_name, o.owner_email,
       s.product_line <> 'Licenses' AS requires_bom
FROM skus s
LEFT JOIN product_line_owners o ON s.product_line = o.product_line;

ALTER TABLE sku_gold SET TAGS ('domain' = 'product_data', 'tier' = 'gold');

-- Change tracking: every edit to the SKU master is recorded by Delta Change Data Feed.
-- SELECT sku, lifecycle_status, list_price_usd, _change_type, _commit_timestamp
-- FROM table_changes('workspace.product_data.skus', 0) WHERE _change_type <> 'insert';

-- 3b. Spec mismatches: PDF spec sheet vs SKU master, one row per disagreeing field.
CREATE OR REPLACE VIEW spec_mismatches
COMMENT 'Fields where the spec-sheet PDF disagrees with sku_gold.'
AS
WITH pairs AS (
  SELECT g.sku, g.product_name, g.owner_email, e.source_file,
         stack(5,
           'weight_g',         cast(g.weight_g AS STRING),         cast(e.weight_g AS STRING),
           'op_temp_min_c',    cast(g.op_temp_min_c AS STRING),    cast(e.op_temp_min_c AS STRING),
           'op_temp_max_c',    cast(g.op_temp_max_c AS STRING),    cast(e.op_temp_max_c AS STRING),
           'ip_rating',        g.ip_rating,                        e.ip_rating,
           'lifecycle_status', g.lifecycle_status,                 upper(e.lifecycle_status)
         ) AS (field, table_value, spec_sheet_value)
  FROM sku_gold g
  JOIN spec_extracted e ON upper(trim(e.sku)) = g.sku
)
SELECT * FROM pairs WHERE NOT (table_value <=> spec_sheet_value);

-- 3c. One row per SKU with every data quality check. This is the source of truth the agent uses.
CREATE OR REPLACE VIEW sku_data_quality
COMMENT 'Per-SKU data quality. quality_score starts at 100: -40 GA SKU with no BOM, -20 BOM older than 365 days, -20 obsolete component, -10 NRND component, -10 per spec-sheet mismatch.'
AS
WITH bom AS (
  SELECT b.sku,
         count(*) AS bom_lines,
         max(to_date(b.last_updated)) AS bom_last_updated,
         count_if(c.lifecycle = 'Obsolete') AS obsolete_components,
         count_if(c.lifecycle = 'NRND') AS nrnd_components,
         sum(b.qty * c.unit_cost_usd) AS bom_cost_usd
  FROM bom_lines b LEFT JOIN components c ON b.component_id = c.component_id
  GROUP BY b.sku
),
mm AS (SELECT sku, count(*) AS spec_mismatches FROM spec_mismatches GROUP BY sku),
flags AS (
  SELECT g.sku, g.product_name, g.product_line, g.lifecycle_status, g.owner_name, g.owner_email,
         coalesce(bom.bom_lines, 0) AS bom_lines, bom.bom_last_updated, round(bom.bom_cost_usd, 2) AS bom_cost_usd,
         g.requires_bom AND g.lifecycle_status = 'GA' AND bom.sku IS NULL AS missing_bom,
         bom.bom_last_updated < date_sub(current_date(), 365) AS stale_bom,
         coalesce(bom.obsolete_components, 0) AS obsolete_components,
         coalesce(bom.nrnd_components, 0) AS nrnd_components,
         coalesce(mm.spec_mismatches, 0) AS spec_mismatches
  FROM sku_gold g
  LEFT JOIN bom ON g.sku = bom.sku
  LEFT JOIN mm ON g.sku = mm.sku
)
SELECT *,
       greatest(0, 100
         - CASE WHEN missing_bom THEN 40 ELSE 0 END
         - CASE WHEN coalesce(stale_bom, false) THEN 20 ELSE 0 END
         - CASE WHEN obsolete_components > 0 THEN 20 ELSE 0 END
         - CASE WHEN nrnd_components > 0 THEN 10 ELSE 0 END
         - 10 * spec_mismatches) AS quality_score
FROM flags;

-- 3d. Business meaning: a Unity Catalog metric view, so Genie and dashboards share one definition.
-- If your workspace rejects version 1.1, change "version: 1.1" to "version: 0.1" and "fields:" to "dimensions:".
CREATE OR REPLACE VIEW product_data_metrics
WITH METRICS
LANGUAGE YAML
AS $$
version: 1.1
comment: "Product data quality KPIs for SKU, BOM and spec-sheet governance"
source: workspace.product_data.sku_data_quality
fields:
  - name: product_line
    expr: product_line
  - name: lifecycle_status
    expr: lifecycle_status
  - name: owner_name
    expr: owner_name
measures:
  - name: sku_count
    expr: COUNT(1)
  - name: bom_completeness_pct
    expr: ROUND(100.0 * COUNT(1) FILTER (WHERE bom_lines > 0) / NULLIF(COUNT(1) FILTER (WHERE product_line <> 'Licenses'), 0), 1)
  - name: missing_bom_skus
    expr: COUNT(1) FILTER (WHERE missing_bom)
  - name: stale_bom_skus
    expr: COUNT(1) FILTER (WHERE stale_bom)
  - name: skus_with_obsolete_parts
    expr: COUNT(1) FILTER (WHERE obsolete_components > 0)
  - name: spec_mismatch_count
    expr: SUM(spec_mismatches)
  - name: avg_quality_score
    expr: ROUND(AVG(quality_score), 1)
$$;

-- Example: SELECT product_line, MEASURE(avg_quality_score), MEASURE(missing_bom_skus)
--          FROM product_data_metrics GROUP BY product_line;

-- 3e. Unity Catalog functions the agent calls as tools (run on the SQL warehouse).
CREATE OR REPLACE FUNCTION get_data_quality(query STRING COMMENT 'A SKU, a product line (Gateways, Cameras, Sensors, Cables, Accessories, Licenses), or "all"')
RETURNS STRING
COMMENT 'Returns per-SKU data quality checks and quality_score as JSON, lowest score first.'
RETURN (
  SELECT to_json(collect_list(struct(*)))
  FROM (
    SELECT * FROM workspace.product_data.sku_data_quality
    WHERE lower(query) = 'all' OR lower(sku) = lower(query) OR lower(product_line) = lower(query)
    ORDER BY quality_score, sku
  )
);

CREATE OR REPLACE FUNCTION get_sku_details(sku_query STRING COMMENT 'The SKU code, for example CM-20')
RETURNS STRING
COMMENT 'Returns the SKU master record, its BOM lines with component lifecycle, and any spec-sheet mismatches as JSON.'
RETURN (
  SELECT to_json(named_struct(
    'sku', (SELECT first(struct(*)) FROM workspace.product_data.sku_gold g WHERE g.sku = upper(sku_query)),
    'bom', (SELECT collect_list(struct(b.component_id, c.description, c.supplier, c.lifecycle, b.qty, b.bom_revision, b.last_updated))
            FROM workspace.product_data.bom_lines b
            LEFT JOIN workspace.product_data.components c ON b.component_id = c.component_id
            WHERE b.sku = upper(sku_query)),
    'spec_mismatches', (SELECT collect_list(struct(m.field, m.table_value, m.spec_sheet_value, m.source_file))
                        FROM workspace.product_data.spec_mismatches m WHERE m.sku = upper(sku_query))
  ))
);

-- Check: lowest quality SKUs first.
SELECT sku, product_line, lifecycle_status, quality_score, missing_bom, stale_bom, obsolete_components, spec_mismatches
FROM sku_data_quality ORDER BY quality_score, sku;
