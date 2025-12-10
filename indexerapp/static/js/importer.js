let data;
let manuscriptId;
let traditionId;
let contributorId;
let dataTable;
let tableName;

function browseFile() {
    document.getElementById('file-input').click();
}

function handleFile() {
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];

    if (file) {
        parseCSV(file);
    }
}

function handleDragOver(event) {
    event.preventDefault();
    document.getElementById('upload-container').classList.add('dragover');
}

function handleDragLeave(event) {
    event.preventDefault();
    document.getElementById('upload-container').classList.remove('dragover');
}

function handleDrop(event) {
    event.preventDefault();
    document.getElementById('upload-container').classList.remove('dragover');

    const file = event.dataTransfer.files[0];

    if (file) {
        parseCSV(file);
    }
}

function parseCSV(file) {
    const reader = new FileReader();

    reader.onload = function (e) {
        const csvData = e.target.result;
        processData(csvData);
    };

    reader.readAsText(file);
}

function processData(csvData) {
    // Your CSV processing logic here
    // Assuming the data is in a CSV format, you can use a library like PapaParse to parse it
    Papa.parse(csvData, {
        header: true,
        skipEmptyLines: true,
        complete: function(results) {
            // Assuming results.data is an array of objects representing the CSV rows
            data = results.data;

            // Loop through each row in the parsed data
            /*
            data = data.map(row => {
                // Apply the reverse foliation logic for where_in_ms_from and where_in_ms_to columns
                if (row.where_in_ms_from) {
                    row.where_in_ms_from = row.where_in_ms_from.replace(/r$/, '.1').replace(/v$/, '.2');
                }
                if (row.where_in_ms_to) {
                    row.where_in_ms_to = row.where_in_ms_to.replace(/r$/, '.1').replace(/v$/, '.2');
                }
                return row;
            });
            */

            const columnNames = Object.keys(data[0]);

            tableName = ''
            
            if (columnNames.includes('shelf_mark')) {
                console.log(`Manuscripts table`);
                tableName='Manuscripts';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'block';

            } else if (columnNames.includes('title')) {
                console.log(`Bibliography table`);
                tableName='Bibliography';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'none';
            } else if (columnNames.includes('formula_text_from_ms')) {
                console.log(`Content table`);
                tableName='Content';

                document.getElementById('ms_selector').style.display = 'block';
                document.getElementById('contributor_selector').style.display = 'block';
            } else if (columnNames.includes('feast_rubric_sequence')) {
                console.log(`EditionContent content table`);
                tableName='EditionContent';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'block';
            } else if (columnNames.includes('co_no')) {
                console.log(`Formulas table`);
                tableName='Formulas';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'none';
            } else if (columnNames.includes('english_translation')) {
                console.log(`RiteNames table`);
                tableName='RiteNames';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'none';
            } else if (columnNames.includes('clla_no')) {
                console.log(`Clla table`);
                tableName='Clla';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'none';
            } else if (columnNames.includes('longitude')) {
                console.log(`Places table`);
                tableName='Places';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'none';
            } else if (columnNames.includes('century_from')) {
                console.log(`TimeReference table`);
                tableName='TimeReference';

                document.getElementById('ms_selector').style.display = 'none';
                document.getElementById('contributor_selector').style.display = 'none';
            } else {
                alert(`Unknown table! Column names unknown!`);
            }

            // Perform data validation
            const validationErrors = validateData(data, tableName);

            if (validationErrors.length === 0) {
                // Data is valid, display the table
                displayTable();
            } else {
                // Display validation errors
                document.getElementById('error-info').innerText = 'Errors:\n ' + validationErrors.join(',\n ');
            }
        }
    });
}

