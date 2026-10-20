-- Fallback for step 2: use this only if ai_parse_document / ai_extract are not available in your workspace.
-- It loads the same values the spec-sheet PDFs contain, so steps 3 onward work unchanged.
USE workspace.product_data;

CREATE OR REPLACE TABLE spec_extracted (
  source_file STRING, sku STRING, weight_g INT, op_temp_min_c INT, op_temp_max_c INT,
  ip_rating STRING, lifecycle_status STRING)
COMMENT 'Specs extracted from spec-sheet PDFs (fallback: loaded directly, not parsed).';
INSERT INTO spec_extracted VALUES
  ('GW-100_spec_sheet.pdf', 'GW-100', 310, -30, 70, 'IP67', 'EOL'),
  ('GW-200_spec_sheet.pdf', 'GW-200', 325, -40, 85, 'IP67', 'GA'),
  ('GW-300_spec_sheet.pdf', 'GW-300', 280, -40, 85, 'IP68', 'GA'),
  ('GW-400_spec_sheet.pdf', 'GW-400', 300, -40, 85, 'IP68', 'NPI'),
  ('CM-10_spec_sheet.pdf', 'CM-10', 180, -20, 70, 'IP54', 'EOL'),
  ('CM-20_spec_sheet.pdf', 'CM-20', 240, -20, 60, 'IP54', 'GA'),
  ('CM-30_spec_sheet.pdf', 'CM-30', 260, -30, 75, 'IP65', 'GA'),
  ('CM-40_spec_sheet.pdf', 'CM-40', 620, -30, 60, 'IP66', 'NPI'),
  ('SN-TEMP_spec_sheet.pdf', 'SN-TEMP', 45, -40, 85, 'IP67', 'GA'),
  ('SN-DOOR_spec_sheet.pdf', 'SN-DOOR', 38, -30, 70, 'IP65', 'GA'),
  ('SN-TPMS_spec_sheet.pdf', 'SN-TPMS', 30, -40, 125, 'IP67', 'GA'),
  ('SN-AIR_spec_sheet.pdf', 'SN-AIR', 95, -20, 60, 'IP54', 'GA');
