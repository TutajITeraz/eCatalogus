# eCatalogus — answers to the ritus+ integration questions

Reply to *"Requests to the eCatalogus administrator — ritus+ Send to eCatalogus"*.

Verified on **2026-08-25** against the source of `apiv1/`, `etlapp/` and the
instance settings, and re-checked against all five live instances.

Thank you for the report — it is precise, and every observation in it is
correct. The CORS claim in the integration guide was wrong and has been
withdrawn; §1 of `INTEGRATION.md` will be corrected.

**Everything you asked for has been built**, plus a fix for `music_notation_id`,
which turned out to be a harder problem than either of us had noticed. §4 and §5
describe what is now in the API; §8 and §9 are the two things you did not ask
about but will need.

**One item in your report is not a question and needs your attention first: §3.**
Resolving a ritus integer id against the `id` column of a downloaded dictionary
is correct on MPL Limbo and eCatalogus and **silently wrong on the other three
instances**. Details and evidence below. It is the only correctness bug we
found, and we caused it.

---

## Summary

| # | Your item | Answer |
|---|---|---|
| 1 | CORS blocker | **Confirmed, our fault, being fixed.** The guide described a setting that is not live on any instance. |
| 2 | `api_importers` rights | **Done on MPL Limbo.** Test there. |
| 3 | Integer id in relation fields | **No — and it will never be added.** The integer `id` is instance-local. See the warning below. **`id` has now been removed from the API.** |
| 4 | Fetching selected dictionary entries | **Built:** `?uuids=`, `?legacy_ids=` and `?fields=` are implemented, and unknown parameters are now rejected. |
| 5 | `quire_id` | Quires are **not a dictionary** — they belong to one manuscript. You said ritus has no quire data, so nothing was built; skipping remains correct. |
| 6 | Four instances list zero manuscripts | **Genuinely empty.** No visibility filter exists; credentials change nothing. |
| 7 | *(not asked)* Server behaviour that will bite you | Five things worth reading before the first real import. |
| 8 | *(not asked)* Caching the dictionaries locally | Everything you need now exists. **`music_notation_id` is solved** — see §8.2. |
| 9 | *(not asked)* Migrating the ritus database | Required, and it has to be done with committed scripts. Recipe below. |

---

## 1. CORS — confirmed, and the guide was wrong

Your diagnosis is exactly right, including the `vary: origin` inference.

The guide's sentence *"`https://ritus-indexer.ispan.pl` is already on the
allow-list"* described the intended configuration, not the deployed one. In the
source, `API_INTEGRATION_ORIGINS` is merged into `CORS_ALLOWED_ORIGINS` per
instance, but the ritus origin is only present as a default for **one** of the
five instances (`eCatalogus`), and even there it is not live in the deployed
build.

The middleware itself is healthy. An instance's *own* origins do get the
headers, which localises the fault precisely to the allow-list:

```
$ curl -s -D - -o /dev/null -H "Origin: https://ecatalogus.ispan.pl" \
       https://ecatalogus.ispan.pl/api/v1/
HTTP/2 200
access-control-allow-origin: https://ecatalogus.ispan.pl      <-- works
access-control-allow-credentials: true

$ curl -s -D - -o /dev/null -H "Origin: https://ritus-indexer.ispan.pl" \
       https://ecatalogus.ispan.pl/api/v1/
HTTP/2 200
                                                              <-- nothing
```

So this is a one-line configuration change per instance, not a code change.

### What has been set

Both origins are now declared as `api_integration_origins` in all five instance
settings files, which merges them into `CORS_ALLOWED_ORIGINS`:

| Origin | Purpose |
|---|---|
| `https://ritus-indexer.ispan.pl` | ritus+ in production |
| `http://localhost:5173` | your dev server |

They take effect on each instance when the servers next pick up the current
build. We will tell you when that is done; until then the `curl` above is the
one-line way to check for yourself, on any instance:

```bash
curl -s -D - -o /dev/null -H "Origin: https://ritus-indexer.ispan.pl" \
     https://<instance>/api/v1/ | grep -i access-control-allow-origin
```

### The preflight needs nothing further

Already verified against an origin that *is* on the list — `Authorization`,
`Content-Type` and `POST` all pass today, so once the origin is added there is
no second round of configuration:

