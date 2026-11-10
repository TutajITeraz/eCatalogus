# Cantus dictionaries — seed data

Loaded by migration `indexerapp/0027_seed_chant_dictionaries`.

| file | model | source |
|---|---|---|
| `chant_modes.tsv` | `ChantMode` | Cantus mode codes after https://cantusdatabase.org/description/ (68 codes) |
| `07_differentiae_database.tsv` | `ChantDifferentia` | Differentiae Database, Rebecca Shaw — see `07_differentiae_database.LICENSE.txt` |

`07_differentiae_database.tsv` is licensed **CC BY-NC-SA 4.0**, not under the eCatalogus data
licence. Changes made here, in addition to those listed in the licence file: the columns
`no_of_mss` and `chants_in_cantus_pl` were removed. `chant_modes.tsv` keeps only `short_name`
and `name` of the Ritus+ file `03b_chant_modes_dictionary.tsv`.
