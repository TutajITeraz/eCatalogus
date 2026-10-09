-- Data fixes applied to the restored legacy eCLLA database (a scratch copy of
-- ispan_eclla) before running scripts/convert_legacy_db.py. They resolve rows
-- that violate UNIQUE constraints of the current schema.

-- Unused duplicate of project 1 ("CLLA"); indexerapp_msprojects references only id 1.
DELETE FROM indexerapp_projects
WHERE id = 2 AND NOT EXISTS (SELECT 1 FROM indexerapp_msprojects WHERE project_id = 2);

-- Align the project name with the master eCatalogus project list.
UPDATE indexerapp_projects SET name = 'eCLLA' WHERE id = 1;

-- Typo: id 138 covers the 13th century (1235-1265) but was labelled like id 124.
UPDATE time_reference SET time_description = 'XIII med'
WHERE id = 138 AND time_description = 'XII med' AND century_from = 13;

-- Every eCLLA manuscript is shown in the catalogue (also the 43 edition/PRG ones whose
-- content would otherwise be hidden from the /api/content/ table).
UPDATE manuscripts SET display_as_main = 1;