```
$ curl -s -D - -o /dev/null -X OPTIONS \
       -H "Origin: https://ecatalogus.ispan.pl" \
       -H "Access-Control-Request-Method: POST" \
       -H "Access-Control-Request-Headers: authorization,content-type" \
       https://ecatalogus.ispan.pl/api/v1/whoami/

access-control-allow-headers: accept, authorization, content-type, user-agent, x-csrftoken, x-requested-with
access-control-allow-methods: DELETE, GET, OPTIONS, PATCH, POST, PUT
access-control-max-age: 86400
```

The guide's advice stands: do **not** set `credentials: 'include'`. The
`Access-Control-Allow-Credentials: true` you will see in the response is a
side effect of the instance's own session-based tooling, not an invitation.

---

## 2. Import rights

**Done: the `api_importers` group is set up on MPL Limbo**, so the whole path
can be exercised there against real data. Tell us which accounts to enable on
the other instances once Limbo is proven.

Your handling is right, and worth confirming from the code side: `401` and
`can_import: false` really are two different states, and the `xBasic` challenge
is deliberate — `apiv1/authentication.py` overrides `authenticate_header()`
precisely so the browser's native dialog stays out of the way.

---

## 3. Integer ids — no, and a warning about the current mapping

**Answer: no.** `POST /content/bulk/` resolves a relation field in this order,
and nowhere in it is the integer `id` consulted:

1. the value parsed as a UUID,
2. the `"<shortname> c.<sequence>"` composite form, for `edition_index` only,
3. the field's declared name columns, matched case-insensitively.

It will not be added, and here is why it must not be.

### The integer `id` is instance-local

Replication between instances matches rows by **UUID** and deliberately never
copies the primary key (`etlapp/services.py`: `if field.primary_key: continue`).
Each instance therefore assigns its own autoincrement `id` in the order it
happened to receive the rows. The same dictionary entry, live today:

| Entry | Limbo | Liturgica Poloniae | eCatalogus | Canon Missae | Corpus Liturgicum | UUID (everywhere) |
|---|---|---|---|---|---|---|
| RiteNames *apostoli plures* | **1** | **4565** | **1** | **4565** | **9129** | `0d6b1e87-2887-5b4c-b464-a14d78895b30` |
| Formulas *Exorcizo te creatura salis…* (CO 2) | **1** | **13235** | **1** | **13235** | **26469** | `44064845-17c3-5f94-9756-93588ebfa2e0` |
| ContentFunctions *Collecta* | **1** | **235** | **1** | **79** | **157** | `85d62046-5521-5150-aa23-799de39d44f9` |

The UUID is identical on all five. The `id` is not, and the offsets are not even
consistent between dictionaries — so there is no correction factor to apply.

**The UUID is the only cross-instance identifier. Treat `id` as a display
detail of one server's response, never as a key.**

### ⚠️ This affects ritus+ today

Your dialog downloads the chosen instance's dictionary and maps
`rite_id: 1 → results[id == 1].uuid`. Against Limbo and eCatalogus that is
right. Against **Liturgica Poloniae, Canon Missae or Corpus Liturgicum** it
resolves to a completely unrelated rite — and, because the UUID it produces is
perfectly valid on that instance, the import succeeds. No error, wrong data.

Since those three are empty today (§6) nothing has been damaged, but the bug is
latent and would fire the first time someone points the dialog at one of them.

### What to do instead

**For every field where ritus holds a name — resolve nothing.** The bulk import
already accepts the name and does the lookup server-side:

| ritus field | Send | Matched against |
|---|---|---|
| `rubric_id` | `"Ad complendum"` | `RiteNames.name` |
| `function_id` / `subfunction_id` | `"Collecta"` | `ContentFunctions.name` |
| `section_id` / `subsection_id` | name | `Sections.name` |
| `liturgical_genre_id` | title | `LiturgicalGenres.title` |
| `layer`, `mass_hour`, `genre`, `season_month`, `week`, `day` | `"S/C"` | `short_name`, then `name` |
| `text_standarization` | standard incipit | `TextStandarization.standard_incipit` |
| `contributor_id` | initials | `Contributors.initials` |
| `music_notation_id` | `"Square notation"` | `MusicNotationNames.name`, then this manuscript's notation records (§5) |

Names are stable across instances; ids are not. This deletes the download for
`rite-names` (1.4 MB, ~6 s) and every small dictionary outright, and it removes
the whole class of bug above. Unmatched values still come back before anything
is written, from a `dry_run`, with the row, field and value named.

