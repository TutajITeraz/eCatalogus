# ETL Replication Plan — eCatalogus

## Decyzje architektoniczne

- **UUID**: etapowa migracja (dodaj pole → wypełnij → zaktualizuj relacje → usuń int PK na osobne polecenie)
- **Multi-instancja**: jedno repo, `settings_base.py` + `settings_<name>.py` per instancja
- **Media per instancja**: jeden katalog `media_instances/` w repo, z osobnym `MEDIA_ROOT` dla każdej instancji
- **Statyki różnicowe**: `STATICFILES_DIRS` overlay — katalog `static_<name>/` poprzedza `catalogue/static`
- **Kategorie danych**: main (master→slave), shared (bidirectional), ms (slave→master jako paczka)
- **TimeReference i Places**: kategoria `main`
- **Pola audit**: `entry_date` (auto_now=True, już istniejące) do detekcji delta; `version` (int) tylko dla `shared`; brak `is_deleted`
- **sync_status na Manuscripts**: `in_preparation / ready / synchronized / updated / deleted`
- **Pakiet ETL**: `django-import-export` + `django-import-export-extensions` + Celery + Redis
- **Autentykacja ETL**: statyczny token per instancja w settings
- **Deletions**: explicit endpoint `GET /api/etl/<category>/deleted/?since=<date>` zwraca listę deleted UUID

## Stan repo na teraz

Stan na 2026-04-20 po lokalnym wdrożeniu pierwszych etapów i testach multi-instance:

- `etlapp` istnieje i obsługuje ETL API poza `indexerapp/views.py`
- działa `GET /api/etl/status/` i jest zabezpieczony tokenem `ETL_API_TOKEN`
- działa `GET /api/etl/<category>/deleted/?since=<date>` dla `main/shared/ms`
- działa `GET /api/etl/<category>/export/?since=<date>` dla `main/shared`
- działa `POST /api/etl/<category>/import/` dla `main/shared`
- działa `GET /api/etl/manuscripts/list/`
- działa `GET /api/etl/manuscripts/export/<uuid>/`
- działa `POST /api/etl/manuscripts/import/`
- import pakietu manuskryptu przenosi już także pliki `media` z pól `FileField/ImageField`
- istnieją komendy:
	- `export_model_categories`
	- `generate_uuids`
	- `validate_uuid_integrity`
	- `export_uuid_fk_plan`
- lokalny setup multi-instance ma rozdzielone cookies sesji per instancja (`SESSION_COOKIE_NAME`, `CSRF_COOKIE_NAME`)
- lokalny setup multi-instance ma rozdzielone `MEDIA_ROOT` per instancja pod `media_instances/`
- migracja `indexerapp.0002` została wygenerowana przez `makemigrations` i jest aktualnym punktem odniesienia dla rolloutu
- UUID są obecnie wdrożone w trybie bezpiecznym dla rolloutu: pole nullable + index, bez `unique=True` na tym etapie

To oznacza, że baza produkcyjna nie powinna się rozjechać, jeśli dostanie dokładnie te same migracje i te same komendy backfill/validation. Przy założeniu identycznej struktury i co najwyżej kilku nowych rekordów nie potrzeba osobnej gałęzi migracyjnej dla produkcji.

## Rzeczywista topologia produkcyjna na teraz

Stan na 2026-04-27:

- `ecatalogus.ispan.pl` działa jako nowa instancja docelowa, instalowana przez `scripts/install_instance.sh`
- `ecatalogus.ispan.pl` jest obecnie puste: brak manuscriptów, brak `main`, brak `shared`
- `monumenta-poloniae-liturgica.ispan.pl` działa jako starsza instancja produkcyjna instalowana ręcznie
- `monumenta-poloniae-liturgica.ispan.pl` zawiera właściwe dane robocze: manuscripts, `main`, `shared`
- stara instancja MPL jest jeszcze sprzed wdrożenia ETL i UUID, więc nie może jeszcze być źródłem dla standardowego `pull main/shared` po ETL

Wniosek operacyjny:

