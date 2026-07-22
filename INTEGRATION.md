# eCatalogus — integration guide for external systems

This document is for the administrator of a system that needs to read data from,
or push data into, eCatalogus — for example **ritus-indexer**.

It covers the three tasks that integration usually needs:

1. creating manuscripts,
2. checking whether a manuscript already has content,
3. uploading content in bulk.

Everything here is stable API v1 under `/api/v1/`. The interactive reference,
generated from the running server, lives at `/api/schema/swagger/`.

> Replace `https://ecatalogus.example.org` below with the real host.

---

## 1. How authentication works

Reading is open — no account, no key, nothing to request:

```bash
curl https://ecatalogus.example.org/api/v1/
```

**Writing requires an eCatalogus account**, and the intended flow is that *your
user* supplies their own eCatalogus credentials at the moment of upload.

### The intended flow

ritus-indexer generates the content JSON in the browser. Before sending it, the
page asks the user to confirm who they are in eCatalogus — a small login form
with their eCatalogus username and password. The page sends those credentials
with the upload as an `Authorization: Basic` header.

```
ritus-indexer (browser)                      eCatalogus
───────────────────────                      ──────────
generate JSON in page
[eCatalogus login: ____]
[password:         ____]
[Confirm]  ──────────────────────────────>   GET  /api/v1/whoami/
           <──────────────────────────────   "Anna Kowalska, may import"
[Upload]   ──────────────────────────────>   POST /api/v1/…/content/bulk/
           <──────────────────────────────   812 rows created
```

**Nothing is stored.** The credentials live in the page's memory for the duration
of the upload and are never persisted — not in ritus-indexer's database, not in
`localStorage`. No API tokens to provision, rotate or leak.

Because each user authenticates as themselves, eCatalogus records who imported
what, and access can be granted or revoked per person.

### Granting a user the right to import

Every eCatalogus user who may push data needs to be in the **`api_importers`**
group. The eCatalogus administrator adds them in the Django admin:
*Authentication → Users → (user) → Groups → `api_importers`*.

That is the whole procedure — it works on existing accounts, takes effect
immediately, and needs no restart. Removing them from the group revokes access
just as immediately.

There is also a command for creating a dedicated account, should you ever want
an unattended one:

```bash
python manage.py create_api_integration_user some-service   # --remove to revoke
```

### Confirming an identity

```
GET /api/v1/whoami/
```

Call this as soon as the user submits the login form. It costs nothing and lets
you show a precise message instead of a generic failure:

```json
{
  "authenticated": true,
  "username": "akowalska",
  "display_name": "Anna Kowalska",
  "can_import": true
}
```

| Result | Meaning | What to tell the user |
|---|---|---|
| `401` | Wrong username or password | "Nieprawidłowy login lub hasło." |
| `200`, `can_import: false` | Credentials fine, no import rights | "Twoje konto nie ma uprawnień do importu — poproś administratora eCatalogus o dodanie do grupy `api_importers`." |
| `200`, `can_import: true` | Ready to upload | Proceed. |

A failed attempt returns `401` **without** a `WWW-Authenticate: Basic` challenge,
so the browser will *not* pop up its own native password dialog on top of your
form. You render the error yourself.

### CORS

`https://ritus-indexer.ispan.pl` is already on the allow-list, so browser calls
from that origin work without further setup. Additional origins are configured on
the eCatalogus side via the `API_INTEGRATION_ORIGINS` environment variable.

Do **not** set `credentials: 'include'` on these requests — the `Authorization`
header carries the identity, and no cookies are needed.

---

## 2. Task: create a manuscript

```
POST /api/v1/manuscripts/
```

Only `name` is required. Relation fields accept **either a UUID or the
dictionary entry's name**, so you can write `"dating": "s. XIV in."` instead of
looking up a UUID first.

```bash
curl -u ritus-indexer:PASSWORD \
     -X POST https://ecatalogus.example.org/api/v1/manuscripts/ \
     -H 'Content-Type: application/json' \
     -d '{
           "name": "Graduale Cracoviense",
           "foreign_id": "ritus-2291",
           "shelf_mark": "MS 12",
           "contemporary_repository_place": "Kraków",
           "dating": "s. XIV in.",
           "main_script": "Textualis"
         }'
```

Response `201`:

```json
{
  "uuid": "0b7622ff-91aa-46c0-a618-124cfc6fca2e",
  "name": "Graduale Cracoviense",
  "foreign_id": "ritus-2291",
  "content_count": 0,
  "entry_date": "2026-07-21T10:30:00+00:00"
}
```