expectedColumnNamesByTable = {
    'Content': [
        'id', 'manuscript_id', 'sequence_in_ms', 'formula_id', 'formula_text_from_ms',
        'similarity_by_user', 'where_in_ms_from', 'where_in_ms_to', 'digital_page_number', 'rubric_name_from_ms', 'subrubric_name_from_ms',
        'rubric_id', 'rubric_sequence_in_the_MS', 'original_or_added', 'biblical_reference',
        'reference_to_other_items', 'edition_index', 'edition_subindex', 'comments', 'function_id', 'subfunction_id',
        'liturgical_genre_id', 'music_notation_id', 'quire_id', 'section_id', 'subsection_id',
        'contributor_id', 'entry_date'
    ],
    'Manuscripts': [
        'id', 'main_script',	'how_many_columns_mostly',	'lines_per_page_usually',	'how_many_quires',	'quires_comment',	'foliation_or_pagination',	'decorated',	'decoration_comments',	'music_notation', 'music_notation_comments',	'binding_date',	'binding_place',	'links',	'iiif_manifest_url', 'form_of_an_item', 'connected_ms', 'where_in_connected_ms', 'general_comment', 'additional_url',	'display_as_main',  'authors',	'data_contributor'
    ],
    'Bibliography': [
        'title',	'author',	'shortname',	'year',	'zotero_id',	'hierarchy'
    ],
    'Formulas': [
        'id',	'co_no',	'text'
    ],
    'RiteNames': [
        'name',	'english_translation',	'section',	'votive'
    ],
    'TimeReference': [
        'time_description',	'century_from',	'century_to',	'year_from',	'year_to'
    ],
    'EditionContent': [
        'bibliography_id',	'formula_id',	'rubric_name_standarized',	'feast_rubric_sequence',	'subsequence',	'page',	'function',	'subfunction',	'authors',	'data_contributor'
    ],
    'Places': [
        'longitude','latitude','place_type','country_today_eng','region_today_eng','city_today_eng','repository_today_eng','country_today_local_language','region_today_local_language','city_today_local_language','repository_today_local_language','country_historic_eng','region_historic_eng','city_historic_eng','repository_historic_eng','country_historic_local_language','region_historic_local_language','city_historic_local_language','repository_historic_local_language','country_historic_latin','region_historic_latin','city_historic_latin','repository_historic_latin',
    ],
    'Clla': [
        'manuscript_id','clla_no','liturgical_genre','dating','dating_comment','provenance','provenance_comment','comment'
    ]

}

function validateClla(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( row.manuscript_id.length < 1 ) {
            errors.push(`obligatory field "manuscript_id" is too short at row ${rowIndex + 1}.`);
        }

        if ( !isInteger(row.manuscript_id) && row.manuscript_id != "" ) {
            errors.push(`Invalid integer value in manuscript_id at row ${rowIndex + 1}. Value: "${row.manuscript_id}"`);
        }
    });

    return errors;
}

function validatePlaces(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( !isFloat(row.longitude) && row.longitude != "") {
            errors.push(`Invalid float value in longitude at row ${rowIndex + 1}. Value: "${row.longitude}"`);
        }
        if ( !isFloat(row.latitude) && row.latitude != "") {
            errors.push(`Invalid float value in latitude at row ${rowIndex + 1}. Value: "${row.latitude}"`);
        }
        if( !(row.place_type=="library" || row.place_type=="center" || row.place_type=="scriptory" || row.place_type=="multiple" || row.place_type=="" || !row.place_type ) )
        {
            errors.push(`Invalid value in place_type at row ${rowIndex + 1}. Value: "${row.place_type}". Only "library", "center", "scriptory", "multiple" or empty is allowed"`);
        }
    });

    return errors;
}