**`formula_id` is now the only field that genuinely needs a UUID** — `Formulas`
has no name lookup declared, because neither `co_no` nor `text` identifies an
entry uniquely. `quire_id` and `edition_index` are also UUID-only, but you have
told us ritus carries neither. See §4 for how to resolve formulas in one
request.

---

## 4. Fetching selected dictionary entries — built

Your reading of the endpoint was correct: it accepted only `search`, `since`,
`limit` and `offset`, and ignored everything else silently. That is fixed, and
three selectors are now implemented.

Note that a plain `?ids=` filter, as proposed, would **not** have solved your
problem: you would be sending Limbo's numbering to a server that numbers rows
differently (§3). It would have been a fast path to the wrong answer.

### `?uuids=` — batch fetch by UUID

```bash
curl 'https://ecatalogus.ispan.pl/api/v1/dictionaries/rite-names/?uuids=0d6b1e87-2887-5b4c-b464-a14d78895b30,5dfcff1d-ed9e-59b3-be0c-8b6296262474'
```

Up to 1000 UUIDs per request. A malformed value is a `400` naming it, not a
silently short page.

### `?legacy_ids=` — resolve the numbering ritus already holds

This is the one that removes the 25-second step. When the legacy database was
migrated, every row was given a UUID **derived from its old primary key**, and
that old numbering is exactly what ritus's CSV dictionaries carry. The server
now does that derivation for you:

```bash
curl 'https://ecatalogus.ispan.pl/api/v1/dictionaries/formulas/?legacy_ids=1,2,3,999999'
```

```json
{
  "slug": "formulas",
  "count": 3,
  "results": [
    { "uuid": "44064845-17c3-5f94-9756-93588ebfa2e0", "legacy_id": 1, "co_no": "2", "text": "Exorcizo te…" }
  ],
  "unresolved_legacy_ids": [999999]
}
```

Each record gains a **`legacy_id`** key so you can join the response straight
back to your own rows, and every id with no entry here comes back in
**`unresolved_legacy_ids`** — which is precisely the report you want at
migration time (§9).

It is not universal, and the response says so rather than guessing: entries
created *after* the migration have random UUIDs and will always appear as
unresolved. In practice that matters only for `formula_id`, because everything
else should be sent by name (§3).

### `?fields=` — projection

```bash
curl 'https://ecatalogus.ispan.pl/api/v1/dictionaries/formulas/?fields=co_no,text'
```

`uuid` is always included whether you ask for it or not, and so is `legacy_id`
when `?legacy_ids=` was used. There is no way to receive a row you cannot
identify.

### Unknown parameters are now a `400`

```bash
$ curl '…/api/v1/dictionaries/formulas/?id=1'
{"detail": "Unknown query parameter(s): id. This endpoint accepts: fields, format, legacy_ids, limit, offset, search, since, uuids."}
```

Answering `200` to `?id=1` is how a caller convinces itself that a filter it
invented is being applied — which is very close to what happened here.

### Combined

Naming entries explicitly is treated as a request for all of them, so `limit`
defaults to 1000 rather than 200 when `?uuids=` or `?legacy_ids=` is present.
Resolving a few hundred formulas is one request:

```
GET /api/v1/dictionaries/formulas/?legacy_ids=1,7,12,…&fields=co_no,text
```

---

## 5. `quire_id` — and `music_notation_id`

The premise was slightly off, which is why it looked unmappable: **`Quires` is
not a controlled vocabulary.** A quire row belongs to exactly one manuscript and
describes its physical structure — sequence, type, folio range, material. That
is why there is no `quires` entry under `/api/v1/dictionaries/`, and there never
will be. The same is true of `ManuscriptMusicNotations`, which `music_notation_id`
points at.

You have since told us **ritus has no quire data assigned**, so nothing was
built for `quire_id`. Skipping it and telling the user remains exactly right —
better than failing 800 good rows over one unmappable column. Please keep the
notice visible. If quires are ever assigned in ritus, say so and `quire_id` will
accept a quire sequence within the target manuscript.

If you want to map them by hand in the meantime,
`/api/v1/manuscripts/{uuid}/package/` includes the model `indexerapp.Quires`
with `sequence_of_the_quire` and the folio range on every row.

### `music_notation_id` — this one is now solved