**Keep the returned `uuid`** — every later call uses it.

Use `foreign_id` to store your own identifier. You can then find the manuscript
again without keeping your own mapping table:

```bash
curl 'https://ecatalogus.example.org/api/v1/manuscripts/?foreign_id=ritus-2291'
```

### If a dictionary value does not exist

The API **never invents dictionary entries**. An unknown value is an error:

```json
{
  "detail": "1 problem(s) found; the manuscript was not created.",
  "errors": [
    {
      "row": 0,
      "field": "dating",
      "value": "s. XXX",
      "error": "not_found",
      "detail": "No TimeReference entry matches \"s. XXX\" (matched against: time_description). Dictionary entries must exist before content referencing them is imported."
    }
  ]
}
```

This is deliberate — controlled vocabularies are curated inside eCatalogus. Ask
the editors to add the term, then retry. Section 5 explains how to read the
vocabularies so you can validate before sending.

---

## 3. Task: check whether a manuscript already has content

Call this before uploading, so a retry or a re-run does not create duplicates.

```
GET /api/v1/manuscripts/{uuid}/content/summary/
```

```json
{
  "manuscript_uuid": "0b7622ff-91aa-46c0-a618-124cfc6fca2e",
  "manuscript_name": "Graduale Cracoviense",
  "content_count": 812,
  "has_content": true,
  "sequence_in_ms_min": 1,
  "sequence_in_ms_max": 812,
  "last_modified": "2026-07-21T11:02:00+00:00"
}
```

It is a cheap call — safe to make before every upload.

---

## 4. Task: upload content in bulk

```
POST /api/v1/manuscripts/{uuid}/content/bulk/
```

**There is no row limit and no rate limit on this endpoint.** 800 rows in one
request is a normal, expected payload.

```json
{
  "items": [
    {
      "sequence_in_ms": 1,
      "where_in_ms_from": "1r",
      "where_in_ms_to": "1v",
      "formula_text_from_ms": "Deus qui nos patrem et matrem",
      "rubric_id": "Ad complendum",
      "liturgical_genre_id": "Missale",
      "function_id": "Oratio",
      "original_or_added": "ORIGINAL"
    },
    {
      "sequence_in_ms": 2,
      "where_in_ms_from": "1v",
      "formula_text_from_ms": "Per omnia saecula saeculorum"
    }
  ],
  "mode": "append",
  "dry_run": false
}
```

A bare JSON list is also accepted as the body, matching the older
`/content_import/` format.

### Options

| Field | Default | Meaning |
|---|---|---|
| `mode` | `append` | `append` only adds. `replace` deletes the manuscript's existing content first — use it to re-upload after corrections. |
| `dry_run` | `false` | Validate the whole payload and report every problem **without writing anything**. |
| `strict` | `true` | Reject unrecognised field names. Set `false` to ignore them instead. |

### All-or-nothing

The entire payload is validated before a single row is written, and the write
runs in one transaction. **If any row is bad, nothing is imported** — there is no
such thing as a half-finished upload.

Success, `200`:

```json
{
  "manuscript_uuid": "0b7622ff-91aa-46c0-a618-124cfc6fca2e",
  "mode": "append",
  "dry_run": false,
  "received": 812,
  "created": 812,
  "deleted": 0,
  "errors": [],
  "created_uuids": ["113baaf7-…", "…"]
}
```

Failure, `400` — every problem located by row index, field and value:

```json
{
  "detail": "2 problem(s) found; nothing was imported.",
  "errors": [
    {
      "row": 17,
      "field": "rubric_id",
      "value": "Ad conplendum",
      "error": "not_found",
      "detail": "No RiteNames entry matches \"Ad conplendum\" (matched against: name). …"
    },
    {
      "row": 204,
      "field": "sequence_in_ms",
      "value": "twelve",
      "error": "invalid_value",
      "detail": "expected a whole number, got \"twelve\""
    }
  ]
}
```

`row` is the zero-based index in the `items` list you sent.

### Recommended upload flow (browser JavaScript)