- są teraz dwa osobne tory pracy
- tor A: doprowadzić kod lokalny i nową bazę docelową do stanu gotowego na ETL/UUID
- tor B: przygotować bootstrap słowników `main` ze starej produkcji do plików, zanim stara instancja dostanie pełny rollout ETL

Bez rozdzielenia tych torów łatwo pomylić dwa różne cele: rollout ETL na starej instancji versus jednorazowe zasilenie nowej pustej instancji słownikami.

## Najbliższy cel techniczny

Najbliższy sensowny checkpoint nie jest już tylko "dopracować admin/GUI". Teraz priorytet jest taki:

1. lokalnie dodać plikowy export/import bundle dla ETL `main`, żeby ustalić docelowy format wsadu słowników po stronie nowej instancji
2. lokalnie wdrożyć legacy bootstrap `main` do jednego bundle z deterministycznymi UUID, tak żeby stara instancja mogła później dostać te same UUID przy rolloucie
3. dopiero potem wykonywać rollout UUID/ETL na starej produkcji MPL

To zmniejsza ryzyko, bo nowa instancja `ecatalogus.ispan.pl` może być napełniona słownikami wcześniej, bez wymuszania od razu pełnej migracji starej produkcji.

## Kiedy potrzebne są działania na produkcji

Na produkcji potrzebne są działania dopiero w tych checkpointach:

1. wdrożenie kodu zawierającego `etlapp`, nowe modele i migrację `indexerapp.0002`
2. uruchomienie `migrate`
3. uruchomienie `generate_uuids`
4. uruchomienie `validate_uuid_integrity --fail-on-issues`
5. później, dopiero przed Fazą 3 lub przed zaostrzeniem constraintów UUID, ponowne odpalenie walidacji i eksportu planu FK

Rekomendacja operacyjna na teraz:

- jeszcze można chwilę nie dotykać produkcji
- eksport/import dla `main/shared`, manuscript package i pierwsze GUI ETL sync są już dostępne, więc następny sensowny checkpoint to dopracowanie admin/GUI i etapowe narzędzia FK
- produkcję ruszyć dopiero przy większym checkpointcie, nie po każdym małym kroku

Nie ma jeszcze potrzeby wykonywania na produkcji żadnych operacji typu `drop_int_pk`, zmiany FK, ani ręcznego SQL.

## Sekwencja rolloutu lokalnie i produkcyjnie

### Checkpoint A — lokalnie na kopii produkcji

1. `python manage.py migrate`
2. `python manage.py generate_uuids`
3. `python manage.py validate_uuid_integrity --fail-on-issues`
4. `python manage.py export_model_categories --output /tmp/etl_model_categories.tsv`
5. `python manage.py export_uuid_fk_plan --output /tmp/etl_uuid_fk_plan.tsv`
6. test endpointów ETL

Jeżeli to przejdzie, produkcja powinna wykonać dokładnie tę samą sekwencję.

### Checkpoint B — produkcja

1. deploy tego samego commitu
2. `python manage.py migrate`
3. `python manage.py generate_uuids`
4. `python manage.py validate_uuid_integrity --fail-on-issues`
5. `python manage.py export_uuid_fk_plan --output /tmp/etl_uuid_fk_plan.tsv`

Jeśli krok 4 przejdzie, można uznać Fazę 2 za wdrożoną także na produkcji.

### Checkpoint C — przed Fazą 3

Przed dodaniem `*_uuid` dla FK i przed ewentualnym `unique=True` na UUID trzeba ponownie wykonać:

1. `python manage.py generate_uuids`
2. `python manage.py validate_uuid_integrity --fail-on-issues`
3. `python manage.py export_uuid_fk_plan --output /tmp/etl_uuid_fk_plan.tsv`

To daje aktualny obraz relacji i eliminuje ryzyko, że kilka nowych rekordów z produkcji wypadnie z migracji etapowej.

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
| main | Characteristics |
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
| local | AttributeDebate |
| local | UserOpenAIAPIKey |
| local | Profile |
| local | AIQuery |
| local | ImproveOurDataEntry |
| main | Projects |
| ms | MSProjects |

