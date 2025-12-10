let prayers = [];
let foliationOrPagination = '';
let numberOfPages = 0;
let contentTable = [];

// Define headers as a constant string so it's easy to replace
const CSV_HEADERS_STRING = "sequence_in_ms,formula_id,formula_text_from_ms,similarity_by_user,where_in_ms_from,where_in_ms_to,digital_page_number,rubric_name_from_ms,subrubric_name_from_ms,rubric_id,rubric_sequence_in_the_MS,original_or_added,biblical_reference,reference_to_other_items,edition_index,comments,function_id,subfunction_id,liturgical_genre_id,music_notation_id,quire_id,section_id,subsection_id,contributor_id,entry_date";
const HEADERS = CSV_HEADERS_STRING.split(',');

function parseCatalogue() {
    const catalogueText = document.getElementById('catalogueText').value;
    let ritesWithPageNumber = catalogueText.split(';').map(x => x.trim()).filter(x => x);
    console.log('Split rites:', ritesWithPageNumber);

    prayers = ritesWithPageNumber.map((item, idx) => {
    let match = item.match(/\(([^()]*)\)\s*$/);
    if (!match) return null;
    let page = match[1].trim();
    let text = item.replace(/\([^()]*\)\s*$/, '').trim();

    if (/^f\.?/i.test(page)) foliationOrPagination = 'f';
    else if (/^p\.?/i.test(page)) foliationOrPagination = 'p';

    // Remove prefix like f., p., f, p
    let cleanPage = page.replace(/^(f\.?|p\.?)/i, '').trim();

    return { riteText: text, where_in_ms_from: cleanPage, originalIndex: idx+1 };
    }).filter(x => x);

    console.log('Prayers:', prayers);

    let maxPage = Math.max(...prayers.map(p => parseInt(p.where_in_ms_from)));
    numberOfPages = foliationOrPagination === 'f' ? maxPage * 2 : maxPage;
    console.log('Number of Pages:', numberOfPages);

    // Build content table
    contentTable = [];
    for (let i = 1; i <= numberOfPages; i++) {
    let where = '';
    if (foliationOrPagination === 'f') {
        let folio = Math.ceil(i/2);
        where = folio + (i % 2 === 1 ? 'r' : 'v');
    } else {
        where = i.toString();
    }

    let row = {};
    HEADERS.forEach(h => row[h] = '');
    row.where_in_ms_from = where;
    row.digital_page_number = i;
    contentTable.push(row);
    }

    // Fill prayers into table
    prayers.forEach(prayer => {
    let lastIndex = -1;
    contentTable.forEach((row, idx) => {
        if (row.where_in_ms_from === prayer.where_in_ms_from) {
        lastIndex = idx;
        }
    });
    if (lastIndex >= 0) {
        if (contentTable[lastIndex].rubric_name_from_ms === '') {
        contentTable[lastIndex].rubric_name_from_ms = prayer.riteText;
        contentTable[lastIndex].rubric_sequence_in_the_MS = prayer.originalIndex;
        contentTable[lastIndex].sequence_in_ms = prayer.originalIndex;
        } else {
        let duplicate = { ...contentTable[lastIndex] };
        duplicate.rubric_name_from_ms = prayer.riteText;
        duplicate.rubric_sequence_in_the_MS = prayer.originalIndex;
        duplicate.sequence_in_ms = prayer.originalIndex;
        contentTable.splice(lastIndex+1, 0, duplicate);
        }
    }
    });

    console.log('Content Table:', contentTable);
}

function displayTable() {
    parseCatalogue();
    if (!contentTable.length) return;
    let table = '<table><tr>';
    HEADERS.forEach(h => table += `<th>${h}</th>`);
    table += '</tr>';

    contentTable.forEach(row => {
    table += '<tr>';
    HEADERS.forEach(h => table += `<td>${row[h]}</td>`);
    table += '</tr>';
    });
    table += '</table>';

    document.getElementById('output').innerHTML = table;
}

function downloadCSV() {
    parseCatalogue();
    if (!contentTable.length) return;
    let csv = CSV_HEADERS_STRING + '\n';
    contentTable.forEach(row => {
    let values = HEADERS.map(h => `"${row[h]}"`);
    csv += values.join(',') + '\n';
    });

    let blob = new Blob([csv], { type: 'text/csv' });
    let url = URL.createObjectURL(blob);
    let a = document.createElement('a');
    a.href = url;
    a.download = 'contentTable.csv';
    a.click();
    URL.revokeObjectURL(url);
}

function catalogue_parser_init() {
    
}