function validateManuscripts(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( row.name.length < 3 ) {
            errors.push(`obligatory field "name" is too short at row ${rowIndex + 1}.`);
        }

        if ( row.how_many_columns_mostly && !isInteger(row.how_many_columns_mostly) && row.how_many_columns_mostly != "") {
            errors.push(`Invalid integer value in how_many_columns_mostly at row ${rowIndex + 1}. Value: "${row.how_many_columns_mostly}"`);
        }

        if ( row.lines_per_page_usually && !isInteger(row.lines_per_page_usually) && row.lines_per_page_usually != "") {
            errors.push(`Invalid integer value in lines_per_page_usually at row ${rowIndex + 1}. Value: "${row.lines_per_page_usually}"`);
        }

        if ( row.how_many_quires && !isInteger(row.how_many_quires) && row.how_many_quires != "") {
            errors.push(`Invalid integer value in how_many_quires at row ${rowIndex + 1}. Value: "${row.how_many_quires}"`);
        }
        if( row.foliation_or_pagination && !(row.foliation_or_pagination=="FOLIATION" || row.foliation_or_pagination=="PAGINATION" || row.foliation_or_pagination=="") )
        {
            errors.push(`Invalid value in foliation_or_pagination at row ${rowIndex + 1}. Value: "${row.foliation_or_pagination}". Only "PAGINATION", "FOLIATION" or empty is allowed"`);
        }

        if( row.decorated && !(row.decorated=="yes" || row.decorated=="no" || row.decorated=="") )
        {
            errors.push(`Invalid value in decorated at row ${rowIndex + 1}. Value: "${row.decorated}". Only "yes", "no" or empty is allowed"`);
        }
        if( row.music_notation && !(row.music_notation=="yes" || row.music_notation=="no" || row.music_notation=="") )
        {
            errors.push(`Invalid value in music_notation at row ${rowIndex + 1}. Value: "${row.music_notation}". Only "yes", "no" or empty is allowed"`);
        }

        if( row.form_of_an_item && !(row.form_of_an_item=="C" || row.form_of_an_item=="F" || row.form_of_an_item=="P" || row.form_of_an_item=="L" || row.form_of_an_item=="") )
        {
            errors.push(`Invalid value in form_of_an_item at row ${rowIndex + 1}. Value: "${row.form_of_an_item}". Only "C", "F", "P", "L" or empty is allowed"`);
        }
        // Add more specific checks for other data types as needed
    });

    return errors;
}

function validateBibliography(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( row.shortname.length > 5 ) {
            errors.push(`Invalid shortname length at row ${rowIndex + 1}. Value: "${row.shortname}"`);
        }

        if (!isInteger(row.year) && row.year != "") {
            errors.push(`Invalid integer value in year at row ${rowIndex + 1}. Value: "${row.year}"`);
        }

        if (!isInteger(row.hierarchy) && row.hierarchy != "") {
            errors.push(`Invalid integer value in hierarchy at row ${rowIndex + 1}. Value: "${row.hierarchy}"`);
        }
    });

    return errors;
}

function validateContent(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( !isInteger(row.formula_id) && row.formula_id != "") {
            errors.push(`Invalid integer value in formula_id at row ${rowIndex + 1}. Value: "${row.formula_id}"`);
        }
        if ( !isInteger(row.sequence_in_ms) && row.sequence_in_ms != "") {
            errors.push(`Invalid integer value in sequence_in_ms at row ${rowIndex + 1}. Value: "${row.sequence_in_ms}"`);
        }
        if ( !isInteger(row.digital_page_number) && row.digital_page_number != "") {
            errors.push(`Invalid integer value in digital_page_number at row ${rowIndex + 1}. Value: "${row.digital_page_number}"`);
        }
        /*
        if (row.where_in_ms_to && !isFloat(row.where_in_ms_to)) {
            errors.push(`Invalid float value in where_in_ms_to at row ${rowIndex + 1}. Value: "${row.where_in_ms_to}"`);
        }
        if (row.where_in_ms_from && !isFloat(row.where_in_ms_from)) {
            errors.push(`Invalid float value in where_in_ms_from at row ${rowIndex + 1}. Value: "${row.where_in_ms_from}"`);
        }*/
        
    });

    return errors;
}

