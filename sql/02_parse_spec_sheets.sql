-- Product Data Copilot, step 2: turn spec-sheet PDFs into a table (Document Intelligence).
-- Before running: upload every PDF in spec_sheets/ to the volume
--   Catalog > workspace > product_data > Volumes > spec_sheets > Upload to this volume
-- If ai_parse_document or ai_extract is not available in your workspace, run 02b_fallback_spec_values.sql instead.
USE workspace.product_data;

-- 2a. Parse each PDF into layout-aware elements (text, tables, titles).
CREATE OR REPLACE TABLE spec_sheets_parsed AS
SELECT path, ai_parse_document(content, map('version', '2.0')) AS parsed
FROM READ_FILES('/Volumes/workspace/product_data/spec_sheets/', format => 'binaryFile', pathGlobFilter => '*.pdf');

-- 2b. Flatten the parsed elements into one text block per document.
CREATE OR REPLACE TABLE spec_sheets_text AS
SELECT path,
       concat_ws('\n', transform(cast(parsed:document:elements AS ARRAY<VARIANT>), e -> cast(e:content AS STRING))) AS doc_text
FROM spec_sheets_parsed;

-- 2c. Extract typed fields with an LLM, constrained to a schema.
CREATE OR REPLACE TABLE spec_extracted
COMMENT 'Specs extracted from spec-sheet PDFs with ai_parse_document + ai_extract.'
AS
SELECT element_at(split(path, '/'), -1) AS source_file,
       cast(x:response:sku:value AS STRING) AS sku,
       cast(x:response:weight_g:value AS INT) AS weight_g,
       cast(x:response:op_temp_min_c:value AS INT) AS op_temp_min_c,
       cast(x:response:op_temp_max_c:value AS INT) AS op_temp_max_c,
       cast(x:response:ip_rating:value AS STRING) AS ip_rating,
       cast(x:response:lifecycle_status:value AS STRING) AS lifecycle_status
FROM (
  SELECT path,
         ai_extract(
           doc_text,
           '{
             "sku": {"type": "string", "description": "Model or SKU code, for example GW-200"},
             "weight_g": {"type": "integer", "description": "Weight in grams"},
             "op_temp_min_c": {"type": "integer", "description": "Minimum operating temperature in Celsius"},
             "op_temp_max_c": {"type": "integer", "description": "Maximum operating temperature in Celsius"},
             "ip_rating": {"type": "string", "description": "Ingress protection rating such as IP67, or null if not rated"},
             "lifecycle_status": {"type": "enum", "labels": ["NPI", "GA", "EOL"],
                                  "description": "GA if generally available, EOL if end of life, NPI if pre-launch"}
           }',
           options => map('version', '2.1')
         ) AS x
  FROM spec_sheets_text
);

-- Check: should return 12 rows, one per spec sheet.
SELECT * FROM spec_extracted ORDER BY sku;