Your notation dictionary is not a ritus-local table. It is **exactly** our
`MusicNotationNames` vocabulary — same seven entries, same names, same
numbering:

| ritus | eCatalogus `music-notation-names` | UUID |
|---|---|---|
| 1 Messine | 1 Messine | `38fadc77-a147-52f8-b3cd-2bae2234930c` |
| 2 German-French unheightened | 2 German-French unheightened | `8061e783-48d1-502e-bfd7-8641e15bd976` |
| 3 German neumatic notation | 3 German neumatic notation | `0f98cadb-38df-5fb0-bd6f-217fbfe477d8` |
| 4 Gothic neumes | 4 Gothic neumes | `152ade8b-3b24-58ab-a11b-7cf04fbdd922` |
| 5 Messine-German neumes | 5 Messine-German neumes | `826a8adb-4dda-50c8-a497-a5ad5021a4e7` |
| 6 Cistercian neumes | 6 Cistercian neumes | `2a238f44-af1d-53ed-87cd-ff021696e356` |
| 7 Square notation | 7 Square notation | `68e98f86-a64c-5265-a3b7-e317728123b7` |

But the content field does **not** point there. `Content.music_notation_uuid`
references a `ManuscriptMusicNotations` row — one notated stretch of one
manuscript, with its own folio range and sequence. ritus records *which notation
an item is written in*; eCatalogus records *which notated block it falls in*.
Different granularities, which is why no amount of caching the vocabulary would
have resolved the field.

**The importer now bridges the two.** `music_notation_id` accepts a
`MusicNotationNames` name (or UUID) and resolves it against the target
manuscript's own notation records:

```json
{ "sequence_in_ms": 1, "formula_text_from_ms": "…", "music_notation_id": "Square notation" }
```

Matching is case-insensitive, so `"square notation"` works too. Send the **name**
from your table, not the id — the ids agree today by coincidence, and the rule
from §3 applies here as much as anywhere.

Three outcomes, all reported by `dry_run` before anything is written:

| Situation | Result |
|---|---|
| The manuscript has a block with that notation | Resolved to that block |
| The notation exists, but the manuscript has no block using it | `not_found`, naming the manuscript: *"Square notation is a known music notation, but 'X' has no notation described with it."* |
| The name is not one of the seven | `not_found` |

The middle case is the common one, and it is not an error you can code around:
it means nobody has described that manuscript's notation in eCatalogus yet.
**Keep your skip-and-tell behaviour as the fallback** — if the manuscript's
notation has not been described, the field simply cannot be imported, and 800
good rows should not fail over it.

A `ManuscriptMusicNotations` row is never created from a content row. It carries
a folio range and a sequence that a content import has no way to know, and
inventing that would produce codicological description nobody wrote.

---

## 6. The four instances really are empty

Confirmed from both sides.

`ManuscriptListView` applies no visibility filter of any kind — it reads
`Manuscripts.objects.all()`, ordered by name, narrowed only by your `search` and
`foreign_id` parameters. There is no draft flag, no publication state, no
per-user scoping anywhere in the endpoint. **Anonymous and authenticated callers
see byte-identical results.**

The administrator confirms it independently: all manuscript data currently lives
on MPL Limbo. The other four instances are provisioned and empty.

So: **do not add the `Authorization` header to the manuscript list call.** It
would change nothing and would send credentials where they are not needed. Your
current behaviour is right.

---

## 7. Worth knowing before the first real import

Small things in the server's behaviour that are easy to trip over.

**`dry_run` stops reporting after 200 problems.** A payload with more than that
ends with a final `too_many_errors` entry and validation of the remaining rows
is abandoned. A table with a systematically mis-mapped column will therefore
report 200 errors and hide the rest — worth saying in the UI, so nobody fixes
200 rows and expects to be finished.

**You are stripping more than you need to.** `id`, `uuid`, `manuscript_uuid`,
`entry_date` and every `*_label` key are accepted and ignored even under
`strict`, so an export from one manuscript can be posted straight to another.
`manuscript_id`, `formula_standardized`, `rite_name_standarized` and
`levenshtein` do have to go, as you already do.

**`mode: "replace"` deletes the manuscript's *entire* content**, not the rows
your payload happens to overlap. Given your dialog offers it when a manuscript
already holds records, please make sure the confirmation says so plainly.