function validateEditionContent(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( !isInteger(row.bibliography_id) ) {
            errors.push(`Invalid integer value in bibliography_id at row ${rowIndex + 1}. Value: "${row.bibliography_id}"`);
        }
        if ( !isInteger(row.formula_id)  && row.formula_id != "" ) {
            errors.push(`Invalid integer value in formula_id at row ${rowIndex + 1}. Value: "${row.formula_id}"`);
        }

        if ( !isFloat(row.feast_rubric_sequence) && row.feast_rubric_sequence != "") {
            errors.push(`Invalid integer value in feast_rubric_sequence at row ${rowIndex + 1}. Value: "${row.feast_rubric_sequence}"`);
        }
        if ( !isInteger(row.subsequence) && row.subsequence != "") {
            errors.push(`Invalid integer value in subsequence at row ${rowIndex + 1}. Value: "${row.subsequence}"`);
        }
        if ( !isInteger(row.page) && row.page != "") {
            errors.push(`Invalid integer value in page at row ${rowIndex + 1}. Value: "${row.page}"`);
        }
    });

    return errors;
}

function validateFormulas(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( !isInteger(row.id) ) {
            errors.push(`Invalid integer value in id at row ${rowIndex + 1}. Value: "${row.id}"`);
        }
    });

    return errors;
}

function validateRiteNames(data) {
    const errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( !(row.votive == "yes" || row.votive == "no" || row.votive == "")) {
            errors.push(`Invalid value in votive at row ${rowIndex + 1}. Value: "${row.votive}" - only yes/no or empty is allowed"`);
        }
    });

    return errors;
}

function validateTimeReference(data) {
    let errors = [];

    // Check data types
    data.forEach((row, rowIndex) => {
        if ( !isInteger(row.century_from) ) {
            errors.push(`Invalid integer value in century_from at row ${rowIndex + 1}. Value: "${row.century_from}"`);
        }
        if ( !isInteger(row.century_to) ) {
            errors.push(`Invalid integer value in century_to at row ${rowIndex + 1}. Value: "${row.century_to}"`);
        }
        if ( !isInteger(row.year_from) ) {
            errors.push(`Invalid integer value in year_from at row ${rowIndex + 1}. Value: "${row.year_from}"`);
        }
        if ( !isInteger(row.year_to) ) {
            errors.push(`Invalid integer value in year_to at row ${rowIndex + 1}. Value: "${row.year_to}"`);
        }
    });

    return errors;
}


function validateData(data, tableName) {
    let errors = [];

    // Check if the first row has the correct column names
    const expectedColumnNames = expectedColumnNamesByTable[tableName];

    const actualColumnNames = Object.keys(data[0]);

    if (!arraysEqual(expectedColumnNames, actualColumnNames)) {
        errors.push('Invalid column names');
    }

    isDataValid = false;
    if(tableName=='Manuscripts')
    {
        errors = validateManuscripts(data);
    }
    else if(tableName=='Bibliography')
    {
        errors = validateBibliography(data);
    }
    else if(tableName=='Content')
    {
        errors = validateContent(data);
    }
    else if(tableName=='EditionContent')
    {
        errors = validateEditionContent(data);
    }
    else if(tableName=='Formulas')
    {
        errors = validateFormulas(data);
    }
    else if(tableName=='RiteNames')
    {
        errors = validateRiteNames(data);
    }
    else if(tableName=='TimeReference')
    {
        errors = validateTimeReference(data);
    }
    else if(tableName=='Clla')
    {
        errors = validateClla(data);
    }
    else if(tableName=='Places')
    {
        errors = validatePlaces(data);
    }
    else{
        errors.push('Invalid Table!')
    }

    return errors;
}

function arraysEqual(arr1, arr2) {
    return JSON.stringify(arr1) === JSON.stringify(arr2);
}

function isInteger(value) {
    return /^\d+$/.test(value);
}

function isFloat(value) {
    return /^-?\d+(\.\d+)?$/.test(value);
}

