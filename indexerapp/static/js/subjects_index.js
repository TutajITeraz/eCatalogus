subjects_init = function() {
    var table;

    $(document).ready(function(){
        function adjustLayout() {
            $("#subjectsTable_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "0px",
                "background": "#fff7f1",
                "z-index": "20",
            });
            $("#subjectsTable_wrapper .dt-layout-row").eq(2).css({
                "position": "sticky",
                "bottom": "0px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        }
        $(window).resize(adjustLayout);
    });

    function table_init(reinit=false) {
        table = $('#subjectsTable').DataTable({
            destroy: reinit,
            ajax: {
                url: pageRoot + "/api/subjects_index/?format=datatables",
                dataSrc: function (data) { return data.data; }
            },
            processing: true,
            serverSide: true,
            lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
            pagingType: "full_numbers",
            pageLength: 25,
            bAutoWidth: false,
            columns: [
                { data: "id", title: "ID", width: "8%", defaultContent: "" },
                { data: "name", title: "Subject", width: "42%", defaultContent: "" },
                {
                    data: "used_in",
                    title: "Used in Manuscripts",
                    width: "40%",
                    defaultContent: "",
                    orderable: false,
                    render: function(data) {
                        if (!data || data.length === 0) return "-";
                        var html = '<div style="max-height: 140px; overflow-y: auto;" class="whitespace-pre-wrap break-words">';
                        data.forEach(function(ms) {
                            html += '<div><a href="' + window.getManuscriptPageUrl(ms) + '" target="_blank" class="text-blue-600 hover:underline">' + ms.name + '</a></div>';
                        });
                        html += '</div>';
                        return html;
                    }
                },
                { data: "used_in_count", title: "Uses", width: "10%", searchable: false, defaultContent: "0" }
            ],
            order: [[1, "asc"]],
            drawCallback: function (settings) {
                $("#subjectsTable_wrapper .dt-layout-row").eq(0).css({
                    "position": "sticky",
                    "top": "0px",
                    "background": "#fff7f1",
                    "z-index": "20",
                });
            }
        });
    }

    table_init();
}