**Omitted `sequence_in_ms` continues from the current maximum**, so an `append`
of rows without an explicit sequence lands after the existing content rather
than colliding with it.

**Timing.** Rows are written one at a time inside a single transaction, with
related bookkeeping per row; budget roughly a second per hundred rows. 800 rows
is a normal payload and there is no row cap, no size cap and no rate limit for
authenticated callers — but set a generous client timeout. Nothing on the server
cuts the request short.

**Everything is one transaction.** A timeout on your side does not mean a
partial import on ours: the write either completed or left nothing behind. On a
timeout, re-check `/content/summary/` before retrying rather than assuming
failure.

---

## 8. Loading and caching the dictionaries

You asked whether the API can serve the dialog. It can, and it can also serve
the local cache — with one exception, named in §8.7. This section is the whole
recipe, so nothing has to be inferred from the reference.

### 8.1 Pull from eCatalogus, not from the instance you are uploading to

`https://ecatalogus.ispan.pl` is the **canonical master** for every controlled
vocabulary. The other four instances receive those tables through a one-way
replication pull and may not edit them locally — that rule is enforced in the
server, not merely by convention.

Because replication matches rows by UUID, **the UUIDs are identical on all five
instances** (§3). So one cache, pulled once from eCatalogus, is valid for
uploads to any instance. You do not need a cache per instance, and you should
not build one.

One exception: **`contributors` is not a master vocabulary.** Contributors may
be created on any instance and reconciled afterwards, so a person who exists on
MPL Limbo may not yet exist on eCatalogus. Pull that one from the instance you
are uploading to, or simply send initials and let the server resolve them.

### 8.2 What ritus actually needs — coverage

Sixteen content fields reference something. Thirteen are fully served by the
dictionary endpoints:

| ritus column | eCatalogus field | Dictionary slug | Model label (for §9) | Rows |
|---|---|---|---|---|
| `rite_id` | `rubric_id` | `rite-names` | `indexerapp.RiteNames` | 4 564 |
| `formula_id` | `formula_id` | `formulas` | `indexerapp.Formulas` | 13 234 |
| `function_id`, `subfunction_id` | same | `content-functions` | `indexerapp.ContentFunctions` | 113 |
| `section_id`, `subsection_id` | same | `sections` | `indexerapp.Sections` | 11 |
| `liturgical_genre_id` | same | `liturgical-genres` | `indexerapp.LiturgicalGenres` | 9 |
| `layer` | same | `layers` | `indexerapp.Layer` | 4 |
| `mass_hour` | same | `mass-hours` | `indexerapp.MassHour` | 19 |
| `genre` | same | `genres` | `indexerapp.Genre` | 133 |
| `season_month` | same | `seasons-and-months` | `indexerapp.SeasonMonth` | 21 |
| `week` | same | `weeks` | `indexerapp.Week` | 30 |
| `day` | same | `days` | `indexerapp.Day` | 41 |
| `text_standarization` | same | `text-standarization` | `indexerapp.TextStandarization` | 368 |
| `contributor_id` | same | `contributors` | `indexerapp.Contributors` | 13 |

Note the singular model names — `Layer`, `MassHour`, `Genre`, `SeasonMonth`,
`Week`, `Day`. They matter in §9.

Three do **not** come from a dictionary, and none of them needs one:

| Field | Why | What to do |
|---|---|---|
| `music_notation_id` | `ManuscriptMusicNotations` is per-manuscript — not the `music-notation-names` vocabulary, which is a different model | **Send the notation name.** The server resolves it against the manuscript (§5). Nothing to cache. |
| `quire_id` | Quires belong to one manuscript | Not assigned in ritus — skip it (§5) |
| `edition_index` | No read endpoint exists | Not needed in ritus — skip it (§8.7) |

So **there is nothing to cache beyond the thirteen dictionaries above**, and one
of those thirteen — `music-notation-names` — you do not need to cache either,
since that field is resolved by name.

Do not be misled by the name `music-notation-names`: that dictionary is the
*catalogue of notation types*, and caching it will not let you resolve
`music_notation_id`, because the content field points at per-manuscript records
instead. It is listed here only so you do not go looking for it.

### 8.3 The calls

One endpoint, one paging loop, no authentication:

```bash
curl 'https://ecatalogus.ispan.pl/api/v1/dictionaries/'                       # the index
curl 'https://ecatalogus.ispan.pl/api/v1/dictionaries/rite-names/?limit=1000' # one page
```

