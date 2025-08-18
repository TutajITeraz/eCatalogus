const colorPalette = [
    '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
    '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4',
    '#469990', '#dcbeff', '#9A6324', '#fffac8', '#800000',
    '#aaffc3', '#808000', '#ffd8b1'
];
let traditionColors = {
};
let traditionMap = {
};
let IDENTIFY_TRADITIONS = false;
let colorIndex = 0;

function displayUniqueAuthorsAndContributors(dataTable, divToAppend) {
    var table = dataTable.table();

    var uniqueAuthors = [];
    var uniqueContributors = [];

    table.rows().every(function () {
        var rowData = this.data();
        var authors = "";
        if (Array.isArray(rowData.authors)) {
            authors = rowData.authors.join(', ');
        }

        if (!uniqueAuthors.includes(authors)) {
            uniqueAuthors.push(authors);
        }
        if (!uniqueContributors.includes(rowData.data_contributor)) {
            uniqueContributors.push(rowData.data_contributor);
        }
    });

    // Render unique values in a div below the table
    var uniqueValuesDiv = $('<div>');
    var authorsString = uniqueAuthors.join(', ');
    var contributorsString = uniqueContributors.join(', ');

    var combinedParagraph = '<p class="printIt"><strong>Authors:</strong>' + authorsString + '. <strong>Data Contributors</strong>: ' + contributorsString + '</p>';
    uniqueValuesDiv.append(combinedParagraph);

    $(divToAppend).after(uniqueValuesDiv);
}


function displaOriginalAddedLegend(dataTable, divToAppend) {
    var table = dataTable.table();

    // Render unique values in a div below the table
    var mainDiv = $('<div class="printIt" style="margin-top:0.5em;">'
        + '<div class="medieval-row" style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em;  margin-left: 1em; text-align: middle"></div>'
        + '<i>Original</i>'
        + '<div style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em; margin-left: 1em; text-align: middle" class="non-medieval-row"></div>'
        + '<i>Added</i></div>');

    $(divToAppend).after(mainDiv);
}

function displayTraditionLegend(dataTable, divToAppend) {
    const genreId = $('#genreSelect').val();
    if (!genreId) {
        const allTraditions = Object.keys(traditionColors);
        let html = '<div class="printIt" style="margin-top:0.5em;">';
        allTraditions.forEach(trad => {
            const tradColor = traditionColors[trad];
            const displayText = trad === 'Unattributed' ? 'Unattributed' : trad === 'Multiple' ? 'Multiple traditions' : trad;
            html += `<div style="display: inline-block; margin-right:0.5em; margin-left:1em; text-align:middle;">
                        <span class="dot" style="background-color: ${tradColor};" title="${displayText}"></span>
                        <i>${displayText}</i>
                     </div>`;
        });
        html += '</div>';

        $(divToAppend).next('.printIt').remove();
        $(divToAppend).after(html);
        return;
    }

    function fetchTraditions(page = 1, accumulatedResults = []) {
        $.ajax({
            url: `${pageRoot}/traditions-autocomplete/?genre=${genreId}&page=${page}`,
            dataType: 'json',
            xhrFields: {
                withCredentials: true
            },
            success: function(response) {
                const results = response.results || [];
                accumulatedResults = accumulatedResults.concat(results);

                if (response.pagination && response.pagination.next) {
                    fetchTraditions(page + 1, accumulatedResults);
                } else {
                    traditionMap = { 'Unattributed': 'Unattributed' };
                    accumulatedResults.forEach(trad => {
                        traditionMap[trad.id] = trad.text;
                        if (!traditionColors[trad.text]) {
                            traditionColors[trad.text] = colorPalette[colorIndex % colorPalette.length];
                            colorIndex++;
                        }
                    });

                    const allTraditions = Object.keys(traditionColors);
                    let html = '<div class="printIt" style="margin-top:0.5em;">';
                    allTraditions.forEach(trad => {
                        const tradColor = traditionColors[trad];
                        const displayText = trad === 'Unattributed' ? 'Unattributed' : trad === 'Multiple' ? 'Multiple traditions' : trad;
                        html += `<div style="display: inline-block; margin-right:0.5em; margin-left:1em; text-align:middle;">
                                    <span class="dot" style="background-color: ${tradColor};" title="${displayText}"></span>
                                    <i>${displayText}</i>
                                 </div>`;
                    });
                    html += '</div>';

                    $(divToAppend).next('.printIt').remove();
                    $(divToAppend).after(html);
                }
            },
            error: function() {
                const allTraditions = Object.keys(traditionColors);
                let html = '<div class="printIt" style="margin-top:0.5em;">';
                allTraditions.forEach(trad => {
                    const tradColor = traditionColors[trad];
                    const displayText = trad === 'Unattributed' ? 'Unattributed' : trad === 'Multiple' ? 'Multiple traditions' : trad;
                    html += `<div style="display: inline-block; margin-right:0.5em; margin-left:1em; text-align:middle;">
                                <span class="dot" style="background-color: ${tradColor};" title="${displayText}"></span>
                                <i>${displayText}</i>
                             </div>`;
                });
                html += '</div>';

                $(divToAppend).next('.printIt').remove();
                $(divToAppend).after(html);
            }
        });
    }

    fetchTraditions();
}