function displayTable() {
    // Assuming your data is an array of objects with keys corresponding to column names
    const columns = Object.keys(data[0]);

    // Clear existing table content

    if(dataTable)
        dataTable.destroy(false);
    $('#data-table').empty();

    // Append the table headers
    const thead = $('<thead>');
    const tr = $('<tr>');
    columns.forEach(column => {
        tr.append('<th>' + column + '</th>');
    });
    thead.append(tr);
    $('#data-table').append(thead);

    // Append the table body
    const tbody = $('<tbody>');
    data.forEach(row => {
        const tr = $('<tr>');
        columns.forEach(column => {
            tr.append('<td>' + row[column] + '</td>');
        });
        tbody.append(tr);
    });
    $('#data-table').append(tbody);

    // Show the table, error info, and send to server button
    document.getElementById('data-table').style.display = 'table';
    document.getElementById('error-info').innerText = '';
    document.getElementById('send-to-server').style.display = 'block';

    // Convert the table to DataTable with explicit column definition
    dataTable = $('#data-table').DataTable({
        columns: columns.map(column => ({ data: column }))
    });
}

function sendToServer() {
    // Display loading info

    if(tableName == 'Content')
    {

        if (! (manuscriptId > 0 && manuscriptId < 99999999))
        {
            alert('You have to select manuscript from the list!');
            return;
        }

        data.forEach(row => {
            row.manuscript_id = manuscriptId;
        });
    }

    if(tableName == 'Content' || tableName == 'EditionContent' || tableName == 'Manuscripts')
    {
        if (! (contributorId > 0 && contributorId < 99999999))
        {
            alert('You have to select contributor from the list!')
            return;
        }

        data.forEach(row => {
            row.contributor_id = contributorId;

            if( !row.id )
                row.id=''
        
            if( !row.how_many_columns_mostly)
                row.how_many_columns_mostly=''
    
            if( !row.lines_per_page_usually)
                row.lines_per_page_usually=''
    
            if( !row.how_many_quires)
                row.how_many_quires=''
        
            if( !row.foliation_or_pagination)
                row.foliation_or_pagination=''
        
            if( !row.decorated)
                row.decorated=''
        
            if( !row.music_notation)
                row.music_notation=''
    
            if( !row.form_of_an_item)
                row.form_of_an_item=''

            if(!row.main_script)
                row.main_script =''

            if(!row.binding_date)
                row.binding_date =''
            
            if(!row.binding_place)
                row.binding_place =''

            if(!row.place_of_origin)
                row.place_of_origin=''
        
        });
    }


    document.getElementById('loading-info').style.display = 'block';

    url = '';
    if(tableName=='Content')
        url = '/content_import/';
    else if(tableName=='Manuscripts')
        url = '/manuscripts_import/';
    else if(tableName=='Bibliography')
        url = '/bibliography_import/';
    else if(tableName=='EditionContent')
        url = '/editioncontent_import/';
    else if(tableName=='Formulas')
        url = '/formulas_import/';
    else if(tableName=='RiteNames')
        url = '/ritenames_import/';
    else if(tableName=='TimeReference')
        url = '/timereference_import/';
    else if(tableName=='Places')
        url = '/places_import/';
    else if(tableName=='Clla')
        url = '/clla_import/';
    else
    {
        console.error("Unknown tableName. '"+tableName+"' Cannot send AJAX - no url");
        return;
    }

    // Your AJAX request to send data to the server
    $.ajax({
        url: url,
        type: 'POST',
        data: JSON.stringify(data),
        contentType: 'application/json',
        success: function (response) {
            handleServerResponse(response);
        },
        error: function () {
            handleServerResponse({info: 'error'});
        }
    });
}

