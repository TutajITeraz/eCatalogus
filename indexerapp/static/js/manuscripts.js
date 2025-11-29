const DATING_YEAR_MIN = 1000;
const DATING_YEAR_MAX = 1400;

manuscripts_init = function()
{

    //Slider:
    // Initialize noUiSlider
    const slider = document.getElementById('year-range-slider');
    const minInput = document.getElementById('ms_dating_years_min');
    const maxInput = document.getElementById('ms_dating_years_max');

    noUiSlider.create(slider, {
        start: [DATING_YEAR_MIN, DATING_YEAR_MAX], // Default to full range
        connect: true,
        range: {
            'min': DATING_YEAR_MIN,
            'max': DATING_YEAR_MAX
        },
        step: 1,
        margin: 1, // Ensure min and max are not the same
        behaviour: 'drag',
        tooltips: [true, true], // Show tooltips for both handles
        format: {
            to: value => Math.round(value), // Round to integers
            from: value => Number(value)
        }
    });

    // Sync slider with number inputs
    slider.noUiSlider.on('update', function(values, handle) {
        const [min, max] = values;
        // Clear inputs if slider is at full range (1000–1400)
        if (min === DATING_YEAR_MIN && max === DATING_YEAR_MAX) {
            minInput.value = '';
            maxInput.value = '';
        } else {
            minInput.value = min;
            maxInput.value = max;
        }
    });

    // Trigger processFilters on slider change
    slider.noUiSlider.on('change', function() {
        processFilters();
    });


    // Mapping of quick filter checkboxes to menu checkboxes
    const checkboxPairs = [
        { quick: '#decoration_yes', menu: '#decoration_true' },
        { quick: '#decoration_no', menu: '#decoration_false' },
        { quick: '#music_yes', menu: '#music_notation_true' },
        { quick: '#music_no', menu: '#music_notation_false' },
        { quick: '#digitized_yes', menu: '#digitized_true' },
        { quick: '#digitized_no', menu: '#digitized_false' }
    ];

    // Function to synchronize checkboxes
    function syncCheckboxes(sourceId, targetId) {
        $(targetId).prop('checked', $(sourceId).prop('checked'));
        processFilters(); // Call existing processFilters function
    }

    // Add change event listeners for all checkboxes
    checkboxPairs.forEach(pair => {
        // Quick filter to menu sync
        $(pair.quick).on('change', function() {
            syncCheckboxes(pair.quick, pair.menu);
        });
        // Menu to quick filter sync
        $(pair.menu).on('change', function() {
            syncCheckboxes(pair.menu, pair.quick);
        });
    });



    //static resizer width:
    const leftColumn = document.getElementById("leftColumn");
    const rightColumn = document.getElementById("rightColumn");
    const resizer = document.getElementById("resizer");

    const newLeftWidth = 300;

    // leftColumn.style.width = `${newLeftWidth}px`;
    // rightColumn.style.width = `calc(100% - 305px)`;
    // resizer.style.left =`${newLeftWidth}px`;

    let clearingAllFieldsInProgress = false;

    function processFilters(e)
    {
        updateTags();
        
        if(!clearingAllFieldsInProgress)
            manuscripts_table.ajax.reload();
    }


    $('#ms_name_select').select2({
        ajax: {
            url: pageRoot+'/manuscripts-autocomplete-main/?project_id='+projectId,
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_name_select').on('select2:select', processFilters);


    $('#ms_foreign_id_select').select2({
        ajax: {
            url: pageRoot+'/ms-foreign-id-autocomplete/?project_id='+projectId,
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_foreign_id_select').on('select2:select', processFilters);


    $('#ms_liturgical_genre_select').select2({
        ajax: {
            url: pageRoot+'/liturgical-genres-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_liturgical_genre_select').on('select2:select', processFilters);


    $('#ms_contemporary_repository_place_select').select2({
        ajax: {
            url: pageRoot+'/ms-contemporary-repository-place-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
        },
    	formatSelection: function(selected, total) {
      	    return "Selected " + selected.length + " of " + total;
        },
        allowClear: true,
        placeholder: '',
    });
    $('#ms_contemporary_repository_place_select').on('select2:select', processFilters);

    // ms_shelfmark_select 'ms-shelf-mark-autocomplete/
    $('#ms_shelfmark_select').select2({
        ajax: {
            url: pageRoot+'/ms-shelf-mark-autocomplete/?project_id='+projectId,
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_shelfmark_select').on('select2:select', processFilters);
    /*
    // ms_dating_select ms-dating-autocomplete/
    $('#ms_dating_select').select2({
        ajax: {
            url: '/ms-dating-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_dating_select').on('select2:select', processFilters);
    */
    // ms_place_of_origin_select ms-place-of-origins-autocomplete/
    $('#ms_place_of_origin_select').select2({
        ajax: {
            url: pageRoot+'/ms-place-of-origins-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_place_of_origin_select').on('select2:select', processFilters);

    // ms_main_script_select ms-main-script-autocomplete/
    /*
    $('#ms_main_script_select').select2({
        ajax: {
            url: '/ms-main-script-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    
    $('#ms_main_script_select').on('select2:select', processFilters);
    */

    /*
    // ms_binding_date_select ms-binding-date-autocomplete/
    $('#ms_binding_date_select').select2({
        ajax: {
            url: '/ms-binding-date-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ms_binding_date_select').on('select2:select', processFilters);
    */

    //New select2 with explicite options (no json):
    $('#type_of_the_quire_select').select2({
        allowClear: true,
        placeholder: '',
    });
    //$('#type_of_the_quire_select').on('select2:select', processFilters);

    $('#ruling_method_select').select2({
        allowClear: true,
        placeholder: '',
    });
    //$('#ruling_method_select').on('select2:select', processFilters);

    $('#pricking_select').select2({
        allowClear: true,
        placeholder: '',
    });
    //$('#pricking_select').on('select2:select', processFilters);

    $('#damage_select').select2({
        allowClear: true,
        placeholder: '',
    });
    //$('#damage_select').on('select2:select', processFilters);

    //New select2 with remote options (json):
    $('#parchment_colour_select').select2({
        ajax: {
            url: pageRoot+'/colours-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#parchment_colour_select').on('select2:select', processFilters);

    $('#main_script_select').select2({
        ajax: {
            url: pageRoot+'/script-names-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#main_script_select').on('select2:select', processFilters);

    $('#script_name_select').select2({
        ajax: {
            url: pageRoot+'/script-names-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#script_name_select').on('select2:select', processFilters);


    $('#binding_place_of_origin_select').select2({
        ajax: {
            url: pageRoot+'/places-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_place_of_origin_select').on('select2:select', processFilters);

    $('#binding_type_select').select2({
        ajax: {
            url: pageRoot+'/binding-types-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_type_select').on('select2:select', processFilters);


    $('#binding_style_select').select2({
        ajax: {
            url: pageRoot+'/binding-styles-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_style_select').on('select2:select', processFilters);

    $('#binding_material_select').select2({
        ajax: {
            url: pageRoot+'/binding-materials-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_material_select').on('select2:select', processFilters);

    $('#binding_decoration_select').select2({
        ajax: {
            url: pageRoot+'/binding-decoration-type-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_decoration_select').on('select2:select', processFilters);

    $('#binding_components_select').select2({
        ajax: {
            url: pageRoot+'/binding-components-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_components_select').on('select2:select', processFilters);

    $('#binding_category_select').select2({
        ajax: {
            url: pageRoot+'/binding-category-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#binding_category_select').on('select2:select', processFilters);


    $('#formula_select').select2({
        ajax: {
            url: pageRoot+'/formulas-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#provenance_place_select').on('select2:select', processFilters);


    $('#rite_select').select2({
        ajax: {
            url: pageRoot+'/ritenames-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#provenance_place_select').on('select2:select', processFilters);


    $('#provenance_place_select').select2({
        ajax: {
            url: pageRoot+'/ms-provenance-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });

    $('#provenance_place_countries_select').select2({
        ajax: {
            url: pageRoot+'/places-countries-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#provenance_place_select').on('select2:select', processFilters);

    $('#form_of_an_item_select').select2({
          allowClear: true,
          placeholder: '',
    });


    $('#title_select').select2({
        ajax: {
            url: pageRoot+'/bibliography-title-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#title_select').on('select2:select', processFilters);


    $('#author_select').select2({
        ajax: {
            url: pageRoot+'/bibliography-author-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });
    //$('#author_select').on('select2:select', processFilters);


    $('#clla_liturgical_genre_select').select2({
        ajax: {
            url: pageRoot+'/clla-liturgical-genre-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });


    $('#clla_provenance_place_select').select2({
        ajax: {
            url: pageRoot+'/clla-provenance-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
            // Additional AJAX parameters go here; see the end of this chapter for the full code of this example
          },
          allowClear: true,
          placeholder: '',
    });


    /////////////////////////// DECORATION SELECT //////////////////////////////
    $('#decoration_type_select').select2({
        ajax: {
            url: pageRoot+'/decoration-type-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#decoration_subtype_select').select2({
        ajax: {
            url: pageRoot+'/decoration-subtype-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#technique_select').select2({
        ajax: {
            url: pageRoot+'/decoration-techniques-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#ornamented_text_select').select2({
        ajax: {
            url: pageRoot+'/decoration-ornamented_text-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#decoration_subject_select').select2({
        ajax: {
            url: pageRoot+'/subject-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#decoration_colours_select').select2({
        ajax: {
            url: pageRoot+'/colours-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#decoration_characteristics_select').select2({
        ajax: {
            url: pageRoot+'/characteristics-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
           }
          },
          allowClear: true,
          placeholder: '',
    });
    $('#musicology_type_select').select2({
        ajax: {
            url: pageRoot+'/music-notation-names-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
              }
            },
            allowClear: true,
            placeholder: '',
    });


    
    //explicitly added options:
    $('#location_on_the_page_select').select2({
          allowClear: true,
          placeholder: '',
    });
    $('#monochrome_or_colour_select').select2({
        allowClear: true,
        placeholder: '',
    });
    $('#size_characteristic_select').select2({
        allowClear: true,
        placeholder: '',
    });
    $('#original_or_added_select').select2({
        allowClear: true,
        placeholder: '',
    });


    //Unselecting:

    $('select').on('select2:unselecting', function() {
        $(this).data('unselecting', true);
    }).on('select2:opening', function(e) {
        if ($(this).data('unselecting')) {
            $(this).removeData('unselecting');
            e.preventDefault();

            processFilters();
        }
    });

    // Function to clear form fields
    function clearFields() {

        clearingAllFieldsInProgress = true;
        // Clear all input fields
        $('input').each(function() {
            if ($(this).attr('type') !== 'checkbox' && $(this).attr('type') !== 'radio') {
                $(this).val('');
            } else {
                $(this).prop('checked', false);
            }
        });
    
        // Clear all select fields (including Select2)
        $('.manuscript_filter').each(function() {
            $(this).val("").change(); // Clear Select2 value and trigger change event
        });

        clearingAllFieldsInProgress = false;

        processFilters(); 
    }
    

    // Add click event to the button
    $('#clearFieldsButton').click(function() {
        clearFields();
    });

    // function setTableHeight() {
    //     var windowHeight = $(window).height();
    //     var windowWidth = $(window).width();
    //     if(windowWidth > 768){
    //         var tableHeight = windowHeight - 510;
    //     } else {
    //         var tableHeight = windowHeight - 650;
    //     }
        
    //     // $('#manuscripts').css('height', tableHeight + 'px');
    //     // console.log('table height : ', tableHeight);
    // }

    // // Set initial height
    // setTableHeight();

    // Adjust height on window resize
    $(window).resize(function() {
        // setTableHeight();

        var windowWidth = $(window).width();

        if(windowWidth < 768){
            $("#manuscripts_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "88px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        } else if (windowWidth < 1280){
            $("#manuscripts_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "68px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        } else {
            $("#manuscripts_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "48px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        }
        // Apply CSS to the first dt-layout-row
    
        // Apply CSS to the second dt-layout-row
        // $("#manuscripts_wrapper .dt-layout-row").eq(1).css({
        //     "background-color": "lightgreen",
        //     "margin-top": "20px",
        //     "border": "2px solid green"
        // });
    
        // Apply CSS to the third dt-layout-row
        $("#manuscripts_wrapper .dt-layout-row").eq(2).css({
            "position": "sticky",
            "bottom": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
    });


    $(document).ready(function() {
        clearFields();
        
        // setTableHeight();

        var windowWidth = $(window).width();

        if(windowWidth < 768){
            $("#manuscripts_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "88px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        } else if (windowWidth < 1280){
            $("#manuscripts_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "68px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        } else {
            $("#manuscripts_wrapper .dt-layout-row").eq(0).css({
                "position": "sticky",
                "top": "48px",
                "background": "#fff7f1",
                "z-index": "20",
            });
        }
        // Apply CSS to the first dt-layout-row
    
        // Apply CSS to the second dt-layout-row
        // $("#manuscripts_wrapper .dt-layout-row").eq(1).css({
        //     "background-color": "lightgreen",
        //     "margin-top": "20px",
        //     "border": "2px solid green"
        // });
    
        // Apply CSS to the third dt-layout-row
        $("#manuscripts_wrapper .dt-layout-row").eq(2).css({
            "position": "sticky",
            "bottom": "0px",
            "background": "#fff7f1",
            "z-index": "20",
        });
    });

    $('#ms_dating_years_min, #ms_dating_years_max').on('change', function() {
        const minVal = parseInt(minInput.value) || DATING_YEAR_MIN;
        const maxVal = parseInt(maxInput.value) || DATING_YEAR_MAX;
        // Update slider only if values are valid
        if (minVal <= maxVal && minVal >= DATING_YEAR_MIN && maxVal <= DATING_YEAR_MAX) {
            slider.noUiSlider.set([minVal, maxVal]);
        } else if (!minInput.value && !maxInput.value) {
            slider.noUiSlider.set([DATING_YEAR_MIN, DATING_YEAR_MAX]); // Reset to full range
        }
        processFilters();
    });

    //$('#ms_how_many_columns_min').on( "change", processFilters );
    //$('#ms_how_many_columns_max').on( "change", processFilters );
    $('#ms_how_many_columns1').on( "change", processFilters );
    $('#ms_how_many_columns2').on( "change", processFilters );
    $('#ms_how_many_columns3').on( "change", processFilters );
    $('#ms_lines_per_page_min').on( "change", processFilters );
    $('#ms_lines_per_page_max').on( "change", processFilters );
    $('#ms_how_many_quires_min').on( "change", processFilters );
    $('#ms_how_many_quires_max').on( "change", processFilters );
    $('#decoration_true').on( "change", processFilters );
    $('#decoration_false').on( "change", processFilters );
    $('#music_notation_true').on( "change", processFilters );
    $('#music_notation_false').on( "change", processFilters );
    $('#digitized_true').on( "change", processFilters );
    $('#digitized_false').on( "change", processFilters );
    $('#ms_dating_min').on("change", processFilters);
    $('#ms_dating_max').on("change", processFilters);
    $('#clla_dating_min').on("change", processFilters);
    $('#clla_dating_max').on("change", processFilters);
    $('#clla_dating_years_min').on("change", processFilters);
    $('#clla_dating_years_max').on("change", processFilters);
    $('#number_of_parchment_folios_min').on("change", processFilters);
    $('#number_of_parchment_folios_max').on("change", processFilters);
    $('#ms_binding_date_min').on("change", processFilters);
    $('#ms_binding_date_max').on("change", processFilters);
    $('#ms_binding_date_years_min').on("change", processFilters);
    $('#ms_binding_date_years_max').on("change", processFilters);
    $('#foliation').on( "change", processFilters );
    $('#pagination').on( "change", processFilters );

    //$('#display_as_main_true').on( "change", processFilters );
    //$('#display_as_main_false').on( "change", processFilters );

    $('#paper_leafs_true').on("change", processFilters);
    $('#parchment_thickness_min').on("change", processFilters);
    $('#parchment_colour_select').on("change", processFilters);
    $('#page_size_w_min').on("change", processFilters);
    $('#page_size_h_min').on("change", processFilters);
    $('#main_script_select').on("change", processFilters);
    $('#watermarks_true').on("change", processFilters);
    $('#type_of_the_quire_select').on("change", processFilters);
    $('#script_name_select').on("change", processFilters);
    $('#is_main_text_true').on("change", processFilters);
    $('#is_hand_identified_true').on("change", processFilters);
    $('#ms_how_many_hands_min').on("change", processFilters);
    $('#distance_between_horizontal_ruling_min').on("change", processFilters);
    $('#distance_between_vertical_ruling_min').on("change", processFilters);
    $('#written_space_height_min').on("change", processFilters);
    $('#written_space_width_min').on("change", processFilters);
    $('#ruling_method_select').on("change", processFilters);
    $('#written_above_the_top_line_true').on("change", processFilters);
    $('#pricking_select').on("change", processFilters);
    $('#binding_height_min').on("change", processFilters);
    $('#binding_width_min').on("change", processFilters);
    $('#block_size_min').on("change", processFilters);
    $('#block_size_max').on("change", processFilters);
    $('#binding_place_of_origin_select').on("change", processFilters);
    $('#binding_type_select').on("change", processFilters);
    $('#binding_style_select').on("change", processFilters);
    $('#binding_material_select').on("change", processFilters);
    $('#binding_decoration_select').on("change", processFilters);
    $('#binding_components_select').on("change", processFilters);
    $('#binding_category_select').on("change", processFilters);
    $('#formula_select').on("change", processFilters);
    $('#rite_select').on("change", processFilters);
    $('#binding_decoration_true').on("change", processFilters);
    $('#damage_select').on("change", processFilters);
    $('#parchment_shrinkage_true').on("change", processFilters);
    $('#illegible_text_true').on("change", processFilters);
    $('#ink_corrosion_true').on("change", processFilters);
    $('#copper_corrosion_true').on("change", processFilters);
    $('#powdering_or_cracking_paint_layer_true').on("change", processFilters);
    $('#conservation_true').on("change", processFilters);
    $('#provenance_place_select').on("change", processFilters);
    $('#provenance_place_countries_select').on("change", processFilters);
    $('#form_of_an_item_select').on("change", processFilters);
    $('#title_select').on("change", processFilters);
    $('#author_select').on("change", processFilters);
    $('#clla_liturgical_genre_select').on("change", processFilters);
    $('#clla_provenance_place_select').on("change", processFilters);

    $('#original_or_added_select').on("change", processFilters);
    $('#location_on_the_page_select').on("change", processFilters);
    $('#decoration_type_select').on("change", processFilters);
    $('#decoration_subtype_select').on("change", processFilters);
    $('#size_characteristic_select').on("change", processFilters);
    $('#monochrome_or_colour_select').on("change", processFilters);
    $('#technique_select').on("change", processFilters);
    $('#ornamented_text_select').on("change", processFilters);
    $('#decoration_subject_select').on("change", processFilters);
    $('#decoration_colours_select').on("change", processFilters);
    $('#decoration_characteristics_select').on("change", processFilters);
    $('#musicology_type_select').on("change", processFilters);

    $('#decoration_size_height_min').on("change", processFilters);
    $('#decoration_size_height_max').on("change", processFilters);
    $('#decoration_size_width_min').on("change", processFilters);
    $('#decoration_size_width_max').on("change", processFilters);
    $('#decoration_addition_date_min').on("change", processFilters);
    $('#decoration_addition_date_max').on("change", processFilters);
    $('#decoration_addition_date_years_min').on("change", processFilters);
    $('#decoration_addition_date_years_max').on("change", processFilters);

    $('#musicology_how_many_lines_min').on("change", processFilters);
    $('#musicology_how_many_lines_max').on("change", processFilters);


    $('#paper_leafs_false').on("change", processFilters);
    $('#parchment_thickness_max').on("change", processFilters);
    $('#page_size_w_max').on("change", processFilters);
    $('#page_size_h_max').on("change", processFilters);
    $('#watermarks_false').on("change", processFilters);
    $('#is_main_text_false').on("change", processFilters);
    $('#is_hand_identified_false').on("change", processFilters);
    $('#ms_how_many_hands_max').on("change", processFilters);
    $('#distance_between_horizontal_ruling_max').on("change", processFilters);
    $('#distance_between_vertical_ruling_max').on("change", processFilters);
    $('#written_space_height_max').on("change", processFilters);
    $('#written_space_width_max').on("change", processFilters);
    $('#written_above_the_top_line_false').on("change", processFilters);
    $('#binding_height_max').on("change", processFilters);
    $('#binding_width_max').on("change", processFilters);
    $('#binding_decoration_false').on("change", processFilters);
    $('#parchment_shrinkage_false').on("change", processFilters);
    $('#illegible_text_false').on("change", processFilters);
    $('#ink_corrosion_false').on("change", processFilters);
    $('#copper_corrosion_false').on("change", processFilters);
    $('#powdering_or_cracking_paint_layer_false').on("change", processFilters);
    $('#conservation_false').on("change", processFilters);
    $('#formula_text').on("change", processFilters);
    $('#clla_no').on("change", processFilters);

    $('#rite_name_from_ms').on("change", processFilters);

    $('#darkening_true').on("change", processFilters);
    $('#darkening_false').on("change", processFilters);
    $('#water_staining_true').on("change", processFilters);
    $('#water_staining_false').on("change", processFilters);
    $('#historic_repairs_true').on("change", processFilters);
    $('#historic_repairs_false').on("change", processFilters);

    $('#musicology_original_true').on("change", processFilters);
    $('#musicology_original_false').on("change", processFilters);
    $('#musicology_on_lines_true').on("change", processFilters);
    $('#musicology_on_lines_false').on("change", processFilters);


    var getFilterData = function(d)
    {    
        d.name = $('#ms_name_select').select2('data').map(item => item.id).join(';');
        d.foreign_id = $('#ms_foreign_id_select').select2('data').map(item => item.id).join(';');
        d.liturgical_genre = $('#ms_liturgical_genre_select').select2('data').map(item => item.id).join(';');
        d.contemporary_repository_place = $('#ms_contemporary_repository_place_select').select2('data').map(item => item.id).join(';');
        d.shelfmark = $('#ms_shelfmark_select').select2('data').map(item => item.id).join(';');
        //jd.dating = $('#ms_dating_select').select2('data').map(item => item.id).join(';');
        d.place_of_origin = $('#ms_place_of_origin_select').select2('data').map(item => item.id).join(';');
        //d.main_script = $('#ms_main_script_select').select2('data').map(item => item.id).join(';');
        //d.binding_date = $('#ms_binding_date_select').select2('data').map(item => item.id).join(';');
        //d.how_many_columns_min = $('#ms_how_many_columns_min').val();
        //d.how_many_columns_max = $('#ms_how_many_columns_max').val();
        d.how_many_columns = [$('#ms_how_many_columns1').is(":checked") ? '1' : '', $('#ms_how_many_columns2').is(":checked") ? '2' : '', $('#ms_how_many_columns3').is(":checked") ? '3' : ''].filter(Boolean).join(';');
        d.lines_per_page_min = $('#ms_lines_per_page_min').val();
        d.lines_per_page_max = $('#ms_lines_per_page_max').val();
        d.how_many_quires_min = $('#ms_how_many_quires_min').val();
        d.how_many_quires_max = $('#ms_how_many_quires_max').val();
        d.decoration_true = $('#decoration_true').is(":checked");
        d.decoration_false = $('#decoration_false').is(":checked")
        d.music_notation_true = $('#music_notation_true').is(":checked")
        d.music_notation_false = $('#music_notation_false').is(":checked")
        d.digitized_true = $('#digitized_true').is(":checked")
        d.digitized_false = $('#digitized_false').is(":checked")
        d.foliation = $('#foliation').is(":checked")
        d.pagination = $('#pagination').is(":checked")

        d.dating_min = $('#ms_dating_min').val();
        d.dating_max = $('#ms_dating_max').val();
        d.dating_years_min = $('#ms_dating_years_min').val();
        d.dating_years_max = $('#ms_dating_years_max').val();
        //d.clla_dating_max = $('#clla_dating_max').val();
        //d.clla_dating_years_min = $('#clla_dating_years_min').val();
        //d.clla_dating_min = $('#clla_dating_min').val();
        //d.clla_dating_years_max = $('#clla_dating_years_max').val();

        d.number_of_parchment_folios_min = $('#number_of_parchment_folios_min').val();
        d.number_of_parchment_folios_max = $('#number_of_parchment_folios_max').val();

        d.binding_date_min = $('#ms_binding_date_min').val();
        d.binding_date_max = $('#ms_binding_date_max').val();
        d.binding_date_years_min = $('#ms_binding_date_years_min').val();
        d.binding_date_years_max = $('#ms_binding_date_years_max').val();

        //New min/max:
        d.binding_height_min = $('#binding_height_min').val();
        d.binding_width_min = $('#binding_width_min').val();
        d.written_space_height_min = $('#written_space_height_min').val();
        d.written_space_width_min = $('#written_space_width_min').val();
        d.distance_between_horizontal_ruling_min = $('#distance_between_horizontal_ruling_min').val();
        d.distance_between_vertical_ruling_min = $('#distance_between_vertical_ruling_min').val();
        d.ms_how_many_hands_min = $('#ms_how_many_hands_min').val();
        d.page_size_w_min = $('#page_size_w_min').val();
        d.page_size_h_min = $('#page_size_h_min').val();
        d.parchment_thickness_min = $('#parchment_thickness_min').val();
        d.binding_height_max = $('#binding_height_max').val();
        d.binding_width_max = $('#binding_width_max').val();
        d.written_space_height_max = $('#written_space_height_max').val();
        d.written_space_width_max = $('#written_space_width_max').val();
        d.distance_between_horizontal_ruling_max = $('#distance_between_horizontal_ruling_max').val();
        d.distance_between_vertical_ruling_max = $('#distance_between_vertical_ruling_max').val();
        d.ms_how_many_hands_max = $('#ms_how_many_hands_max').val();
        d.page_size_w_max = $('#page_size_w_max').val();
        d.page_size_h_max = $('#page_size_h_max').val();
        d.parchment_thickness_max = $('#parchment_thickness_max').val();
        d.block_size_min = $('#block_size_min').val();
        d.block_size_max = $('#block_size_max').val();

        //New True/False:
        d.paper_leafs_true = $('#paper_leafs_true').is(':checked');
        d.watermarks_true = $('#watermarks_true').is(':checked');
        d.is_main_text_true = $('#is_main_text_true').is(':checked');
        d.is_hand_identified_true = $('#is_hand_identified_true').is(':checked');
        d.written_above_the_top_line_true = $('#written_above_the_top_line_true').is(':checked');
        d.binding_decoration_true = $('#binding_decoration_true').is(':checked');
        d.parchment_shrinkage_true = $('#parchment_shrinkage_true').is(':checked');
        d.illegible_text_true = $('#illegible_text_true').is(':checked');
        d.ink_corrosion_true = $('#ink_corrosion_true').is(':checked');
        d.copper_corrosion_true = $('#copper_corrosion_true').is(':checked');
        d.powdering_or_cracking_paint_layer_true = $('#powdering_or_cracking_paint_layer_true').is(':checked');
        d.conservation_true = $('#conservation_true').is(':checked');
        d.paper_leafs_false = $('#paper_leafs_false').is(':checked');
        d.watermarks_false = $('#watermarks_false').is(':checked');
        d.is_main_text_false = $('#is_main_text_false').is(':checked');
        d.is_hand_identified_false = $('#is_hand_identified_false').is(':checked');
        d.written_above_the_top_line_false = $('#written_above_the_top_line_false').is(':checked');
        d.binding_decoration_false = $('#binding_decoration_false').is(':checked');
        d.parchment_shrinkage_false = $('#parchment_shrinkage_false').is(':checked');
        d.illegible_text_false = $('#illegible_text_false').is(':checked');
        d.ink_corrosion_false = $('#ink_corrosion_false').is(':checked');
        d.copper_corrosion_false = $('#copper_corrosion_false').is(':checked');
        d.powdering_or_cracking_paint_layer_false = $('#powdering_or_cracking_paint_layer_false').is(':checked');
        d.conservation_false = $('#conservation_false').is(':checked');

        d.darkening_true = $('#darkening_true').is(':checked');
        d.darkening_false = $('#darkening_false').is(':checked');
        d.water_staining_true = $('#water_staining_true').is(':checked');
        d.water_staining_false = $('#water_staining_false').is(':checked');        
        d.historic_repairs_true = $('#historic_repairs_true').is(':checked');
        d.historic_repairs_false = $('#historic_repairs_false').is(':checked');

        d.musicology_original_true = $('#musicology_original_true').is(':checked');
        d.musicology_original_false = $('#musicology_original_false').is(':checked');
        d.musicology_on_lines_true = $('#musicology_on_lines_true').is(':checked');
        d.musicology_on_lines_false = $('#musicology_on_lines_false').is(':checked');

        //New Select:
        d.parchment_colour_select = $('#parchment_colour_select').select2('data').map(item => item.id).join(';');
        d.main_script_select = $('#main_script_select').select2('data').map(item => item.id).join(';');
        d.type_of_the_quire_select = $('#type_of_the_quire_select').select2('data').map(item => item.id).join(';');
        d.script_name_select = $('#script_name_select').select2('data').map(item => item.id).join(';');
        d.ruling_method_select = $('#ruling_method_select').select2('data').map(item => item.id).join(';');
        d.pricking_select = $('#pricking_select').select2('data').map(item => item.id).join(';');
        d.binding_place_of_origin_select = $('#binding_place_of_origin_select').select2('data').map(item => item.id).join(';');
        d.binding_type_select = $('#binding_type_select').select2('data').map(item => item.id).join(';');
        d.binding_style_select = $('#binding_style_select').select2('data').map(item => item.id).join(';');
        d.binding_material_select = $('#binding_material_select').select2('data').map(item => item.id).join(';');
        d.binding_decoration_select = $('#binding_decoration_select').select2('data').map(item => item.id).join(';');
        d.binding_components_select = $('#binding_components_select').select2('data').map(item => item.id).join(';');
        d.binding_category_select = $('#binding_category_select').select2('data').map(item => item.id).join(';');
        d.formula_select = $('#formula_select').select2('data').map(item => item.id).join(';');
        d.rite_select = $('#rite_select').select2('data').map(item => item.id).join(';');
        d.damage_select = $('#damage_select').select2('data').map(item => item.id).join(';');
        d.provenance_place_select = $('#provenance_place_select').select2('data').map(item => item.id).join(';');
        d.provenance_place_countries_select = $('#provenance_place_countries_select').select2('data').map(item => item.id).join(';');
        d.form_of_an_item_select = $('#form_of_an_item_select').select2('data').map(item => item.id).join(';');

        d.title_select = $('#title_select').select2('data').map(item => item.id).join(';');
        //Special case (authors does not have .id)
        d.author_select = $('#author_select').select2('data').map(item => item.text).join(';');

        //d.clla_liturgical_genre_select = $('#clla_liturgical_genre_select').select2('data').map(item => item.text).join(';');
        //d.clla_provenance_place_select = $('#clla_provenance_place_select').select2('data').map(item => item.text).join(';');



        d.original_or_added_select = $('#original_or_added_select').select2('data').map(item => item.id).join(';');
        d.location_on_the_page_select = $('#location_on_the_page_select').select2('data').map(item => item.id).join(';');
        d.decoration_type_select = $('#decoration_type_select').select2('data').map(item => item.id).join(';');
        d.decoration_subtype_select = $('#decoration_subtype_select').select2('data').map(item => item.id).join(';');
        d.size_characteristic_select = $('#size_characteristic_select').select2('data').map(item => item.id).join(';');
        d.monochrome_or_colour_select = $('#monochrome_or_colour_select').select2('data').map(item => item.id).join(';');
        d.technique_select = $('#technique_select').select2('data').map(item => item.id).join(';');
        d.ornamented_text_select = $('#ornamented_text_select').select2('data').map(item => item.id).join(';');
        d.decoration_subject_select = $('#decoration_subject_select').select2('data').map(item => item.id).join(';');
        d.decoration_colours_select = $('#decoration_colours_select').select2('data').map(item => item.id).join(';');
        d.decoration_characteristics_select = $('#decoration_characteristics_select').select2('data').map(item => item.id).join(';');
        d.musicology_type_select = $('#musicology_type_select').select2('data').map(item => item.id).join(';');

        d.binding_date_years_max = $('#ms_binding_date_years_max').val();

        
        d.decoration_size_height_min = $('#decoration_size_height_min').val();
        d.decoration_size_height_max = $('#decoration_size_height_max').val();
        d.decoration_size_width_min = $('#decoration_size_width_min').val();
        d.decoration_size_width_max = $('#decoration_size_width_max').val();
        d.decoration_addition_date_min = $('#decoration_addition_date_min').val();
        d.decoration_addition_date_max = $('#decoration_addition_date_max').val();
        d.decoration_addition_date_years_min = $('#decoration_addition_date_years_min').val();
        d.decoration_addition_date_years_max = $('#decoration_addition_date_years_max').val();


        d.musicology_how_many_lines_min = $('#musicology_how_many_lines_min').val();
        d.musicology_how_many_lines_max = $('#musicology_how_many_lines_max').val();
        

        d.formula_text = $('#formula_text').val();
        d.rite_name_from_ms = $('#rite_name_from_ms').val();
        //d.clla_no = $('#clla_no').val();

        //d.display_as_main_true = $('#display_as_main_true').is(':checked');
        //d.display_as_main_false = $('#display_as_main_false').is(':checked');

        d.projectId = projectId;

        //d.order_column = 'dating__year_from';
        d.order_column = $('#sortField').val();
        d.order_direction = $('.sort-arrow').data('direction') || 'asc'
    }
    
    var manuscripts_table;
    var map = null;
    var markerClusterGroup = null;
    var allMarkers = [];
    var map_bounds;
    var savedPageLength = 25;
    var currentView = 'table';
    var currentPlaceType = 'contemporary_repository_place';

    function initMap() {
        if (map) {
            map.remove();
        }

        var southWest = L.latLng(-89.98155760646617, -180),
            northEast = L.latLng(89.99346179538875, 180);
        var bounds = L.latLngBounds(southWest, northEast);

        var osm = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        });

        map = L.map('manuscripts_map', {
            center: bounds.getCenter(),
            zoom: 2,
            layers: [osm],
            maxBounds: bounds,
            maxBoundsViscosity: 1.0
        });

        markerClusterGroup = L.markerClusterGroup({
            maxClusterRadius: 20,
            disableClusteringAtZoom: 10,
            spiderfyOnMaxZoom: false,
            showCoverageOnHover: false,
            iconCreateFunction: function(cluster) {
                var manuscriptCount = cluster.getAllChildMarkers().reduce(function(sum, marker) {
                    return sum + (marker.manuscriptCount || 1);
                }, 0);
                return L.divIcon({
                    html: '<img src="/static/img/icons/marker_number.svg"><div class="number">' + manuscriptCount + '</div>',
                    className: 'leaflet-marker-icon leaflet-div-icon',
                    iconSize: L.point(25, 41)
                });
            }
        });

        map.addLayer(markerClusterGroup);
        updateMapMarkers();
    }

    function updateMapMarkers() {
        if (!map || !markerClusterGroup) return;

        markerClusterGroup.clearLayers();
        allMarkers = [];

        var data = manuscripts_table.rows({ search: 'applied' }).data().toArray();
        var manuscriptsByLocation = {};

        // Group manuscripts by coordinates
        data.forEach((item, index) => {
            let lat, lon, name, id;
            if (currentPlaceType === 'contemporary_repository_place') {
                lat = item.contemporary_repository_place_latitude;
                lon = item.contemporary_repository_place_longitude;
                name = item.contemporary_repository_place_name;
                id = item.id;
            } else if (currentPlaceType === 'place_of_origin') {
                lat = item.place_of_origin_latitude;
                lon = item.place_of_origin_longitude;
                name = item.place_of_origin_name;
                id = item.id;
            } else {
                lat = item.binding_place_latitude;
                lon = item.binding_place_longitude;
                name = item.binding_place_name;
                id = item.id;
            }

            if (lat && lon && !isNaN(lat) && !isNaN(lon)) {
                let key = `${lat},${lon}`;
                if (!manuscriptsByLocation[key]) {
                    manuscriptsByLocation[key] = { lat, lon, name, manuscripts: [] };
                }
                manuscriptsByLocation[key].manuscripts.push({ id, name: item.name, shelf_mark: item.shelf_mark });
            }
        });

        // Create markers for each unique location
        Object.values(manuscriptsByLocation).forEach(location => {
            let popupContent = `<b>${location.name || 'Unknown'}</b><ul class="list-disc pl-4">`;
            location.manuscripts.forEach(ms => {
                const shelfMark = ms.shelf_mark || ''; // Fallback to empty string if shelf_mark is undefined
                const displayName = shelfMark ? `${shelfMark}, ${ms.name || 'Manuscript ' + ms.id}` : ms.name || 'Manuscript ' + ms.id;
                popupContent += `<li><a href="/static/page.html?p=manuscript&id=${ms.id}" class="text-blue-600 hover:underline">${displayName}</a></li>`;
            });
            popupContent += '</ul>';
            var marker = L.marker([location.lat, location.lon], {
                icon: L.divIcon({
                    html: `<img src="/static/img/icons/marker_number.svg">${location.manuscripts.length > 1 ? '<div class="number">' + location.manuscripts.length + '</div>' : ''}`,
                    className: 'leaflet-marker-icon leaflet-div-icon',
                    iconSize: L.point(25, 41)
                })
            });
            marker.manuscriptCount = location.manuscripts.length; // Store manuscript count for clustering
            marker.bindPopup(popupContent, { autoPan: true });
            allMarkers.push(marker);
            markerClusterGroup.addLayer(marker);
        });

        if (allMarkers.length > 0) {
            var group = new L.featureGroup(allMarkers);
            map_bounds = group.getBounds();
            map.fitBounds(map_bounds, { padding: [50, 50] });
        }

        map.invalidateSize();
    }





    var manuscripts_table = $('#manuscripts').DataTable({
        "ajax": {
            "url": pageRoot + "/api/manuscripts/?format=datatables",
            "dataSrc": function (data) {
                var processedData = [];
                for (var c in data.data) {
                    processedData[c] = {};
                    for (var f in data.data[c]) {
                        processedData[c][f] = getPrintableValues(f, data.data[c][f]).value;
                    }
                }
                return processedData;
            },
            "data": getFilterData
        },
        "processing": false,
        "serverSide": true,
        "lengthMenu": [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
        "pagingType": "full_numbers",
        "pageLength": savedPageLength,
        "columns": [
            { "data": "main_script", "title": "Main Script", visible: false },
            {
                "data": "image",
                "title": "Image",
                "width": "220px",
                "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                    if (oData.image && oData.image.length > 3) {
                        $(nTd).html("<img src='" + oData.image + "' style='max-height: 170px; max-width: 190px;'></img>");
                    }
                }
            },
            {
                "data": "name",
                "title": "Info",
                "fnCreatedCell": function (nTd, sData, oData, iRow, iCol) {
                    let html = "<h3 class='ms_name'><a href='/static/page.html?p=manuscript&id=" + oData.id + "' class='text-blue-600 hover:underline'>" + oData.rism_id + " " + (oData.name || '') + "</a></h3>"
                        + "<div class='left_script_content'>"
                        + "<div class='ms_foreign_id'><span class='mspltext'> " + (oData.contemporary_repository_place_name || '') + ":</span> "+ (oData.shelf_mark || '') + "<span class='mspltext'> (Shelfmark), </span><br /><span class='mspltext'>Manuscripta.pl: </span>" + (oData.foreign_id || '') + "</div>"
                        + "<div class='ms_dating'><b>Dating: </b>" + (oData.dating || '') + "</div>"
                        + "<div class='ms_place_of_origin'><b>Place of origin: </b>" + (oData.place_of_origin_name || '') + "</div>"
                        + "<div class='ms_place_of_origin'><b>Medieval provenance: </b>" + (oData.ms_provenance || '') + "</div>"
                        + "</div>"
                        + "<div class='right_script_content'>"
                        + "<div class='ms_folios'><span class='decorated_left'>Number of folios: </span><span class='decorated_right'>" + (oData.folios_no || '-') + "</span></div>"
                        + "<div class='ms_measurements'><span class='decorated_left'>Measurements: </span><span class='decorated_right'>" + (oData.page_size_max_h || '-') + "mm x " + (oData.page_size_max_w || '-') + "mm</span></div>"
                        + "<div class='ms_main_script'><span class='decorated_left'>Main script: </span><span class='decorated_right'>" + (oData.main_script || '') + "</span></div>"
                        + "<div class='ms_decorated'><span class='decorated_left'>Decorated: </span><span class='decorated_right'>" + (oData.decorated || '') + "</span></div>"
                        + "<div class='ms_music_notation'><span class='decorated_left'>Music notation: </span><span class='decorated_right'>" + (oData.music_notation || '') + "</span></div>"
                        + "<div class='ms_binding_date'><span class='decorated_left'>Binding date: </span><span class='decorated_right'>" + (oData.binding_date || '') + "</span></div>"
                        + "</div>";
                    $(nTd).html(html);
                }
            },
            { "data": "id", "title": "ID", visible: false },
            { "data": "rism_id", "title": "RISM ID", visible: false },
            { "data": "ms_provenance", "title": "Medieval Provenance", visible: false },
            { "data": "folios_no", "title": "Folios No", visible: false },
            { "data": "page_size_max_h", "title": "Page Size Max Height", visible: false },
            { "data": "page_size_max_w", "title": "Page Size Max Width", visible: false },
            { "data": "foreign_id", "title": foreign_id_name, visible: false },
            { "data": "contemporary_repository_place_name", "title": "Contemporary Repository Place Name", visible: false },
            { "data": "contemporary_repository_place_latitude", "title": "Contemporary Repository Place Latitude", visible: false },
            { "data": "contemporary_repository_place_longitude", "title": "Contemporary Repository Place Longitude", visible: false },
            { "data": "shelf_mark", "title": "Shelfmark", visible: false },
            { "data": "place_of_origin_name", "title": "Place of Origin Name", visible: false },
            { "data": "place_of_origin_latitude", "title": "Place of Origin Latitude", visible: false },
            { "data": "place_of_origin_longitude", "title": "Place of Origin Longitude", visible: false },
            { "data": "dating", "title": "Dating", visible: false },
            { "data": "dating_year", "title": "Dating Year", visible: false },
            { "data": "decorated", "title": "Decorated", visible: false },
            { "data": "music_notation", "title": "Music Notation", visible: false },
            { "data": "binding_date", "title": "Binding Date", visible: false },
            { "data": "binding_place_name", "title": "Binding Place Name", visible: false },
            { "data": "binding_place_latitude", "title": "Binding Place Latitude", visible: false },
            { "data": "binding_place_longitude", "title": "Binding Place Longitude", visible: false }
        ],
        "initComplete": function() {
            // Inject sort dropdown before the search bar
            $('#sortField').select2();
        },
        "drawCallback": function() {
            if (currentView === 'map') {
                updateMapMarkers();
            }
        }
    });

    $('#sortField').select2({
        minimumResultsForSearch: Infinity // Disable search/typing
    });

    // Toggle sort direction and reload DataTable
    $('.sort-arrow').on('click', function() {
        var $arrow = $(this);
        var currentDirection = $arrow.data('direction');
        var newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        $arrow.data('direction', newDirection).text(newDirection === 'asc' ? '▲' : '▼');
        manuscripts_table.ajax.reload();
    });

    // Reload DataTable on sortField change
    $('#sortField').on('change', function() {
        manuscripts_table.ajax.reload();
    });



    $('#tableViewBtn').click(function() {
        if (currentView !== 'table') {
            currentView = 'table';
            $('#tableContainer').show();
            $('#manuscripts_map').hide();
            $('#placeTypeSelector').closest('.select2-container').hide();
            manuscripts_table.page.len(savedPageLength).draw();
            if (map) {
                map.remove();
                map = null;
                markerClusterGroup = null;
            }
            $('#tableViewBtn').addClass('font-bold bg-blue-500').removeClass('bg-gray-200');
            $('#mapViewBtn').removeClass('font-bold bg-blue-500').addClass('bg-gray-200');
        }
    });

    $('#mapViewBtn').click(function() {
        if (currentView !== 'map') {
            currentView = 'map';
            savedPageLength = manuscripts_table.page.len();
            $('#tableContainer').hide();
            $('#manuscripts_map').show();
            $('#placeTypeSelector').closest('.select2-container').show();
            manuscripts_table.page.len(-1).draw();
            initMap();
            $('#mapViewBtn').addClass('font-bold bg-blue-500').removeClass('bg-gray-200');
            $('#tableViewBtn').removeClass('font-bold bg-blue-500').addClass('bg-gray-200');
        }
    });

    $('#placeTypeSelector').select2();

    $('#placeTypeSelector').change(function() {
        currentPlaceType = $(this).val();
        if (currentView === 'map') {
            updateMapMarkers();
        }
    });

// Optional: translation map for cases where filter key != DOM id
const filterIdMap = {
  name: 'ms_name_select',
  foreign_id: 'ms_foreign_id_select',
  liturgical_genre: 'ms_liturgical_genre_select',
  contemporary_repository_place: 'ms_contemporary_repository_place_select',
  shelfmark: 'ms_shelfmark_select',
  place_of_origin: 'ms_place_of_origin_select',

  dating_min: 'ms_dating_min',
  dating_max: 'ms_dating_max',
  dating_years_min: 'ms_dating_years_min',
  dating_years_max: 'ms_dating_years_max',

  binding_date_min: 'ms_binding_date_min',
  binding_date_max: 'ms_binding_date_max',
  binding_date_years_min: 'ms_binding_date_years_min',
  binding_date_years_max: 'ms_binding_date_years_max',

  binding_date_years_max: 'ms_binding_date_years_max',

  order_column: 'sortField'
};

// Resolves the selector (#id) for a given filter key
function resolveSelectorFromKey(key) {
  if (filterIdMap.hasOwnProperty(key)) {
    const id = filterIdMap[key];
    return id.startsWith('#') ? id : `#${id}`;
  }

  const msPrefixed = `#ms_${key}`;
  if (document.querySelector(msPrefixed)) return msPrefixed;

  const plain = `#${key}`;
  if (document.querySelector(plain)) return plain;

  const alt = `#${key.replace(/_true|_false$/, '')}`;
  if (document.querySelector(alt)) return alt;

  return plain;
}

// Returns the element for a given key
function getElementForKey(key) {
  const selector = resolveSelectorFromKey(key);
  return document.querySelector(selector);
}
// --- Improved selector resolver ---
function resolveSelectorFromKey(key) {
  // Check explicit map first
  if (filterIdMap.hasOwnProperty(key)) {
    const id = filterIdMap[key];
    return id.startsWith('#') ? id : `#${id}`;
  }

  // Try variations from your getFilterData naming pattern
  const candidates = [
    `#ms_${key}_select`,
    `#ms_${key}`,
    `#${key}_select`,
    `#${key}`,
  ];

  for (const sel of candidates) {
    if (document.querySelector(sel)) return sel;
  }

  return `#${key}`;
}

function updateTags() {
    const d = {};
    getFilterData(d);

    const container = document.getElementById('filterTagsContainer');
    if (!container) return;
    container.innerHTML = '';

    for (const [key, value] of Object.entries(d)) {
        // skip irrelevant keys
        if (['projectId', 'order_column', 'order_direction', 'dating_years_min', 'dating_years_max'].includes(key))
            continue;

        // skip empty/false values
        if (value === undefined || value === null || value === '' || value === false)
            continue;

        const selector = resolveSelectorFromKey(key);
        const el = document.querySelector(selector);
        if (!el) continue;

        let displayText = '';
        const label = prettifyKeyLabel(key);

        if (el.tagName === 'INPUT' && el.type === 'checkbox') {
            // For checkboxes, only show the label (True/False is in the name)
            displayText = label;
        } else if (el.tagName === 'SELECT' && $(el).hasClass('select2-hidden-accessible')) {
            // Select2: show text of selected items
            const items = $(el).select2('data');
            const valText = items.map(i => i.text || i.id).join('; ');
            displayText = `<strong>${label}</strong>: ${valText}`;
        } else {
            // Input/number fields: label + value
            displayText = `<strong>${label}</strong>: ${value}`;
        }

        const tag = document.createElement('span');
        tag.className = 'filter-tag';
        tag.innerHTML = displayText;

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'filter-tag-x';
        btn.innerHTML = '&times;';
        btn.dataset.key = key;
        btn.dataset.target = selector;
        btn.addEventListener('click', () => clearFilter(btn));

        tag.appendChild(btn);
        container.appendChild(tag);
    }
}


// Converts snake_case keys to readable labels
function prettifyKeyLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, s => s.toUpperCase());
}

// Clears the specific filter element dynamically depending on its DOM type
function clearFilter(btn) {
  const key = btn.dataset.key;
  const targetSelector = btn.dataset.target;
  const el = document.querySelector(targetSelector);

  if (!el) {
    console.warn('clearFilter: element not found for', key, 'selector', targetSelector);
    return;
  }

  const tag = el.tagName.toLowerCase();
  const typeAttr = (el.getAttribute('type') || '').toLowerCase();

  console.log('Clearing', key, '->', targetSelector, '| tag:', tag, '| type:', typeAttr);

  // Handle <select> (Select2 single or multiple)
  if (tag === 'select') {
    try {
      $(el).val(null).trigger('change.select2');
    } catch (e) {}
    el.value = '';
    el.dispatchEvent(new Event('change', { bubbles: true }));
    try { $(el).trigger('change'); } catch (e) {}
    try { $(el).trigger('select2:clear'); } catch (e) {}
  }
  // Handle checkboxes
  else if (tag === 'input' && typeAttr === 'checkbox') {
    el.checked = false;
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // Handle radio buttons
  else if (tag === 'input' && typeAttr === 'radio') {
    const name = el.getAttribute('name');
    if (name) {
      document.querySelectorAll(`input[type="radio"][name="${CSS.escape(name)}"]`).forEach(r => {
        r.checked = false;
        r.dispatchEvent(new Event('change', { bubbles: true }));
      });
    } else {
      el.checked = false;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }
  // Handle text, number, range, textarea, etc.
  else if ((tag === 'input' && ['text','number','range','search','tel','email','url'].includes(typeAttr)) || tag === 'textarea') {
    el.value = '';
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }
  // Fallback
  else {
    try { el.value = ''; } catch (e) {}
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Sync duplicate controls (if they exist)
  syncMirroredControls(key);

  // Refresh tags and filters
  updateTags();
  if (typeof processFilters === 'function') processFilters();
}

// Keeps duplicate UI controls (like quick filters) in sync when one is cleared
function syncMirroredControls(key) {
  const baseKey = key.replace(/_(true|false)$/, '');
  const candidates = Array.from(document.querySelectorAll('input, select, textarea'))
    .filter(el => {
      const id = el.id || '';
      const name = el.getAttribute('name') || '';
      return id.includes(baseKey) || name.includes(baseKey);
    });

  candidates.forEach(el => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();

    if (tag === 'input' && type === 'checkbox') {
      el.checked = false;
      el.dispatchEvent(new Event('change', { bubbles: true }));
    } else if (tag === 'select') {
      try { $(el).val(null).trigger('change.select2'); } catch (e) {}
      el.value = '';
      el.dispatchEvent(new Event('change', { bubbles: true }));
      try { $(el).trigger('change'); } catch (e) {}
    } else if (tag === 'input' || tag === 'textarea') {
      try { el.value = ''; } catch (e) {}
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
}


}