Follow `next_offset` until it comes back `null`:

```python
def fetch_dictionary(slug, base='https://ecatalogus.ispan.pl/api/v1'):
    rows, offset = [], 0
    while offset is not None:
        page = requests.get(
            f'{base}/dictionaries/{slug}/',
            params={'limit': 1000, 'offset': offset},
            timeout=120,
        ).json()
        rows.extend(page['results'])
        offset = page['next_offset']
    return rows
```

`limit` is capped at 1000; anything larger is silently clamped. Ordering is
stable within a single pull.

### 8.4 The cache files

Keep the TSV format you already have. Two rules:

1. **`uuid` is the key column.** It is the only identifier that means the same
   thing on every instance.
2. **Keep `legacy_id` as a separate column** — the id ritus has always used, for
   joining against existing ritus rows during and after the migration. Name it
   `legacy_id`, never `id`, so it can never be mistaken for the server's `id`.

Do **not** cache the `id` field. It was that one server's autoincrement, it
differs per instance, and **it has now been removed from the API** — dictionary
and package responses no longer carry it at all. If your cache builder reads
`row['id']`, it will start raising once the change is deployed; that is
deliberate, and better than the silent mis-resolution it was enabling.

```
# data/ecatalogus/rite-names.tsv
uuid	legacy_id	name	english_translation	section_uuid	votive
0d6b1e87-2887-5b4c-b464-a14d78895b30	1	apostoli plures		18c4efde-…	true
```

A small sidecar per file makes the cache auditable and lets the UI say when it
was last refreshed:

```json
{
  "slug": "rite-names",
  "source": "https://ecatalogus.ispan.pl/api/v1/dictionaries/rite-names/",
  "site_name": "eCatalogus",
  "fetched_at": "2026-08-25T12:00:00Z",
  "row_count": 4564
}
```

Every response also carries a `rights` block. Keep `rights.attribution` and
`rights.license_url` with the cache — CC BY applies to the vocabularies too, and
a TSV on disk has no HTTP headers left to carry the terms.

### 8.5 The refresh button

**Make it a full replace, not a merge.** The whole cache is 30 requests, 9.7 MB
and about 33 seconds, measured against eCatalogus today:

| Dictionary | Rows | Requests | Size | Time |
|---|---|---|---|---|
| `formulas` | 13 234 | 14 | 8.5 MB | 24.5 s |
| `rite-names` | 4 564 | 5 | 1.2 MB | 6.6 s |
| `text-standarization` | 368 | 1 | 132 KB | 0.1 s |
| `genres` | 133 | 1 | 53 KB | 0.5 s |
| the other nine | ≤ 113 each | 1 each | < 20 KB each | < 0.1 s each |
| **total** | **18 560** | **30** | **9.7 MB** | **~33 s** |

That is a perfectly ordinary admin action, and it no longer sits in the upload
path — which is the real win. A full replace is always correct; a merge is only
correct if you can see deletions, and you cannot (§8.6).

Requirements for the button:

- **Admin-only**, and it names its source: *"Refresh dictionaries from
  eCatalogus (last refreshed: 25 Aug 2026, 18 560 entries)"*.
- **Write to a temporary directory, then swap.** A refresh interrupted halfway
  must not leave a half-written cache that a later upload silently resolves
  against.
- **Never partially apply.** If any one dictionary fails, keep the previous
  cache entirely and report the failure.
- **Report the diff** — added, changed, removed per dictionary. An editor who
  refreshes wants to know whether the term they were waiting for has arrived.
- **Do not wire it to the upload dialog.** Resolution should use whatever cache
  is on disk; refreshing is a deliberate act.

### 8.6 Incremental refresh, and what it cannot tell you

`?since=` is supported on **every** dictionary — all 32 models carry
`entry_date`, verified today:

```bash
curl 'https://ecatalogus.ispan.pl/api/v1/dictionaries/rite-names/?since=2026-08-01T00:00:00Z&limit=1000'
```

Two caveats before you build on it:

- **It never reports deletions.** A term withdrawn from the vocabulary stays in
  your cache forever. Tombstones exist server-side but only on the internal
  replication API, which is not open to third parties.
- **`entry_date` is `auto_now`**, so a replication sync that rewrites rows bumps
  it even when nothing changed semantically. `?since=` is correct, but not
  minimal — expect it to return more than you expect right after a sync.