content_comparator_init = function()
{
    $(document).ready(function(){
        $("#content_left_wrapper .dt-layout-row").eq(0).css({
            "position": "sticky",
            "top": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
        $("#content_left_wrapper .dt-layout-row").eq(2).css({
            "position": "sticky",
            "bottom": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
        $("#content_right_wrapper .dt-layout-row").eq(0).css({
            "position": "sticky",
            "top": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
        $("#content_right_wrapper .dt-layout-row").eq(2).css({
            "position": "sticky",
            "bottom": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });

        setTimeout(function() {
            setTableHeight();
        }, 700);
    });

    $(window).resize(function() {
        $("#content_left_wrapper .dt-layout-row").eq(0).css({
            "position": "sticky",
            "top": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
        $("#content_left_wrapper .dt-layout-row").eq(2).css({
            "position": "sticky",
            "bottom": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
        $("#content_right_wrapper .dt-layout-row").eq(0).css({
            "position": "sticky",
            "top": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
        $("#content_right_wrapper .dt-layout-row").eq(2).css({
            "position": "sticky",
            "bottom": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });

        setTableHeight();
    });

    function setTableHeight() {
        var windowHeight = $(window).height();
        var windowWidth = $(window).width();
        // console.log('height: ', windowWidth);
        if(windowWidth > 640){
            var tableHeight = windowHeight - 382;
        } else {
            var tableHeight = windowHeight - 352;
        }
        
        
        $('.two_columns').css('height', tableHeight + 'px');
    }


    // var content_table_left = $('#content_left').DataTable({
    //     "ajax": {
    //         "url": pageRoot+"/api/content/?format=datatables", // Add your URL here
    //         "dataSrc": function (data) {
    //             var processedData=[]

    //             for(var c in data.data)
    //             {
    //                 processedData[c] = {}
    //                 for(var f in data.data[c])
    //                 {
    //                     processedData[c][f] = getPrintableValues(f,data.data[c][f]).value;
    //                 }
    //             }
                
    //             return processedData;
    //         }
    //     },
    //     "processing": false,
    //     "serverSide": true,
    //     "lengthMenu": [ [10, 25, 50, 100, -1], [10, 25, 50, 100, "All"] ],
    //     "pagingType": "full_numbers",
    //     "pageLength": 25,
    //     "columns": [
    //         { "data": "manuscript", "title": "Manuscript ID", "visible": false },
    //         { "data": "manuscript_name", "title": "Manuscript" },
    //         { "data": "where_in_ms_from", "title": "Where in MS (from)" },
    //         { "data": "where_in_ms_to", "title": "Where in MS (to)" },
    //         { "data": "rite_name_from_ms", "title": "Rite name from MS" },
    //         { "data": "subsection", "title": "Subsection" },
    //         { "data": "function", "title": "Function / Genre" },
    //         { "data": "subfunction", "title": "Subgenre" },
    //         { "data": "biblical_reference", "title": "Biblical reference" },
    //         { "data": "formula_standarized", "title": "Formula (standarized)" },
    //         { "data": "formula_text", "title": "Formula (text from MS)" },
    //         { 
    //             "data": "similarity_levenshtein_percent", 
    //             "title": "Similarity (levenshtein)",
    //             "render": function (data, type, row, meta) {
    //                 return row.similarity_levenshtein_percent + "%";
    //             },
    //             "createdCell": function(td, cellData, rowData, row, col) {
    //                 if(cellData == '-' || !cellData || cellData < 50)
    //                     $(td).css("color", "red");
    //                 else if( cellData > 99.9)
    //                     $(td).css("color", "green");
    //                 else
    //                     $(td).css("color", "#a66b00");
    //             },
    //         },
    //         { "data": "similarity_by_user", "title": "Similarity (by user)" },
    //         { "data": "original_or_added", "title": "Original or Added", "visible": false },
    //         { "data": "quire", "title": "Quire" },
    //         { "data": "music_notation", "title": "Music Notation" },


    //         { "data": "sequence_in_ms", "title": "Sequence in MS" },
    //         { "data": "proper_texts", "title": "Proper texts", searchable: false },



    //         { "data": 'subrite_name_from_ms', "title": "Subrite name from MS", searchable: false },
    //         { "data": 'edition_index', "title": "Edition Index", searchable: false },
    //         { "data": 'edition_subindex', "title": "Edition Subindex", searchable: false },


    //         { "data": "authors", "title": "Authors" },
    //         { "data": "data_contributor", "title": "Data contributor" }
    //         // Add more columns as needed
    //     ],
    //     "createdRow": function(row, data, dataIndex) {
    //         if (data.original_or_added == "ORIGINAL") {
    //             $(row).addClass('medieval-row');
    //         } else if (data.original_or_added == "ADDED")  {
    //             $(row).addClass('non-medieval-row');
    //         }
    //     }
    // });

    function content_table_init(reinit=false, filter_selector, table_selector)
    {
        ms_id = parseInt($(filter_selector).val());
        if(isNaN(ms_id))
            ms_id = null;
        content_table = $(table_selector).DataTable({
            "destroy": reinit,
            "ajax": {
                "url": pageRoot + "/api/content/?format=datatables", // Add your URL here
                "dataSrc": function (data) {
                    var processedData = []

                    for (var c in data.data) {
                        processedData[c] = {}
                        for (var f in data.data[c]) {
                            processedData[c][f] = getPrintableValues(f, data.data[c][f]).value;
                        }
                    }

                    return processedData;
                }
            },
            "processing": false,
            "serverSide": true,
            "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
            "pagingType": "full_numbers",
            "pageLength": 10,
            "bAutoWidth": false, 
            "columns": [
                { "data": "manuscript", "title": "Manuscript ID", "visible": false },
                { "data": "sequence_in_ms", "title": "sequence in MS", "visible": false },
                { "data": "manuscript_name", "title": "Manuscript", "visible": false },
                { "data": "where_in_ms_from", "title": "Where in MS (from)", "visible": false },
                { "data": "where_in_ms_to", "title": "Where in MS (to)", "visible": false },
                {
                    "data": "where",
                    "title": "Where in MS",
                    "render": function (data, type, row, meta) {
                        //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
                        //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);

                        let fromText = row.where_in_ms_from;
                        let toText = row.where_in_ms_to;

                        //if(fromIndex)
                        fromText = '<b><a  onclick="goToCanvasByLabel(\'' + row.where_in_ms_from + '\')">' + row.where_in_ms_from + '</a></b>';

                        //if(toIndex)
                        toText = '<b><a  onclick="goToCanvasByLabel(\'' + row.where_in_ms_to + '\')">' + row.where_in_ms_to + '</a></b>';

                        if (row.where_in_ms_from == row.where_in_ms_to || row.where_in_ms_to == '-')
                            return fromText;
                        return fromText + ' - ' + toText;
                    },
                    "width": "10%" 
                },
                { "data": "rite_name_from_ms", "title": "Rite name from MS", "width": "20%" },
                { "data": "subsection", "title": "Subsection", "width": "20%"  },
                { "data": "function", "title": "Function / Genre", "width": "10%"  },
                { "data": "subfunction", "title": "Subgenre", "width": "10%"  },
                { "data": "biblical_reference", "title": "Biblical reference", "width": "10%"  },
                { "data": "traditions", "title": "Traditions", "name": "traditions", "visible": false },
                { 
                    "data": "formula_standarized", 
                    "name": "formula_standarized", 
                    "title": "Formula (standarized)", 
                    render: function(data, type, row, meta) {

                        var rendered_html =  (row.formula_standarized || data);

                        if (row.traditions && IDENTIFY_TRADITIONS) {
                            let traditions = Array.isArray(row.traditions) 
                                ? row.traditions 
                                : row.traditions.split(',').map(t => t.trim()).filter(t => t);
    
                            let dots = '';
                            if (traditions.length === 0) {
                                dots = `<span class="dot" style="background-color: ${traditionColors['Unattributed']};" title="Unattributed"></span>`;
                            } else {
                                traditions.forEach(trad => {
                                    if (!traditionColors[trad]) {
                                        traditionColors[trad] = colorPalette[colorIndex % colorPalette.length];
                                        traditionMap[trad] = trad;
                                        colorIndex++;
                                    }
                                    dots += `<span class="dot" style="background-color: ${traditionColors[trad]};" title="${trad}"></span> `;
                                });
                            }
                            rendered_html = dots + rendered_html;
                        }
                        if (row.translation && row.translation.length>1)
                        {
                            let translation = ` <span 
                                title="${row.translation}" 
                                style="
                                    height: 12px;
                                    width: 12px;
                                    border-radius: 50%;
                                    display: inline-block;
                                    margin-right: 2px;
                                    background-image: url('/static/img/eng_flag.png');
                                    background-size: cover;
                                    background-position: center;
                                ">
                            </span>`;

                            rendered_html = rendered_html+ translation;
                        }

                        return rendered_html;
                    },
                    "width": "40%"  
                },
                {
                    "data": "formula_text",
                    "title": "Formula (text from MS)",
                    "render": function (data, type, row, meta) {
                        if (row.music_notation != "-")
                            return row.formula_text + ' (♪)';
                        return row.formula_text;
                    }, 
                    "width": "40%"
                },
                {
                    "data": "similarity_levenshtein_percent",
                    "title": "Similarity (levenshtein)",
                    "render": function (data, type, row, meta) {
                        return row.similarity_levenshtein_percent + "%";
                    },
                    "createdCell": function (td, cellData, rowData, row, col) {
                        if (cellData == '-' || !cellData || cellData < 50)
                            $(td).css("color", "red");
                        else if (cellData > 99.9)
                            $(td).css("color", "green");
                        else
                            $(td).css("color", "#a66b00");
                    },
                    "width": '60px'
                },
                { "data": "similarity_by_user", "title": "Similarity (by user)", "width": "5%"  },
                { "data": "original_or_added", "title": "Original or Added", "visible": false },
                { "data": "quire", "title": "Quire", "width": "5%"  },

                { "data": "music_notation", "title": "Music Notation", "visible": false },
                { "data": "sequence_in_ms", "title": "Sequence in MS", "visible": false },
                { "data": "original_or_added", "title": "Original or Added", "visible": false },
                { "data": "proper_texts", "title": "Proper texts", "width": "5%"  },

                { "data": "translation", "title": "Translation", "visible": false },

                { "data": "authors", "title": "Authors", "visible": false },
                { "data": "data_contributor", "title": "Data contributor", "visible": false },
                // Add more columns as needed
            ],
            "searchCols":[
                {search:ms_id},
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
            ],
            "order": [
                [1, "asc"]  // kolumna 1 to sequence_in_ms, rosnąco

                //{ "data": "sequence_in_ms", "order": "asc" },  // Sort by the "manuscript_name" column in ascending order
                //{ "data": "where_in_ms_from", "order": "asc" }      // Then sort by the "manuscript" column in descending order
            ],
            "createdRow": function (row, data, dataIndex) {
                if (data.original_or_added == "ORIGINAL") {
                    $(row).addClass('medieval-row');
                } else if (data.original_or_added == "ADDED") {
                    $(row).addClass('non-medieval-row');
                }
            },
            "drawCallback": function (settings) {
                var columns = settings.aoColumns;
                var json = settings.json;

                if (!json || !json.data) return;

                var columnsToCheck = ["function", "subfunction", "biblical_reference", "subsection", "quire", "similarity_by_user", "proper_texts", "formula_text", "rite_name_from_ms", "formula_standarized"];

                var table = this;

                columns.forEach(function (column, columnIndex) {
                    if (columnsToCheck.includes(column.data)) {
                        var isVisible = json.data.some(function (row) {
                            return !(row[column.data] == 'None' || row[column.data] == null || row[column.data] == '');
                        });

                        settings.oInstance.api().column(columnIndex).visible(isVisible);
                    } else if (column.data == "similarity_levenshtein_percent") {
                        var isVisible = json.data.some(function (row) {
                            return !(row[column.data] == 0 || row[column.data] == null);
                        });

                        settings.oInstance.api().column(columnIndex).visible(isVisible);
                    }
                });
            },
            "initComplete": function (settings, json) {
                displayUniqueAuthorsAndContributors(content_table, table_selector);
                displaOriginalAddedLegend(content_table, table_selector);

                if(IDENTIFY_TRADITIONS)
                    displayTraditionLegend(content_table, table_selector);
            }
        });
    }

    content_table_init(false,'.manuscript_filter_left','#content_left');


    $('.manuscript_filter_left').select2({
        ajax: {
            url: pageRoot+'/manuscripts-autocomplete-main/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          }
    });

    $('.manuscript_filter_left').on('select2:select', function (e) {
        var data = e.params.data;
        var id = data.id;
        console.log(id);

        //content_table_left.columns(0).search(id).draw();
        IDENTIFY_TRADITIONS = false; // Reset flag on manuscript change

        content_table_init(true,'.manuscript_filter_left','#content_left');

    });

    content_table_init(false,'.manuscript_filter_right','#content_right');


    $('.manuscript_filter_right').select2({
        ajax: {
            url: pageRoot+'/manuscripts-autocomplete-main/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          }
    });

    $('.manuscript_filter_right').on('select2:select', function (e) {
        var data = e.params.data;
        var id = data.id;
        console.log(id);

        //content_table_right.columns(0).search(id).draw();
        IDENTIFY_TRADITIONS = false; // Reset flag on manuscript change

        content_table_init(true,'.manuscript_filter_right','#content_right');

    });


    $('#genreSelect').select2();

    $('#identifyTraditionsBtn').on('click', function (e) {
        e.preventDefault();
        IDENTIFY_TRADITIONS = true;
        content_table_init(true,'.manuscript_filter_left','#content_left');
        content_table_init(true,'.manuscript_filter_right','#content_right');
    });
    

    $('#compareButton').click(function() {
        var leftId = $('.manuscript_filter_left').val();
        var rightId = $('.manuscript_filter_right').val();
        var url = pageRoot+"/compare_graph/?left=" + leftId + "&right=" + rightId;
        window.open(url, '_blank');
    });


    $('#compareEditionButton').click(function() {
        var leftId = $('.manuscript_filter_left').val();
        var rightId = $('.manuscript_filter_right').val();
        var url = pageRoot+"/compare_edition_graph/?left=" + leftId + "&right=" + rightId;
        window.open(url, '_blank');
    });





    //////////////////////////


    //RESIZER:
    const leftColumn = document.getElementById("leftColumn");
    const rightColumn = document.getElementById("rightColumn");

    // leftColumn.style.width = `100%`;
    // rightColumn.style.width = `100%`;


    const resizer = document.getElementById("resizer");
    let isResizing = false;

    // Event listener for mouse down on the resizer
    resizer.addEventListener("mousedown", function (e) {
        isResizing = true;
        res_mouse_x = e.clientX;
        leftWidth = leftColumn.getBoundingClientRect().width;

        document.addEventListener("mousemove", handleMouseMove);
        document.addEventListener("mouseup", function () {
            isResizing = false;
            document.removeEventListener("mousemove", handleMouseMove);
        });
    });

    function handleMouseMove(e) {
        if (isResizing) {
            const leftColumn = document.getElementById("leftColumn");
            const rightColumn = document.getElementById("rightColumn");
            const resizer = document.getElementById("resizer");

            // How far the mouse has been moved
            const dx = e.clientX - res_mouse_x;

            const newLeftWidth = ((leftWidth + dx) * 100) / resizer.parentNode.getBoundingClientRect().width;
            if(newLeftWidth<1)
                newLeftWidth=1;
            
            const containerWidth = leftColumn.offsetWidth + rightColumn.offsetWidth;

            leftColumn.style.width = `${newLeftWidth-1}%`;
            rightColumn.style.width = `${100 - newLeftWidth-1}%`;

            console.log(newLeftWidth);

            // Adjust the position of the resizer
            const resizerPosition = (newLeftWidth / 100) * containerWidth;
            //resizer.style.left = `${resizerPosition}px`;
            resizer.style.left =`${newLeftWidth}%`;
        }
    }

}