## Fazy implementacji

### Faza 0 — Multi-instancja i refactoring (patrz ETL_plan_multiinstance.md)

### Faza 1 — Kategoryzacja modeli
Wygenerować `etl_model_categories.tsv` z manage.py command `export_model_categories`.
Ręczna weryfikacja przez właściciela bazy.

Status teraz:
- wdrożone
- dodatkowo istnieje `export_uuid_fk_plan`, który przygotowuje wejście do Fazy 3
- dodatkowo wiadomo już, że stare legacy importy pokrywają tylko 10 z 34 modeli `main`
- brakujące legacy importy `main`: `BindingComponents`, `BindingDecorationTypes`, `BindingMaterials`, `BindingStyles`, `BindingTypes`, `Characteristics`, `Colours`, `ContentFunctions`, `DecorationTechniques`, `DecorationTypes`, `EditionContent`, `FeastRanks`, `Formulas`, `LiturgicalGenres`, `LiturgicalGenresNames`, `MusicNotationNames`, `Places`, `Projects`, `RiteNames`, `ScriptNames`, `Sections`, `Subjects`, `TimeReference`, `Traditions`
- technicznie bezpieczniejszy kierunek bootstrapu to już nie 24 osobne `import_*.py`, tylko jeden exporter/importer bundle z deterministycznymi UUID dla starej instancji pre-ETL

### Faza 2 — UUID + pola synchronizacji
Dodać do modeli `main`, `shared`, `ms`:
- `uuid = UUIDField(default=uuid4, unique=True, db_index=True)` (null=True na start)
- Do `shared` tylko: `version = PositiveIntegerField(default=1)`
- Do `Manuscripts` tylko: `sync_status = CharField(choices=[...])`
- Tam gdzie brak `entry_date`: dodać `entry_date = DateTimeField(auto_now=True)`
- Sygnał Django auto-inkrementujący `version` przy save() na modelach `shared`
- Command `generate_uuids` — uzupełnia UUID dla istniejących rekordów

Status teraz:
- wdrożone w wersji rollout-safe
- faktyczny kształt pola na teraz: `UUIDField(db_index=True, null=True, blank=True)`
- UUID dla nowych rekordów są nadawane w sygnale
- istnieje `generate_uuids`
- istnieje `validate_uuid_integrity`
- `unique=True` i ewentualne `null=False` są odłożone do osobnego etapu po pełnej walidacji na wszystkich instancjach

### Faza 3 — UUID migracja FK (etapowa)
To wszystko powinny być skrypty bo każda faza będzie uruchamiana najpierw testowo a potem na docelowym środowisku produkcyjnym.
Można je pogrupować i wrzucić do jednego folderu np. ETL_scripts/Phase_3_step_1_2.py czy coś w tym stylu.

Status teraz:
- wdrożone lokalnie fale 3.1, 3.2 i 3.3 dla zwykłych FK
- istnieje już `export_uuid_fk_plan`, które daje pełną listę FK do migracji etapowej
- istnieją lokalnie komendy `populate_uuid_fk` i `validate_uuid_shadow_fks`
- istnieją już shadow columns `*_uuid` dla wszystkich `120` zwykłych FK relacji sync
- lokalny backfill MPL został wykonany z wynikiem `Updated 20989 rows`
- lokalna walidacja `validate_uuid_shadow_fks --fail-on-issues` przechodzi dla całego zakresu FK
- dopiero po przejściu checkpointów z Fazy 2 można generować właściwe kroki `add_uuid_fk_fields` i `populate_uuid_fk`
- lokalna inwentaryzacja na 2026-04-27 pokazuje realny zakres Fazy 3:
	- `120` zwykłych relacji `ForeignKey`
	- `21` relacji `ManyToMany` do obsłużenia po zakończeniu zwykłych FK
	- rozkład FK według kategorii:
		- `main -> main`: `16`
		- `main -> shared`: `2`
		- `shared -> main`: `1`
		- `shared -> shared`: `1`
		- `ms -> main`: `54`
		- `ms -> shared`: `16`
		- `ms -> ms`: `30`
