# ETL Replication Plan — eCatalogus

## Decyzje architektoniczne

- **UUID**: etapowa migracja (dodaj pole → wypełnij → zaktualizuj relacje → usuń int PK na osobne polecenie)
- **Multi-instancja**: jedno repo, `settings_base.py` + `settings_<name>.py` per instancja
- **Statyki różnicowe**: `STATICFILES_DIRS` overlay — katalog `static_<name>/` poprzedza `catalogue/static`
- **Kategorie danych**: main (master→slave), shared (bidirectional), ms (slave→master jako paczka)
- **TimeReference i Places**: kategoria `main`
- **Pola audit**: `entry_date` (auto_now=True, już istniejące) do detekcji delta; `version` (int) tylko dla `shared`; brak `is_deleted`
- **sync_status na Manuscripts**: `in_preparation / ready / synchronized / updated / deleted`
- **Pakiet ETL**: `django-import-export` + `django-import-export-extensions` + Celery + Redis
- **Autentykacja ETL**: statyczny token per instancja w settings
- **Deletions**: explicit endpoint `GET /api/etl/<category>/deleted/?since=<date>` zwraca listę deleted UUID

## Kategorie modeli (do weryfikacji)

| kategoria | model |
|-----------|-------|
| main | Formulas |
| main | TextStandarization |
| main | EditionContent |
| main | Sections |
| main | ContentFunctions |
| main | RiteNames |
| main | Traditions |
| main | LiturgicalGenres |
| main | LiturgicalGenresNames |
| main | Type |
| main | SeasonMonth |
| main | Week |
| main | Day |
| main | MassHour |
| main | Layer |
| main | Genre |
| main | Topic |
| main | Ceremony |
| main | DecorationTypes |
| main | DecorationTechniques |
| main | DecorationCharacteristics |
| main | Subjects |
| main | Colours |
| main | FeastRanks |
| main | BindingTypes |
| main | BindingStyles |
| main | BindingMaterials |
| main | BindingDecorationTypes |
| main | BindingComponents |
| main | ScriptNames |
| main | MusicNotationNames |
| main | TimeReference |
| main | Places |
| shared | Hands |
| shared | Bibliography |
| shared | Contributors |
| shared | Watermarks |
| ms | Manuscripts |
| ms | Content |
| ms | Calendar |
| ms | Decoration |
| ms | DecorationSubjects |
| ms | DecorationColours |
| ms | DecorationCharacteristics (join) |
| ms | ContentTopic |
| ms | Codicology |
| ms | Layouts |
| ms | Quires |
| ms | ManuscriptHands |
| ms | ManuscriptWatermarks |
| ms | ManuscriptBibliography |
| ms | Binding |
| ms | ManuscriptBindingMaterials |
| ms | ManuscriptBindingDecorations |
| ms | ManuscriptBindingComponents |
| ms | Origins |
| ms | Provenance |
| ms | Clla |
| ms | ManuscriptMusicNotations |
| ms | ManuscriptGenres |
| ms | Image |
| ms | AttributeDebate |
| local | UserOpenAIAPIKey |
| local | Profile |
| local | AIQuery |
| local | ImproveOurDataEntry |
| local | Projects |
| local | MSProjects |

## Fazy implementacji

### Faza 0 — Multi-instancja i refactoring (patrz ETL_plan_multiinstance.md)

### Faza 1 — Kategoryzacja modeli
Wygenerować `etl_model_categories.tsv` z manage.py command `export_model_categories`.
Ręczna weryfikacja przez właściciela bazy.

### Faza 2 — UUID + pola synchronizacji
Dodać do modeli `main`, `shared`, `ms`:
- `uuid = UUIDField(default=uuid4, unique=True, db_index=True)` (null=True na start)
- Do `shared` tylko: `version = PositiveIntegerField(default=1)`
- Do `Manuscripts` tylko: `sync_status = CharField(choices=[...])`
- Tam gdzie brak `entry_date`: dodać `entry_date = DateTimeField(auto_now=True)`
- Sygnał Django auto-inkrementujący `version` przy save() na modelach `shared`
- Command `generate_uuids` — uzupełnia UUID dla istniejących rekordów

### Faza 3 — UUID migracja FK (etapowa)
Krok A: `add_uuid_fk_fields` — dodaj <related>_uuid obok każdego int FK  
Krok B: `populate_uuid_fk` — wypełnij UUID FK przez JOIN po int ID  
Krok C: `validate_uuid_integrity` — raport niespójności  
Krok D: zaktualizuj views i API (lookup po uuid zamiast pk)  
Krok E: `drop_int_pk` — TYLKO na wyraźne polecenie  

### Faza 4 — django-import-export setup
Pakiety: django-import-export, django-import-export-extensions, drf-spectacular, celery, redis  
Plik `catalogue/resources.py` — ModelResource per model  
Rejestracja w adminie  

### Faza 5 — ETL API Endpoints
Plik `catalogue/etl_views.py`:
- GET  /api/etl/status/
- GET  /api/etl/main/export/?since=<date>
- POST /api/etl/main/import/
- GET  /api/etl/main/deleted/?since=<date>
- GET  /api/etl/shared/export/?since=<date>
- POST /api/etl/shared/import/  (409 on conflict)
- GET  /api/etl/shared/deleted/?since=<date>
- GET  /api/etl/manuscripts/list/
- GET  /api/etl/manuscripts/export/<uuid>/
- POST /api/etl/manuscripts/import/

### Faza 6 — GUI (panel migracji w Django Admin)
Custom admin view z listą manuskryptów ze wszystkich slave,
kolumny: instancja, sync_status (slave), sync_status (master), entry_date  
Przyciski: Import / View diff  
Conflict Resolution UI dla shared data