```js
const BASE = 'https://ecatalogus.example.org/api/v1';

// Built once from the login form, kept in memory only.
function authHeader(username, password) {
  return 'Basic ' + btoa(`${username}:${password}`);
}

async function confirmIdentity(auth) {
  const response = await fetch(`${BASE}/whoami/`, { headers: { Authorization: auth } });

  if (response.status === 401) {
    throw new Error('Nieprawidłowy login lub hasło do eCatalogus.');
  }
  const who = await response.json();
  if (!who.can_import) {
    throw new Error(
      `Konto ${who.username} nie ma uprawnień do importu. ` +
      'Poproś administratora eCatalogus o dodanie do grupy api_importers.'
    );
  }
  return who;
}

async function upload(manuscriptUuid, rows, auth) {
  const url = `${BASE}/manuscripts/${manuscriptUuid}/content/bulk/`;

  // 1. Do not duplicate work — this is a public read, no credentials needed.
  const summary = await (
    await fetch(`${BASE}/manuscripts/${manuscriptUuid}/content/summary/`)
  ).json();
  if (summary.has_content) {
    throw new Error(`Rękopis ma już ${summary.content_count} rekordów treści.`);
  }

  const send = (body) => fetch(url, {
    method: 'POST',
    headers: { Authorization: auth, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  // 2. Validate everything first — one request, every problem at once.
  const check = await send({ items: rows, dry_run: true });
  if (!check.ok) {
    const { errors } = await check.json();
    throw new Error(
      errors.map((e) => `wiersz ${e.row}: ${e.field} — ${e.detail}`).join('\n')
    );
  }

  // 3. Import for real.
  const result = await send({ items: rows });
  if (!result.ok) throw new Error((await result.json()).detail);

  return (await result.json()).created;
}
```

Wiring it to a form:

```js
const auth = authHeader(form.username.value, form.password.value);
const who = await confirmIdentity(auth);           // fail fast, clear message
status.textContent = `Zalogowano jako ${who.display_name}. Wysyłanie…`;
const created = await upload(manuscriptUuid, rows, auth);
status.textContent = `Zaimportowano ${created} rekordów.`;
```

Always run `dry_run` first. It costs one request and turns a rejected upload into
a complete, actionable list of corrections — which matters when the person at the
keyboard is a historian, not a programmer.

The same calls work from a server with `curl` or Python `requests`, if you ever
need an unattended import:

```bash
curl -u USER:PASSWORD -X POST \
     https://ecatalogus.example.org/api/v1/manuscripts/{uuid}/content/bulk/ \
     -H 'Content-Type: application/json' \
     -d @content.json
```

Note on timing: a large import does a fair amount of related bookkeeping per row,
so budget roughly a second per hundred rows and set a generous client timeout.
Nothing on the server side will cut the request short.

### Content fields

Relation fields (`*_id`, plus `layer`, `mass_hour`, `genre`, `season_month`,
`week`, `day`) accept a UUID **or** the entry's name.

| Field | Type | Notes |
|---|---|---|
| `sequence_in_ms` | integer | Order within the manuscript. Assigned automatically if omitted. |
| `rubric_sequence_in_the_MS` | integer | |
| `where_in_ms_from` / `where_in_ms_to` | text | Folio references, e.g. `"12v"`. |
| `digital_page_number` | integer | |
| `formula_text_from_ms` | text | The text as it stands in the manuscript. |
| `rubric_name_from_ms` | text | |
| `subrubric_name_from_ms` | text | |
| `original_or_added` | text | `ORIGINAL` or `ADDED`. |
| `proper_texts` | boolean | |
| `biblical_reference` | text | |
| `reference_to_other_items` | text | |
| `comments` | text | |
| `formula_id` | UUID | Formulas. |
| `rubric_id` | UUID or name | RiteNames. |
| `liturgical_genre_id` | UUID or title | LiturgicalGenres. |
| `section_id` / `subsection_id` | UUID or name | Sections. |
| `function_id` / `subfunction_id` | UUID or name | ContentFunctions. |
| `quire_id` | UUID | Quires. |
| `music_notation_id` | UUID | ManuscriptMusicNotations. |
| `layer`, `mass_hour`, `genre`, `season_month`, `week`, `day` | UUID or short name | |
| `text_standarization` | UUID or standard incipit | |
| `edition_index` | UUID or `"<shortname> c.<sequence>"` | EditionContent. |
| `contributor_id` | UUID or initials | Contributors. |
| `edition_subindex` | text | |
| `similarity_by_user` | text | `0`, `0.5` or `1`. |

---

## 5. Reading data back

### The controlled vocabularies

Use these to validate your values *before* uploading, and to align your own terms
with ours by citing stable UUIDs.

```bash
curl https://ecatalogus.example.org/api/v1/dictionaries/
curl 'https://ecatalogus.example.org/api/v1/dictionaries/rite-names/?limit=1000'
curl 'https://ecatalogus.example.org/api/v1/dictionaries/rite-names/?search=complend'
```