- Fala 3.4 pozostaje otwarta dla `ManyToMany` i through tables

Krok A: `add_uuid_fk_fields` — dodaj <related>_uuid obok każdego int FK  
Krok B: `populate_uuid_fk` — wypełnij UUID FK przez JOIN po int ID  
Krok C: `validate_uuid_integrity` — raport niespójności  
Krok D: zaktualizuj views i API (lookup po uuid zamiast pk)  
Krok E: `drop_int_pk` — TYLKO na wyraźne polecenie  

#### Proponowany plan wykonania lokalnie — konkretne fale

Faza 3 nie powinna być robiona jako jeden duży migration burst. Najbezpieczniejszy lokalny plan to 4 fale:

**Fala 3.1 — słowniki i relacje samowystarczalne (`main/shared`)**

Zakres:
- `main -> main` (`16`)
- `main -> shared` (`2`)
- `shared -> main` (`1`)
- `shared -> shared` (`1`)

Cel:
- zbudować cały mechanizm shadow-FK na relacjach, które nie zależą jeszcze od pakietów manuscriptów
- potwierdzić, że importer/exporter ETL dla `main/shared` może już używać `*_uuid`, nawet jeśli DB nadal przechowuje stare int FK

**Fala 3.2 — relacje manuscriptów do słowników (`ms -> main/shared`)**

Zakres:
- `ms -> main` (`54`)
- `ms -> shared` (`16`)

Cel:
- przełączyć większość semantycznie ważnych relacji manuscript package na UUID
- zachować stabilność importu/exportu manuscript package bez ruszania jeszcze relacji wewnątrz samego `ms`

**Fala 3.3 — relacje wewnątrz pakietu manuscriptowego (`ms -> ms`)**

Zakres:
- `ms -> ms` (`30`)

Cel:
- dokończyć spójność całego pakietu manuscriptowego po UUID
- dopiero po tej fali ETL manuscript package będzie semantycznie gotowy do życia bez lookupów po int PK

**Fala 3.4 — relacje `ManyToMany` i tabele through**

Zakres:
- `21` relacji M2M
- dominują M2M typu `authors -> Contributors` w modelach `ms` oraz kilka `main -> main`

Cel:
- po stabilizacji zwykłych FK dopiero przenieść logikę lookupów M2M na UUID
- uniknąć mieszania problemów FK i M2M w jednej iteracji

#### Proponowane komendy / narzędzia dla Fazy 3

Najbardziej spójny kierunek w tym repo to nadal management commands, nie luźne skrypty poza Django. Proponowany zestaw:

1. `python manage.py export_uuid_fk_plan --output /tmp/etl_uuid_fk_plan.tsv`
	- już istnieje
	- źródło prawdy dla kolejności i zakresu

2. `python manage.py add_uuid_fk_fields --wave <wave-name>`
	- generuje i/lub aplikuje migracje dodające nullable shadow columns `*_uuid`
	- pierwsza wersja lokalna może działać tylko na wskazanej liście modeli z bieżącej fali

3. `python manage.py populate_uuid_fk --wave <wave-name>`
	- wypełnia `*_uuid` przez lookup do `related.uuid`
	- powinno działać bez `save()` i bez side effectów sygnałów

4. `python manage.py validate_uuid_shadow_fks --wave <wave-name> [--fail-on-issues]`
	- nowa walidacja Fazy 3
	- sprawdza:
		- brak nulli w wymaganych `*_uuid`
		- zgodność `fk_id -> related.uuid == fk_uuid`
		- brak osieroconych referencji

5. `python manage.py export_m2m_uuid_plan --output /tmp/etl_uuid_m2m_plan.tsv`
	- do wprowadzenia dopiero przed Falą 3.4
	- osobne źródło prawdy dla M2M i through tables