function handleServerResponse(response) {
    // Hide loading info
    document.getElementById('loading-info').style.display = 'none';

    // Display success or error info
    if (response.info === 'success') {
        alert('Data sent successfully!');

        location.reload();

        if(dataTable)
            dataTable.destroy(false);
        $('#data-table').empty();


        document.getElementById('error-info').innerText = '';
        document.getElementById('data-table').innerText = '';

    } else {
        console.log('import error');
        console.log(response);
        document.getElementById('error-info').innerText = 'Error: ' + response.info;
    }
}

function downloadContentCSV() {

    if (!(manuscriptId > 0 && manuscriptId < 99999999)) {
        alert('You have to select a manuscript from the list!');
        return;
    }

    // Trigger the download
    const url = pageRoot+`/export/content/${manuscriptId}/`;
    window.location.href = url;
}

importer_init = function()
{
    console.log('importer_init');


    $('.manuscript_filter').select2({
        ajax: {
            url: pageRoot+'/manuscripts-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          }
    });

    $('.manuscript_filter').on('select2:select', function (e) {
        var data = e.params.data;
        var id = data.id;
        console.log(id);

        manuscriptId = id;
        document.getElementById('download-csv-from-server').style.display = 'block';
        document.getElementById("delete-ms-content").style.display = 'block';

        if(traditionId >=0 && traditionId < 9999999999)
            document.getElementById("content-to-tradition").style.display = 'block';

        //content_table.columns(0).search(id).draw();
    });


        $('.tradition_filter').select2({
        ajax: {
            url: pageRoot+'/traditions-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          }
    });

    $('.tradition_filter').on('select2:select', function (e) {
        var data = e.params.data;
        var id = data.id;
        console.log(id);

        traditionId = id;
        document.getElementById("delete-tradition-content").style.display = 'block';

        if(manuscriptId >=0 && manuscriptId < 9999999999)
            document.getElementById("content-to-tradition").style.display = 'block';

        //content_table.columns(0).search(id).draw();
    });



    $('.contributor_filter').select2({
        ajax: {
            url: pageRoot+'/contributors-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          }
    });

    $('.contributor_filter').on('select2:select', function (e) {
        var data = e.params.data;
        var id = data.id;
        console.log(id);

        contributorId = id;

        //content_table.columns(0).search(contributor_id).draw();
    });
}

function deleteMSContent() {
    if (!(manuscriptId > 0 && manuscriptId < 99999999)) {
        alert('You have to select a manuscript from the list!');
        return;
    }

    if (confirm('Are you sure you want to delete all content for this manuscript?')) {
        fetch(pageRoot+`/delete/content/${manuscriptId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')  // Include CSRF token for security
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`Successfully deleted ${data.deleted_count} items.`);
            } else {
                alert('Failed to delete content.');
            }
        })
        .catch(error => console.error('Error:', error));
    }
}

function deleteTraditionContent() {
    if (!(traditionId > 0 && traditionId < 99999999)) {
        alert('You have to select a tradition from the list!');
        return;
    }

    if (confirm('Are you sure you want to delete all content assigned with this tradition?')) {
        fetch(pageRoot+`/delete/tradition-formulas/${traditionId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')  // Include CSRF token for security
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`Successfully deleted ${data.deleted_count} items.`);
            } else {
                alert('Failed to delete content.');
            }
        })
        .catch(error => console.error('Error:', error));
    }
}

function assignMSContentToTheTradition() {
    if (!(manuscriptId > 0 && manuscriptId < 99999999)) {
        alert('You have to select a manuscript from the list!');
        return;
    }

    if (!(traditionId > 0 && traditionId < 99999999)) {
        alert('You have to select a tradition from the list!');
        return;
    }

    if (confirm('Are you sure you want to assign all content from the manuscript to the tradition?')) {
        fetch(pageRoot+`/assign-ms-content-to-tradition/${manuscriptId}/${traditionId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')  // Include CSRF token for security
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`Successfully assigned ${data.assigned_count} items.`);
            } else {
                alert('Failed to assign content.');
            }
        })
        .catch(error => console.error('Error:', error));
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}