Available: `rite-names`, `liturgical-genres`, `sections`, `content-functions`,
`layers`, `mass-hours`, `genres`, `seasons-and-months`, `weeks`, `days`,
`feast-ranks`, `types`, `topics`, `ceremonies`, `traditions`, `script-names`,
`music-notation-names`, `time-reference`, `places`, `colours`, `subjects`,
`characteristics`, `decoration-types`, `decoration-techniques`, `binding-types`,
`binding-styles`, `binding-materials`, `binding-decoration-types`,
`binding-components`, `contributors`, `formulas`, `text-standarization`.

Paginate with `limit` (max 1000) and `offset`; follow `next_offset` until it is
`null`. `?since=2026-01-01T00:00:00Z` returns only entries changed since then,
which is how you keep a local mirror up to date cheaply.

Vocabularies are read-only. They are curated inside eCatalogus.

### A manuscript's content

```bash
curl 'https://ecatalogus.example.org/api/v1/manuscripts/{uuid}/content/?limit=1000'
```

The rows come back in **exactly the vocabulary the bulk import accepts**, so the
output of this endpoint can be posted straight back to another manuscript. Each
relation carries both the UUID (`rubric_id`) and a readable label
(`rubric_label`).

### The complete manuscript description

```bash
curl https://ecatalogus.example.org/api/v1/manuscripts/{uuid}/package/
```

This is everything behind the manuscript tab in the web interface —
codicology, layouts, quires, binding, decoration, origins, provenance, hands,
watermarks, content — and a **superset of the TEI XML export**, which by design
carries only what TEI can express.

The response groups records by model:

```json
{
  "manuscript_uuid": "0b7622ff-…",
  "manuscript_name": "Graduale Cracoviense",
  "model_count": 12,
  "record_count": 947,
  "models": [
    {
      "model": "indexerapp.Manuscripts",
      "count": 1,
      "results": [
        {
          "uuid": "0b7622ff-…",
          "name": "Graduale Cracoviense",
          "dating_uuid": "9c61dd43-…",
          "dating_label": "s. XIV in.",
          "place_of_origin_uuid": "4f2a…",
          "place_of_origin_label": "Kraków"
        }
      ]
    }
  ]
}
```

Every foreign key comes with a `*_label` giving the human-readable name, so the
package is readable without downloading the dictionaries first. Add
`?labels=false` for the raw UUID-only form, which is smaller and better suited to
machine-to-machine replication.

Other formats for the same manuscript:

- `GET /ms_tei/?manuscript_uuid={uuid}` — TEI XML.
- `GET /export/content/by-uuid/{uuid}/` — content as CSV.

---

## 6. Licence, attribution and citation

**Every response carries its own terms.** You never end up holding eCatalogus
data without knowing what you may do with it.

At the transport layer, on every response including errors:

```
Link: <https://creativecommons.org/licenses/by/4.0/>; rel="license"
```

And inside every payload that carries data, a `rights` block — because JSON gets
saved to a file and headers are lost the moment it does:

```json
"rights": {
  "license": "CC-BY-4.0",
  "license_name": "Creative Commons Attribution 4.0 International",
  "license_url": "https://creativecommons.org/licenses/by/4.0/",
  "copyright": "Copyright (c) 2024-2026 Instytut Sztuki Polskiej Akademii Nauk (PAN) - Polish Academy of Sciences.",
  "rights_holder": "Instytut Sztuki Polskiej Akademii Nauk (PAN)",
  "rights_holder_url": "https://ispan.pl/",
  "required_statement": "Data from eCatalogus, Instytut Sztuki Polskiej Akademii Nauk (PAN). Used under CC BY 4.0.",
  "attribution": "\"Graduale Cracoviense\", contributed by Anna Kowalska, Jan Nowak. Data from eCatalogus, Instytut Sztuki Polskiej Akademii Nauk (PAN). Used under CC BY 4.0.",
  "recommended_citation": "Anna Kowalska, Jan Nowak. \"Graduale Cracoviense\". eCatalogus. Instytut Sztuki Polskiej Akademii Nauk (PAN). accessed 2026-07-21. https://…/package/. Licensed under CC-BY-4.0.",
  "accessed": "2026-07-21T15:04:32+00:00",
  "source": "https://ecatalogus.example.org/api/v1/manuscripts/0b7622ff-…/package/",
  "contributors": [
    { "uuid": "…", "name": "Anna Kowalska", "initials": "AK", "affiliation": "Instytut Sztuki PAN", "url": null },
    { "uuid": "…", "name": "Jan Nowak",     "initials": "JN", "affiliation": "Uniwersytet Warszawski", "url": null }
  ]
}
```