Status na 2026-04-28:
- komenda `python manage.py export_m2m_uuid_plan --output /tmp/etl_uuid_m2m_plan.tsv` jest już dostępna lokalnie
- komenda `python manage.py validate_uuid_m2m --fail-on-issues` jest już dostępna lokalnie
- lokalna inwentaryzacja M2M daje `21` wierszy, zgodnie z zakresem Fali 3.4
- ETL import/export już serializuje M2M jako `*_uuids`, a regresje lokalne pokrywają UUID-first import na M2M

#### Proponowane checkpointy lokalne

**Checkpoint L3-A — stan wejściowy**

1. `python manage.py migrate`
2. `python manage.py generate_uuids`
3. `python manage.py validate_uuid_integrity --fail-on-issues`
4. `python manage.py export_uuid_fk_plan --output /tmp/etl_uuid_fk_plan.tsv`

Warunek wyjścia:
- zero brakujących UUID na modelach sync
- pełna lista relacji wygenerowana i zapisana

**Checkpoint L3-B — Fala 3.1 (`main/shared`)**

1. dodać nullable `*_uuid` dla relacji `main/shared`
2. wypełnić je komendą backfill
3. odpalić walidację shadow-FK
4. przełączyć ETL import/export `main/shared` na preferowanie `*_uuid`
5. uruchomić testy regresji `main/shared`

Warunek wyjścia:
- `main/shared` działają bez lookupów po int PK na granicy ETL

**Checkpoint L3-C — Fala 3.2 (`ms -> main/shared`)**

1. dodać `*_uuid` dla relacji manuscriptów do słowników
2. wypełnić i zwalidować backfill
3. przełączyć manuscript package import/export na `*_uuid` tam, gdzie relacja wychodzi poza `ms`
4. uruchomić testy manuscript package

Warunek wyjścia:
- manuscript package nie zależy już od int PK przy relacjach do `main/shared`

**Checkpoint L3-D — Fala 3.3 (`ms -> ms`)**

1. dodać `*_uuid` dla relacji wewnętrznych `ms`
2. wypełnić i zwalidować backfill
3. przełączyć lokalne lookupi importowe / eksportowe `ms` na UUID
4. przetestować pełny manuscript package roundtrip

Warunek wyjścia:
- cały manuscript package jest spójny po UUID także wewnętrznie

**Checkpoint L3-E — Fala 3.4 (M2M)**

1. wygenerować plan M2M/through tables
2. przełączyć serializację M2M na UUID listy jako źródło prawdy
3. dodać walidację zgodności M2M po UUID
4. uruchomić końcowy zestaw regresji ETL

Warunek wyjścia:
- warstwa ETL i import/export nie potrzebują już semantycznie int PK do relacji sync

Najbliższy stan lokalny na teraz:
- plan M2M jest eksportowalny przez `export_m2m_uuid_plan`
- gotowość danych M2M do lookupów po UUID jest walidowalna przez `validate_uuid_m2m`
- kolejny etap Fali 3.4 to ewentualne dołożenie bardziej szczegółowych walidacji through tables, jeśli pojawią się niestandardowe M2M

### Checkpoint P3-A — produkcyjny rollout `0005` i `0006`

Ten checkpoint dotyczy wyłącznie wdrożenia lokalnie zwalidowanych migracji:
- `indexerapp.0005_binding_data_contributor_uuid_binding_date_uuid_and_more`
- `indexerapp.0006_binding_manuscript_uuid_calendar_content_uuid_and_more`

Kolejność na produkcji MPL:

1. wdrożyć commit zawierający modele, komendy i migracje `0005` oraz `0006`
2. uruchomić `python manage.py migrate indexerapp`
3. uruchomić `python manage.py populate_uuid_fk --chunk-size 500`
4. uruchomić `python manage.py validate_uuid_shadow_fks --chunk-size 500 --fail-on-issues`
5. opcjonalnie zapisać plan M2M: `python manage.py export_m2m_uuid_plan --output /tmp/etl_uuid_m2m_plan.tsv`
6. uruchomić `python manage.py validate_uuid_m2m --chunk-size 200 --fail-on-issues`