So: use `?since=` for a cheap "is there anything new?" check if you want one,
and keep the button itself a full replace.

### 8.7 `edition_index` — left out, by agreement

There is no read endpoint for `EditionContent`, and the composite form the
importer accepts — `"<bibliography shortname> c.<sequence>"` — needs a
bibliography short name, for which there is also no endpoint. So the field
cannot currently be resolved by any route.

You have said ritus does not need it, so nothing was built. If that changes,
both endpoints go in — say the word. Until then treat `edition_index` and
`edition_subindex` the way you treat `quire_id`: drop them, and say so.

### 8.8 Using the new selectors in the refresh

With §4 shipped, the refresh can be much cheaper than the full pull if you want
it to be. The cache only ever needs the entries ritus actually references:

```
GET /api/v1/dictionaries/formulas/?legacy_ids=<the ids in your tables>&fields=co_no,text
```

That turns the 8.5 MB, 24-second `formulas` step into one request of a few
hundred rows. Whether it is worth it is your call — a full pull is 33 seconds on
an admin button and is always correct, whereas a selective pull silently omits
anything ritus has not referenced yet. **For the button, pull everything. For
the migration (§9), pull selectively.**

---

## 9. Migrating the ritus database off the integer ids

This follows from §3 and is not optional. The ritus tables hold legacy integer
ids in `rite_id`, `formula_id`, `function_id` and the rest. Those numbers are
meaningful only against Limbo's and eCatalogus's numbering, by historical
accident. Every one of them needs a UUID stored beside it.

**It must be done with scripts committed to the ritus repository**, not with
ad-hoc SQL — the same commands have to run on the developer's machine, on
staging and on the production server, and produce the same result each time.

### 9.1 What makes it tractable

When the legacy database was migrated into eCatalogus, every row was given a
**deterministic** UUID derived from its legacy primary key:

```python
import uuid
NAMESPACE = uuid.UUID('8e7f6f8a-cc0f-4e6f-a7af-c7a7e9d1f4e3')

def legacy_uuid(model_label, legacy_id):
    return uuid.uuid5(NAMESPACE, f'{model_label}:{legacy_id}')

legacy_uuid('indexerapp.RiteNames', 1)
# UUID('0d6b1e87-2887-5b4c-b464-a14d78895b30')   <- the real entry, on all five instances
```

ritus's ids **are** that legacy numbering, so this maps them directly. Sampled
against the live data today: 500/500 formulas and 500/500 rite names reproduce
exactly. Use the model labels from the table in §8.2 — `indexerapp.Layer`, not
`indexerapp.Layers`.

**Never send a derived UUID without confirming it against the cache.** Entries
created *after* the migration have random UUIDs and are not derivable — about
42 % of `content-functions`, for instance. A derived UUID that does not exist is
harmless (the server rejects it as `not_found`), but you want that reported at
migration time, in bulk, not row by row during an upload.

### 9.2 The four scripts

Four separate, re-runnable commands. Keeping them separate means a failure at
step 3 does not force a re-download, and step 4 can be run at any time
afterwards as an audit.

**1 — pull the cache.** §8.3, writing the TSVs of §8.4.

```
ritus dicts:pull --source https://ecatalogus.ispan.pl --out data/ecatalogus/
```

**2 — build the mapping, resolve nothing yet.** For every distinct legacy id in
every dictionary column, in this order:

1. derive `uuid5(NAMESPACE, f'{label}:{legacy_id}')` and accept it **only if it
   is present in the cache**;
2. otherwise match by name against the cache, using the same columns the server
   matches on (`name`, or `short_name` then `name`, or `title`);
3. otherwise record it as unresolved.

```
ritus dicts:map --dry-run
# -> data/migration/mapping-rite_id.tsv        legacy_id, uuid, method(derived|name), label
# -> data/migration/unresolved.tsv             table, column, legacy_id, occurrences
```

Step 1 can now do the derivation for you, which is worth using for `formula_id`
in particular — one request instead of an 8.5 MB download:

```
GET /api/v1/dictionaries/formulas/?legacy_ids=1,7,12,…
# every row comes back carrying its "legacy_id", and
# "unresolved_legacy_ids" is the first draft of unresolved.tsv
```

Pull that once into the cache and let step 2 read it from disk, so the mapping
stays reproducible (§9.3).

