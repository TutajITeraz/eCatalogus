
formulas_init = function() {
    
    var table;

    $(document).ready(function(){
        // Adjust layout on resize if needed (copied from content.js pattern)
        function adjustLayout() {
             $("#formulasTable_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "0px",
                "background": "#fff7f1",
                "z-index": "20",
            });
            $("#formulasTable_wrapper .dt-layout-row").eq(2).css({
                "position": "sticky",
                "bottom": "0px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        }
        
        $(window).resize(adjustLayout);
        // Initial adjust will be done after table draw
    });


    function formulas_table_init(reinit=false) {
        
        // Get filter values
        var traditionId = $('#traditionSelect').val();
        var usedInMs = $('#usedInMsCheckbox').is(':checked');

        table = $('#formulasTable').DataTable({
            "destroy": reinit,
            "ajax": {
                "url": pageRoot + "/api/formulas_index/?format=datatables", 
                "data": function(d) {
                    d.tradition = traditionId;
                    d.used_in_ms = usedInMs;
                },
                "dataSrc": function (data) {
                    return data.data; 
                }
            },
            "processing": true,
            "serverSide": true,
            "lengthMenu": [[10, 25, 50, 100], [10, 25, 50, 100]],
            "pagingType": "full_numbers",
            "pageLength": 25,
            "bAutoWidth": false, 
            "columns": [
                { "data": "id", "title": "ID", "width": "5%", "defaultContent": "" },
                { "data": "co_no", "title": "CO No.", "width": "10%", "defaultContent": "" },
                { 
                    "data": "text", 
                    "title": "Text", 
                    "width": "35%",
                    "defaultContent": "",
                    "render": function(data, type) {
                        if (type !== 'display') return data;
                        if (!data) return "";
                        const escaped = $('<div>').text(data).html();
                        return '<div class="whitespace-pre-wrap break-words">' + escaped + '</div>';
                    }
                },
                /*{ 
                    "data": "traditions", 
                    "title": "Traditions", 
                    "width": "10%",
                    "defaultContent": "",
                    "render": function(data) {
                        if (Array.isArray(data)) {
                            return data.join(", ");
                        }
                        return data || "";
                    }
                },*/
                { 
                    "data": "translation_en", 
                    "title": "English Translation", 
                    "width": "20%",
                    "defaultContent": "",
                    "render": function(data, type) {
                        if (type !== 'display') return data;
                        if (!data) return "";
                        const escaped = $('<div>').text(data).html();
                        return '<div class="whitespace-pre-wrap break-words">' + escaped + '</div>';
                    }
                },
                {
                    "data": "used_in",
                    "title": "Used in Manuscripts",
                    "width": "15%",
                    "defaultContent": "",
                    "orderable": false, // Sorting by this column content is complex, we use the numeric count column instead
                    "render": function(data) {
                        if (!data || data.length === 0) return "-";
                        
                        var html = '<div style="max-height: 120px; overflow-y: auto;" class="whitespace-pre-wrap break-words">';
                        data.forEach(function(ms) {
                            html += '<div><a href="' + window.getManuscriptPageUrl(ms) + '" target="_blank" class="text-blue-600 hover:underline">' + ms.name + '</a></div>';
                        });
                        html += '</div>';
                        return html;
                    }
                },
                { 
                    "data": "used_in_count", 
                    "title": "Uses", 
                    "width": "5%",
                    "searchable": false,
                    "defaultContent": "0"
                }
            ],
            "order": [[ 0, "asc" ]], // Default sort by ID
            "drawCallback": function (settings) {
                 // Adjust layout after draw
                 $("#formulasTable_wrapper .dt-layout-row").eq(0).css({
                    "position": "sticky",
                    "top": "0px",
                    "background": "#fff7f1",
                    "z-index": "20",
                });
            }
        });
    }

    // Initialize Select2 for Tradition
    $('#traditionSelect').select2({
        ajax: {
            url: pageRoot + '/traditions-autocomplete/', // Ensure this URL exists or use correct one
            dataType: 'json',
            delay: 250,
            data: function (params) {
                return {
                    q: params.term, // search term
                };
            },
            processResults: function (data) {
                return {
                    results: data.results
                };
            },
            cache: true,
             xhrFields: {
                withCredentials: true
           }
        },
        placeholder: 'Select a tradition',
        allowClear: true,
        width: 'resolve'
    });

    // Event listeners
    $('#traditionSelect').on('select2:select select2:unselect', function (e) {
        formulas_table_init(true);
    });

    $('#usedInMsCheckbox').on('change', function() {
        formulas_table_init(true);
    });

    // Initial load
    formulas_table_init();

}