Warunek wejścia:
- produkcja działa już na commicie zawierającym wcześniejsze UUID rollout-safe pola oraz komendy z Fazy 2 i 3
- przed migracją istnieje aktualny backup bazy i plików `media`

Warunek wyjścia:
- migracje `0005` i `0006` są applied
- `populate_uuid_fk` kończy się bez błędów
- `validate_uuid_shadow_fks --fail-on-issues` kończy się statusem `0`
- `validate_uuid_m2m --fail-on-issues` kończy się statusem `0`
- nie wykonujemy jeszcze żadnego `drop_int_pk`, `ALTER ... DROP COLUMN`, ręcznego SQL ani zaostrzania constraintów

Gotowa sekwencja komend w repo:
- `scripts/run_phase3_mpl_rollout_0005_0006.sh`
- skrypt używa domyślnie `scripts/config/monumenta-poloniae-liturgica.ispan.pl.env`
- skrypt wykonuje dokładnie: `migrate indexerapp`, `populate_uuid_fk`, `validate_uuid_shadow_fks`, `export_m2m_uuid_plan`, `validate_uuid_m2m`

Checklist operacyjny dla produkcji:

1. backup bazy i `media`
2. deploy kodu z `0005` i `0006`
3. `migrate indexerapp`
4. `populate_uuid_fk --chunk-size 500`
5. `validate_uuid_shadow_fks --chunk-size 500 --fail-on-issues`
6. `export_m2m_uuid_plan --output /tmp/etl_uuid_m2m_plan.tsv`
7. `validate_uuid_m2m --chunk-size 200 --fail-on-issues`
8. zachować log z backfillu i walidacji
9. dopiero potem planować Falę 3.4 lub kolejne przepięcia runtime lookupów

Checkpoint lokalny wykonany przed produkcją:

- manuscript-bound runtime lookupi działają już w trybie kompatybilnym `uuid-or-id`
- lokalnie zostały przepięte i zwalidowane na `settings_mpl` oraz `settings_ecatalogus` co najmniej następujące surfaces:
	`ms_info`, `ms_gallery`, `content-list`, `hands-list`, `compare_formulas_json`, `ms_tei`, `manuscript_tei_xml`, `content_csv_export`, `delete_content`, `assign_ms_content_to_tradition`
- dla endpointów path-based dodane zostały lokalne aliasy UUID bez usuwania dotychczasowych ścieżek int-based
- nie zmieniamy jeszcze publicznego znaczenia `id` tam, gdzie jest wymagane przez integracje; explicit example: `Formulas.id` zostaje

#### Czego nie robimy jeszcze w Fazie 3

- nie usuwamy starych int FK columns
- nie usuwamy int PK z modeli
- nie ustawiamy jeszcze `uuid` jako jedynego runtime key w całym adminie i wszystkich widokach
- nie wprowadzamy jeszcze `unique=True` / `null=False` na wszystkich shadow-FK bez przejścia lokalnych checkpointów

#### Kryterium zakończenia Fazy 3 lokalnie

Fazę 3 lokalnie uznajemy za zakończoną dopiero, gdy:

1. wszystkie `120` FK mają shadow `*_uuid`
2. wszystkie shadow `*_uuid` są zwalidowane jako zgodne z obecnym `fk_id`
3. ETL `main/shared/ms` działa bez logicznej zależności od int PK na granicy import/export
4. relacje M2M są również serializowane i odtwarzane po UUID
5. aktywne manuscript-bound runtime endpointy lokalnie akceptują UUID bez zrywania kompatybilności z legacy `id`
6. pełny local roundtrip `legacy MPL -> ecatalogus -> ETL package` przechodzi bez ręcznych poprawek danych

### Faza 4 — django-import-export setup
Pakiety: django-import-export, django-import-export-extensions, drf-spectacular, celery, redis  
Plik `catalogue/resources.py` — ModelResource per model  
Rejestracja w adminie  