`unresolved.tsv` is the deliverable of this step. Send it over — most entries
will be terms that genuinely need adding to the vocabulary, which is an
editorial decision, and a few will be ritus-local rows that were never in
eCatalogus at all.

**3 — apply.** Add a `<column>_uuid` beside each `<column>_id` and backfill it
from the mapping.

```
ritus dicts:apply --dry-run     # row counts per table, writes nothing
ritus dicts:apply               # one transaction per table
```

**Keep the old integer columns.** They are the provenance of the migration and
the join key if it has to be re-run. Just stop reading them for anything
API-facing.

**4 — verify.** Re-runnable, exits non-zero if anything regressed:

```
ritus dicts:verify
# rows with a non-null legacy id and a null uuid, per table and column
# uuids present locally but absent from the cache
```

### 9.3 What each script must guarantee

| Requirement | Why |
|---|---|
| **Idempotent** — running twice changes nothing the second time | It will be run more than once, and on production under time pressure |
| **`--dry-run` on every step** | The production run should be the second time you have seen the numbers, not the first |
| **Non-interactive** | It has to run over SSH from a deploy script |
| **Transactional per table** | A partial backfill is far worse than none |
| **Writes a log with counts** | *"4 564 rite ids: 4 561 derived, 2 by name, 1 unresolved"* is the record that the migration was sound |
| **Committed to the repository** | Same commit runs on dev, staging and production |
| **Reads the cache, never the network** | Steps 2–4 must be reproducible from a fixed snapshot |

That last one matters most. If step 2 fetches from the API directly, the
migration is not reproducible: the vocabulary can change between the dev run and
the production run, and the two databases end up mapped differently. Pin the
cache in step 1, commit the mapping files, and let steps 2–4 read only from
disk.

### 9.4 After the migration

The upload dialog changes shape considerably:

- **Send names, not UUIDs, wherever ritus has a name** (§3). The server resolves
  them, and no cache lookup happens at all.
- **`music_notation_id` is now a name too** (§5) — send `"Square notation"`, not
  `7`, and keep the skip-and-tell fallback for manuscripts whose notation has
  not been described.
- **`formula_id` is the only field that needs a cached UUID.**
- The dictionary download disappears from the upload path entirely. What remains
  is a lookup in a local TSV, and the `dry_run` you already do.


---

## What happens next, on our side

Everything below is **implemented and tested**; it goes live on each instance
with the next deployment.

1. **Both origins added to all five instances** (§1) — this is what unblocks
   you. Configuration only, no code involved.
2. **`id` removed from `/api/v1/dictionaries/` and `/package/` responses**, along
   with the raw many-to-many primary-key lists wherever a `*_uuids` companion
   already carried the same information. It was an instance-local database
   artefact with no meaning to a caller, and publishing it next to `uuid` is what
   made §3 look like a reasonable shortcut. **Stop reading it now** — the
   `/content/` endpoints never exposed it, so only your dictionary cache is
   affected.
3. **`?uuids=`, `?legacy_ids=` and `?fields=`** on `/api/v1/dictionaries/{slug}/`,
   with unknown query parameters now rejected as `400` (§4).
4. **`music_notation_id` resolvable by notation name**, against the target
   manuscript's own notation records (§5).
5. `INTEGRATION.md` corrected: the CORS claim removed, the content-field table
   given the exact lookup columns so it is visible at a glance which fields take
   a name and which insist on a UUID.

Not built, by agreement: `quire_id` sequence resolution, and read endpoints for
`EditionContent` and `Bibliography`. Ask and they go in.

And on yours, in priority order:

1. **Fix the id-based resolution (§3).** Send names wherever ritus has one —
   including `music_notation_id` now — and treat `formula_id` as the only field
   that needs a cached UUID. This is the only correctness bug in what you have
   built.
2. **Migrate the ritus database (§9)** — committed scripts, `--dry-run` first,
   `unresolved.tsv` back to us.
3. **Rework the cache around `uuid` and the admin refresh button (§8)**, and drop
   `id` from the cached TSVs.

Everything else in the implementation matches the API as designed, including the
parts that were awkward to get right — the `xBasic` handling, the `dry_run`
gate, the `append`/`replace` choice, and holding credentials in page memory
only. It is a careful piece of work; the id problem is one we handed you by
publishing a column we should not have.