### What you must do

CC BY obliges you to **credit**. Concretely:

- Display `rights.attribution` (or build your own credit from
  `rights.contributors` and `rights.rights_holder`) wherever the data is shown.
- Keep the `rights.copyright` notice with any copy you redistribute.
- Link back to `rights.license_url`.

You do **not** have to ask permission, and you may adapt and redistribute,
including commercially, as long as attribution is preserved.

### Whom to credit

`rights.contributors` is not a fixed institutional list — it is collected from
the records actually contained in *your* export. The scholars who described that
particular manuscript are named, with their affiliations. If you export two
manuscripts you will get two different lists.

That is the point: the historians who did the work are credited by name, not
absorbed into an institutional footnote.

### Citing

`rights.recommended_citation` is a ready-to-paste string, with the access date
and the exact source URL already filled in. Use it verbatim, or reformat it into
your house style — the components are all available separately.

### Other export formats

- **TEI XML** carries the same terms in the `teiHeader`, as
  `<publicationStmt><availability><licence target="…">`, plus the `respStmt`
  entries naming contributors and authors.
- **CSV** carries the licence in the HTTP `Link` header.

---

## 7. Rate limits

| Caller | Limit |
|---|---|
| Anonymous (public reads) | 600 requests/minute per IP; 60/minute on the aggregate index endpoints |
| Authenticated (any account, including yours) | **No limit** |
| ETL replication between eCatalogus instances | **No limit** |

Since your integration authenticates, **you are never throttled** — not on reads,
not on bulk imports, and there is no cap on payload size.

If you do somehow hit the anonymous limit you get `429 Too Many Requests` with a
`Retry-After` header. The fix is simply to authenticate.

---

## 8. Errors

| Status | Meaning | What to do |
|---|---|---|
| `200` | Success | |
| `201` | Manuscript created | Store the returned `uuid`. |
| `400` | Payload rejected; nothing written | Read `errors[]` — each entry gives the row, field and value. |
| `401` | Missing or wrong credentials | Ask the user to re-enter their eCatalogus password. |
| `403` | Authenticated but not authorised | The account needs to be in `api_importers`. |
| `404` | No such manuscript or dictionary | Check the UUID. |
| `429` | Anonymous rate limit | Authenticate. |

Import errors are always a list, so one round trip tells you everything that is
wrong, not just the first problem.

---

## 9. Generating this documentation

The machine-readable OpenAPI schema is served live:

```bash
curl https://ecatalogus.example.org/api/schema/ -o ecatalogus-openapi.yml
```

Or generate it from a checkout:

```bash
python manage.py spectacular --file ecatalogus-openapi.yml
```

To turn it into a standalone HTML or PDF reference:

```bash
npx @redocly/cli build-docs ecatalogus-openapi.yml -o ecatalogus-api.html
# then print ecatalogus-api.html to PDF from any browser

# Markdown, if you prefer:
npx widdershins ecatalogus-openapi.yml -o ecatalogus-api.md
```

The generated reference lists every endpoint and field. This document is the
task-oriented companion to it — send both.

---

## 10. Quick reference

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/v1/` | GET | — | Discovery |
| `/api/v1/whoami/` | GET | — | Confirm credentials and import rights |
| `/api/v1/manuscripts/` | GET | — | List and search manuscripts |
| `/api/v1/manuscripts/` | POST | ✔ | Create a manuscript |
| `/api/v1/manuscripts/{uuid}/package/` | GET | — | Full manuscript description |
| `/api/v1/manuscripts/{uuid}/content/` | GET | — | Content rows |
| `/api/v1/manuscripts/{uuid}/content/summary/` | GET | — | Does it already have content? |
| `/api/v1/manuscripts/{uuid}/content/bulk/` | POST | ✔ | Bulk import content |
| `/api/v1/dictionaries/` | GET | — | List vocabularies |
| `/api/v1/dictionaries/{slug}/` | GET | — | Read one vocabulary |
| `/api/schema/swagger/` | GET | — | Interactive reference |

`/api/etl/` also exists. It is internal replication between eCatalogus
instances, authenticated with a shared per-instance token, and is not intended
for third-party use — use `/api/v1/`.