Status teraz:
- nie ma jeszcze klasycznego eksportera legacy dla starej instancji produkcyjnej MPL
- dodano plikowe komendy bundle oparte o pipeline ETL:
	- `python manage.py export_etl_bundle --category main --output /tmp/main_bundle.json`
	- `python manage.py import_etl_bundle /tmp/main_bundle.json`
- dodano plikowe komendy bootstrapu legacy `main`:
	- `python manage.py export_legacy_main_bundle --output /tmp/legacy_main_bundle.json`
	- `python manage.py import_legacy_main_bundle /tmp/legacy_main_bundle.json`
- dodano tryb `python manage.py generate_uuids --strategy deterministic`, zgodny z bootstrapem legacy
- te komendy są docelowym formatem wsadu po stronie nowej instancji i po stronie instancji już po wdrożeniu UUID/ETL
- nowy legacy exporter rozwiązuje eksport ze starej instancji pre-UUID bez wymuszania natychmiastowego rolloutu ETL

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

Status teraz:
- gotowe: `GET /api/etl/status/`
- gotowe: `GET /api/etl/main/export/?since=<date>`
- gotowe: `GET /api/etl/shared/export/?since=<date>`
- gotowe: `POST /api/etl/main/import/`
- gotowe: `POST /api/etl/shared/import/`
- gotowe: `GET /api/etl/manuscripts/list/`
- gotowe: `GET /api/etl/manuscripts/export/<uuid>/`
- gotowe: `POST /api/etl/manuscripts/import/`
- gotowe: `GET /api/etl/<category>/deleted/?since=<date>` dla `main/shared/ms`
- gotowe: pierwsze GUI ETL sync przez `page.html` + DataTables + backend proxy session-auth
- gotowe: spinner/pending-state w GUI ETL sync
- gotowe: transfer plików `media` w manuscript package ETL
- gotowe: pierwsze GUI review dla konfliktów `shared` z możliwością zastosowania wersji zdalnej
- gotowe: plikowy export/import bundle przez manage.py dla istniejącego formatu ETL (`export_etl_bundle`, `import_etl_bundle`)
- brak jeszcze pełnego panelu admin/conflict resolution w Django Admin i dalsze kroki migracji FK

### Faza 5a — Bootstrap słowników `main` ze starej produkcji

To jest teraz osobna faza operacyjna wynikająca z realnego stanu produkcji.

Cel:
- wyciągnąć `main` ze starej instancji `monumenta-poloniae-liturgica.ispan.pl`
- załadować je do nowej pustej instancji `ecatalogus.ispan.pl`
- zrobić to bez pełnego ETL pull, dopóki stara instancja nie ma jeszcze UUID i endpointów ETL

Zakres lokalny do wdrożenia:
- utrzymać i przetestować jeden legacy exporter wszystkich `main` do jednego bundle JSON
- utrzymać zgodność deterministic UUID między bundle legacy a późniejszym `generate_uuids --strategy deterministic` na starej instancji
- brakujące stare `import_*.py` pozostają opcjonalnym torem pomocniczym, ale nie są już krytyczną ścieżką bootstrapu nowej instancji

Status teraz:
- legacy importer coverage jest niepełne: 10/34 modeli `main`
- legacy exporter istnieje
- legacy importer bundle istnieje
- nowy importer bundle ETL już istnieje i może być docelowym wejściem po stronie nowej instancji

### Faza 6 — GUI (panel migracji w Django Admin)
Custom admin view z listą manuskryptów ze wszystkich slave,
kolumny: instancja, sync_status (slave), sync_status (master), entry_date  
Przyciski: Import / View diff  
Conflict Resolution UI dla shared data

Status teraz:
- istnieje pierwsza wersja GUI konfliktów w panelu ETL sync (`page.html`)
- obsługuje pokazanie konfliktu `shared`, podgląd różnic i zastosowanie wersji zdalnej
- nie ma jeszcze pełnego panelu adminowego z kolejką konfliktów, historią decyzji i trwałym workflow dla decyzji "zachowaj lokalne"