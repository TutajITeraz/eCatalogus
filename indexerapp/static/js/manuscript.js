let manuscriptId = null;
var map = null;
var map_bounds = null;

const colorPalette = [
  "#e6194B",
  "#3cb44b",
  "#ffe119",
  "#4363d8",
  "#f58231",
  "#911eb4",
  "#42d4f4",
  "#f032e6",
  "#bfef45",
  "#fabed4",
  "#469990",
  "#dcbeff",
  "#9A6324",
  "#fffac8",
  "#800000",
  "#aaffc3",
  "#808000",
  "#ffd8b1",
];
let traditionColors = {};
let traditionMap = {};
let IDENTIFY_TRADITIONS = false;
let colorIndex = 0;

manuscriptId = urlParams.get("id");

function setTableHeight() {
  var windowHeight = $(window).height();
  var windowWidth = $(window).width();
  // console.log('height: ', windowWidth);
  if (windowWidth > 640) {
    var tableHeight = windowHeight - 400;
  } else {
    var tableHeight = windowHeight - 370;
  }

  $("#manuscriptPage").css("height", tableHeight + "px");
}

function initZoomist() {
  new Zoomist(".zoomist-container", {
    // Optional parameters
    maxScale: 2.5,
    bounds: true,
    // if you need slider
    slider: true,
    // if you need zoomer
    zoomer: true,
  });
}

$(document).ready(function () {
  console.log("document ready function");
  setTimeout(function () {
    setTableHeight();
  }, 700); // A small delay ensures elements are fully rendered
});

// Adjust height on window resize
$(window).resize(function () {
  setTableHeight();
});

window.openUniversalPopup = async function (event) {
  try {
    // Pobierz nazwę parametru z atrybutu data-param (domyślnie brak dodatkowego parametru)
    const paramName = event.currentTarget.getAttribute("data-param") || null;
    // Pobierz źródło ID z atrybutu data-id-source lub użyj statycznego ID
    const idSource =
      event.currentTarget.getAttribute("data-id-source") || "static";
    let idValue;

    if (idSource === "getMSInfo") {
      const msInfo = await window.getMSInfo();
      idValue = msInfo?.manuscript?.id;
    } else if (idSource === "static") {
      idValue = event.currentTarget.getAttribute("data-id");
    } else if (window[idSource] && typeof window[idSource] === "function") {
      const result = await window[idSource]();
      idValue = result?.id;
    } else {
      throw new Error(`Nieznane źródło ID: ${idSource}`);
    }

    if (!idValue) {
      throw new Error("ID not found");
    }

    // Pobierz bazowy URL z href linku
    let popupUrl = event.currentTarget.getAttribute("href");
    if (paramName) {
      popupUrl = `${popupUrl}&${paramName}=${idValue}`;
    } else {
      popupUrl = popupUrl.replace("__fk__", idValue);
    }

    // Otwórz popup
    const popup = window.open(
      popupUrl,
      "popup",
      "width=800,height=600,resizable=yes,scrollbars=yes"
    );
  } catch (error) {
    console.error("Błąd podczas otwierania popupu:", error);
    alert("Błąd: Nie udało się załadować informacji.");
  }
};

// Nowy helper do otwierania popupów dla DataTable
window.openDataTablePopup = (url, tableToRefresh = null) => {
  const popup = window.open(
    url,
    "popup",
    "width=800,height=600,resizable=yes,scrollbars=yes"
  );
  const checkPopupClosed = setInterval(() => {
    if (popup.closed) {
      clearInterval(checkPopupClosed);
      if (tableToRefresh) {
        tableToRefresh.ajax.reload();
      }
    }
  }, 500);
};

async function getMSInfo() {
  return fetchOnce(pageRoot + `/ms_info/?pk=${manuscriptId}`);
}

async function getTEIUrl() {
  //return pageRoot + '/ms_tei/?ms=' + (await getMSInfo()).manuscript.id;

  return pageRoot + "/manuscript_tei/?ms=" + (await getMSInfo()).manuscript.id;
}

async function getMSInfoFiltered() {
  var info = (await getMSInfo()).manuscript;

  var infoCod = (await getCodicologyInfo()).info;

  return {
    manuscript: {
      common_name: info.common_name,
      contemporary_repository: info.contemporary_repository_place,
      shelf_mark: info.shelf_mark,
      rism_id: info.rism_id,
      foreign_id: info.foreign_id,
      shelf_mark: info.shelf_mark,
      liturgical_genres: info.ms_genres.join([(separator = ", ")]),
      liturgical_genre_comment: info.liturgical_genre_comment,
      dating: info.dating,
      dating_comment: info.dating_comment,
      place_of_origin: info.place_of_origin,
      place_of_origin_comment: info.place_of_origin_comment,
      decorated: info.decorated,
      music_notation: info.music_notation,

      form_of_an_item: info.form_of_an_item,
      connected_ms: info.connected_ms,
      where_in_the_connected_ms: info.where_in_connected_ms,
      /*
            number_of_parchment_folios: infoCod.number_of_parchment_folios,
            number_of_paper_leaves: infoCod.number_of_paper_leaves,
            parchment_thickness: infoCod.parchment_thickness,
            max_page_size: infoCod.page_size_max_height + " mm x "+infoCod.page_size_max_width+" mm " ,
            */
      general_comment: info.general_comment,
      url: '<a href="' + info.links + '">' + info.links + "</a>",
      additional_url:
        '<a href="' + info.additional_url + '">' + info.links + "</a>",
      iiif_manifest_url:
        '<a href="' +
        info.iiif_manifest_url +
        '">' +
        info.iiif_manifest_url +
        "</a>",
      authors: info.authors,
      data_contributor: info.data_contributor,
      entry_date: info.entry_date,
    },
  };
}

async function getCodicologyInfo() {
  return fetchOnce(pageRoot + `/codicology_info/?pk=${manuscriptId}`);
}

async function getCodicologyFiltered() {
  var info = (await getCodicologyInfo()).info;

  var infoMS = (await getMSInfo()).manuscript;

  var parchment_thickness = info.parchment_thickness_min;

  if (info.parchment_thickness_max != parchment_thickness)
    parchment_thickness += " - " + info.parchment_thickness_max;

  return {
    info: {
      number_of_parchment_folios: info.number_of_parchment_folios,
      number_of_paper_leaves: info.number_of_paper_leaves,
      parchment_thickness: parchment_thickness,
      parchment_colour: info.parchment_colour,
      parchment_comment: info.parchment_comment,
      max_page_size:
        info.page_size_max_width +
        " mm x " +
        info.page_size_max_height +
        " mm ",
      max_paper_size:
        info.paper_size_max_width +
        " mm x " +
        info.paper_size_max_height +
        " mm ",
      main_script: infoMS.main_script,
      how_many_columns_mostly: infoMS.how_many_columns_mostly,
      lines_per_page_usually: infoMS.lines_per_page_usually,
      watermarks: info.watermarks,
      foliation_comment: info.foliation_comment,
      authors: info.authors,
      data_contributor: info.data_contributor,
      entry_date: info.entry_date,
    },
  };
}

async function getProvenanceInfo() {
  return fetchOnce(pageRoot + `/provenance_info/?ms=${manuscriptId}`);
}

async function getProvenanceColumns() {
  info = await getProvenanceInfo();
  if (info === "undefined" || info === null) return [];
  first_row = info.data[0];
  if (first_row === "undefined" || first_row === null) return [];

  columns = [];

  for (k in first_row) columns.push(getPrintableValues(k, "").name);

  return columns;
}

async function getBibliographyInfo() {
  return fetchOnce(pageRoot + `/bibliography_info/?ms=${manuscriptId}`);
}

async function getBooksHTML() {
  books = (await getBibliographyInfo()).data;
  booksHTML = "";
  for (b in books) {
    booksHTML += books[b];
  }
  return booksHTML;
}

async function getDecorationInfo() {
  return fetchOnce(pageRoot + `/decoration_info/?ms=${manuscriptId}`);
}
async function getQuiresInfo() {
  return fetchOnce(pageRoot + `/quires_info/?ms=${manuscriptId}`);
}
async function getConditionInfo() {
  return fetchOnce(pageRoot + `/condition_info/?ms=${manuscriptId}`);
}
async function getCLLAInfo() {
  return fetchOnce(pageRoot + `/clla_info/?ms=${manuscriptId}`);
}
async function getOriginsInfo() {
  return fetchOnce(pageRoot + `/origins_info/?ms=${manuscriptId}`);
}

async function getBindingInfo() {
  return fetchOnce(pageRoot + `/binding_info/?ms=${manuscriptId}`);
}

async function getMusicNotationInfo() {
  return fetchOnce(pageRoot + `/music_notation_info/?ms=${manuscriptId}`);
}

/*
async function getHandsInfo() {
    return fetchOnce(`/hands_info/?pk=${manuscriptId}`);
}
*/
async function getWatermarksInfo() {
  return fetchOnce(pageRoot + `/watermarks_info/?ms=${manuscriptId}`);
}
async function getBibliographyPrintableInfo() {
  return fetchOnce(pageRoot + `/bibliography_print/?ms=${manuscriptId}`);
}

// LAYOUTS
// LAYOUTS
var layouts_table;
function init_layouts_table() {
  layouts_table = $("#layouts").DataTable({
    ajax: {
      url: pageRoot + "/layouts_info/?ms=" + manuscriptId,
      dataSrc: (data) => data.data,
    },
    processing: false,
    serverSide: true,
    lengthMenu: [
      [10, 25, 50, 100, -1],
      [10, 25, 50, 100, "All"],
    ],
    pagingType: "full_numbers",
    pageLength: 25,
    bAutoWidth: false,
    columns: [
      {
        data: "graph_img",
        name: "graph_img",
        title: "image",
        /*render: renderImg,*/
        visible: false,
      },
      { data: "name", title: "name", width: "5%" },
      { data: "where_in_ms_from", title: "where in MS from", visible: false },
      { data: "where_in_ms_to", title: "where in MS to", visible: false },
      {
        data: "where",
        title: "where in MS",
        render: (data, type, row) => {
          //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
          //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);
          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;
          //if(fromIndex)
          fromText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_from}')">${row.where_in_ms_from}</a></b>`;
          //if(toIndex)
          toText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_to}')">${row.where_in_ms_to}</a></b>`;
          return row.where_in_ms_from === row.where_in_ms_to ||
            row.where_in_ms_to === "-"
            ? fromText
            : `${fromText} - ${toText}`;
        },
        width: "10%",
        orderable: false,
      },
      { data: "how_many_columns", title: "how many columns", width: "10%" },
      {
        data: "lines_per_page_minimum",
        title: "lines per page (min)",
        visible: false,
      },
      {
        data: "lines_per_page_maximum",
        title: "lines per page (max)",
        visible: false,
      },
      {
        data: "lines_per_page_minimum",
        title: "lines per Page",
        render: (data, type, row) =>
          row.lines_per_page_minimum === row.lines_per_page_maximum
            ? row.lines_per_page_minimum
            : `${row.lines_per_page_minimum} - ${row.lines_per_page_maximum}`,
        width: "10%",
      },
      {
        data: "written_space_height_max",
        title: "written space height (max)",
        visible: false,
      },
      {
        data: "written_space_width_max",
        title: "written space width (max)",
        visible: false,
      },
      {
        data: "written_space",
        title: "writtern Space max.",
        render: (data, type, row) =>
          `${row.written_space_height_max} mm x ${row.written_space_width_max} mm`,
        width: "10%",
      },
      { data: "ruling_method", title: "ruling method", width: "10%" },
      {
        data: "distance_between_horizontal_ruling",
        title: "distance between horizontal ruling",
        width: "5%",
      },
      {
        data: "distance_between_vertical_ruling",
        title: "distance between vertical ruling",
        width: "5%",
      },
      {
        data: "written_above_the_top_line",
        title: "written above the top line",
        width: "10%",
      },
      { data: "pricking", title: "pricking", width: "5%" },
      { data: "comments", title: "comments", width: "10%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "5%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/layouts/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change layout"
             onclick="window.openDataTablePopup(this.href, window.layouts_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/layouts/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete layout"
             onclick="window.openDataTablePopup(this.href, window.layouts_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
          </a>
        `
            : data,
      },
    ],
    order: [[1, "asc"]],
    initComplete: () => {
      displayUniqueAuthorsAndContributors(layouts_table, "#layouts");
      displayUniqueLayouts(layouts_table, "#layouts");
    },
  });
}

function displayUniqueLayouts(dataTable, targetSelector) {
  var tableData = dataTable.rows().data();
  var uniqueLayouts = {};

  // Iterate over table data to gather unique graph_img and name pairs
  tableData.each(function (row) {
    var key = row.name;
    if (!(key in uniqueLayouts)) {
      uniqueLayouts[key] = row;
    }
  });

  // Create a div to contain the unique layout images and names
  var uniqueLayoutsDiv = $('<div class="unique-layouts printIt">');

  // Iterate over unique layouts and create image elements
  for (var key in uniqueLayouts) {
    if (uniqueLayouts.hasOwnProperty(key)) {
      var layout = uniqueLayouts[key];
      var layoutDiv = $('<div class="layout">');
      var img = $("<img>")
        .attr("src", pageRoot + "/media/" + layout.graph_img)
        .attr("alt", layout.name)
        .css("max-width", "200px");
      var name = $("<p>").text(layout.name).css("text-align", "center");

      layoutDiv.append(img, name);
      uniqueLayoutsDiv.append(layoutDiv);
    }
  }

  // Prepend the unique layouts div above the table
  $(targetSelector).closest("#layouts_wrapper").before(uniqueLayoutsDiv);
}
// MUSIC NOTATION
var music_table;
function init_music_table() {
  music_table = $("#music_notation").DataTable({
    ajax: {
      url: pageRoot + "/music_notation_info/?ms=" + manuscriptId,
      dataSrc: (data) => data.data,
    },
    bAutoWidth: false,
    columns: [
      {
        data: "music_notation_name",
        title: "music notation name",
        width: "13%",
      },
      { data: "sequence_in_ms", title: "sequence in MS", width: "5%" },
      { data: "where_in_ms_from", title: "where in MS from", visible: false },
      { data: "where_in_ms_to", title: "where in MS to", visible: false },
      {
        data: "where",
        title: "where in MS",
        render: (data, type, row) => {
          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;
          fromText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_from}')">${row.where_in_ms_from}</a></b>`;
          toText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_to}')">${row.where_in_ms_to}</a></b>`;
          return row.where_in_ms_from === row.where_in_ms_to ||
            row.where_in_ms_to === "-"
            ? fromText
            : `${fromText} - ${toText}`;
        },
        width: "12%",
        orderable: false,
      },
      { data: "dating", title: "dating", width: "15%" },
      { data: "original", title: "original", width: "5%" },
      { data: "on_lines", title: "on Lines", width: "5%" },
      { data: "music_custos", title: "music custos", width: "5%" },
      { data: "number_of_lines", title: "number of lines", width: "5%" },
      { data: "comment", title: "comment", width: "30%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/manuscriptmusicnotations/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change music notation"
             onclick="window.openDataTablePopup(this.href, window.music_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/manuscriptmusicnotations/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete music notation"
             onclick="window.openDataTablePopup(this.href, window.music_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
          </a>
        `
            : data,
      },
    ],
    initComplete: () =>
      displayUniqueAuthorsAndContributors(music_table, "#music_notation"),
  });
}

var content_table;

function init_content_table(reinit = false) {
  content_table = $("#content").DataTable({
    destroy: reinit,
    ajax: {
      url: pageRoot + "/api/content/?format=datatables", // Add your URL here
      dataSrc: function (data) {
        var processedData = [];

        for (var c in data.data) {
          processedData[c] = {};
          for (var f in data.data[c]) {
            processedData[c][f] = getPrintableValues(f, data.data[c][f]).value;
          }
        }

        return processedData;
      },
      data: function (d) {
        if (d.order && d.order.length > 0) {
          var colIndex = d.order[0].column;
          var dir = d.order[0].dir;
          d.order_column = d.columns[colIndex].data;
          d.order_direction = dir;
        }
        return d;
      },
    },
    processing: false,
    serverSide: true,
    lengthMenu: [
      [10, 25, 50, 100, -1],
      [10, 25, 50, 100, "All"],
    ],
    pagingType: "full_numbers",
    pageLength: 10,
    bAutoWidth: false,
    columns: [
      { data: "manuscript", title: "manuscript id", visible: false },
      { data: "sequence_in_ms", title: "sequence in MS", visible: false },
      { data: "manuscript_name", title: "manuscript", visible: false },
      { data: "where_in_ms_from", title: "where in MS (from)", visible: false },
      { data: "where_in_ms_to", title: "where in MS (to)", visible: false },
      {
        data: "where",
        title: "where in MS",
        render: function (data, type, row, meta) {
          //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
          //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);

          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;

          //if(fromIndex)
          fromText =
            "<b><a  onclick=\"goToCanvasByLabel('" +
            row.where_in_ms_from +
            "')\">" +
            row.where_in_ms_from +
            "</a></b>";

          //if(toIndex)
          toText =
            "<b><a  onclick=\"goToCanvasByLabel('" +
            row.where_in_ms_to +
            "')\">" +
            row.where_in_ms_to +
            "</a></b>";

          if (
            row.where_in_ms_from == row.where_in_ms_to ||
            row.where_in_ms_to == "-"
          )
            return fromText;
          return fromText + " - " + toText;
        },
        width: "10%",
        orderable: false,
      },
      { data: "rite_name_from_ms", title: "rite name from MS", width: "20%" },
      { data: "subsection", title: "subsection", width: "20%" },
      { data: "function", title: "function / genre", width: "10%" },
      { data: "subfunction", title: "subgenre", width: "10%" },
      { data: "biblical_reference", title: "biblical reference", width: "10%" },
      {
        data: "traditions",
        title: "Traditions",
        name: "traditions",
        visible: false,
      },
      {
        data: "formula_standarized",
        name: "formula_standarized",
        title: "Formula (standarized)",
        render: function (data, type, row, meta) {
          var rendered_html = row.formula_standarized || data;

          if (row.traditions && IDENTIFY_TRADITIONS) {
            let traditions = Array.isArray(row.traditions)
              ? row.traditions
              : row.traditions
                  .split(",")
                  .map((t) => t.trim())
                  .filter((t) => t);

            let dots = "";
            if (traditions.length === 0) {
              dots = `<span class="dot" style="background-color: ${traditionColors["Unattributed"]};" title="Unattributed"></span>`;
            } else {
              traditions.forEach((trad) => {
                if (!traditionColors[trad]) {
                  traditionColors[trad] =
                    colorPalette[colorIndex % colorPalette.length];
                  traditionMap[trad] = trad;
                  colorIndex++;
                }
                dots += `<span class="dot" style="background-color: ${traditionColors[trad]};" title="${trad}"></span> `;
              });
            }
            rendered_html = dots + rendered_html;
          }
          if (row.translation_en && row.translation_en.length > 1) {
            let translation_en = ` <span 
                                title="Automatic AI translation:\n${row.translation_en}" 
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

            rendered_html = translation_en + rendered_html;
          }

          return rendered_html;
        },
        width: "40%",
      },
      {
        data: "formula_text",
        title: "formula (text from MS)",
        render: function (data, type, row, meta) {
          if (row.music_notation != "-") return row.formula_text + " (♪)";
          return row.formula_text;
        },
        width: "40%",
      },
      {
        data: "similarity_levenshtein_percent",
        title: "similarity (levenshtein)",
        render: function (data, type, row, meta) {
          return row.similarity_levenshtein_percent + "%";
        },
        createdCell: function (td, cellData, rowData, row, col) {
          if (cellData == "-" || !cellData || cellData < 50)
            $(td).css("color", "red");
          else if (cellData > 99.9) $(td).css("color", "green");
          else $(td).css("color", "#a66b00");
        },
        width: "60px",
      },
      {
        data: "similarity_by_user",
        title: "similarity (by user)",
        width: "5%",
      },
      { data: "original_or_added", title: "original or added", visible: false },
      { data: "quire", title: "quire", width: "5%" },

      { data: "music_notation", title: "music notation", visible: false },
      { data: "original_or_added", title: "original or added", visible: false },
      { data: "proper_texts", title: "proper texts", width: "5%" },

      { data: "translation_en", title: "Translation", visible: false },

      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      { data: "comments", title: "comments", width: "30%" },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: function (data, type) {
          if (type === "display") {
            return `
              <a href="/admin/indexerapp/content/${data}/change/?_to_field=id&_popup=1"
                 class="edit_widget related-widget-wrapper-link change-related"
                 data-popup="yes"
                 title="Change content"
                 onclick="window.openDataTablePopup(this.href, window.content_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
              </a>
              <a href="/admin/indexerapp/content/${data}/delete/?_to_field=id&_popup=1"
                 class="delete_widget related-widget-wrapper-link delete-related"
                 data-popup="yes"
                 title="Delete content"
                 onclick="window.openDataTablePopup(this.href, window.content_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
              </a>
            `;
          }
          return data;
        },
      },
    ],
    order: [
      [1, "asc"], // kolumna 1 to sequence_in_ms, rosnąco
      //{ "data": "where_in_ms_from", "order": "asc" },      // Then sort by the "manuscript" column in descending order
      //{ "data": "sequence_in_ms", "order": "asc" }  // Sort by the "manuscript_name" column in ascending order
      //{ "data": "where_in_ms_from", "order": "asc" }      // Then sort by the "manuscript" column in descending order
    ],
    createdRow: function (row, data, dataIndex) {
      if (data.original_or_added == "ORIGINAL") {
        $(row).addClass("medieval-row");
      } else if (data.original_or_added == "ADDED") {
        $(row).addClass("non-medieval-row");
      }
    },
    drawCallback: function (settings) {
      var columns = settings.aoColumns;
      var json = settings.json;

      if (!json || !json.data) return;

      var columnsToCheck = [
        "function",
        "subfunction",
        "biblical_reference",
        "subsection",
        "quire",
        "similarity_by_user",
        "proper_texts",
        "formula_text",
        "rite_name_from_ms",
        "formula_standarized",
        "comments",
      ];

      var table = this;

      columns.forEach(function (column, columnIndex) {
        if (columnsToCheck.includes(column.data)) {
          var isVisible = json.data.some(function (row) {
            return !(
              row[column.data] == "None" ||
              row[column.data] == null ||
              row[column.data] == ""
            );
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
    initComplete: function (settings, json) {
      displayUniqueAuthorsAndContributors(content_table, "#content");
      displaOriginalAddedLegend(content_table, "#content");
      if (IDENTIFY_TRADITIONS)
        displayTraditionLegend(content_table, "#content");
    },
  });
  content_table.columns(0).search(manuscriptId).draw();
}

// Quires----------------------------------------------------------------
var quires_table;
function init_quires_table() {
  quires_table = $("#quires").DataTable({
    ajax: {
      url: pageRoot + "/quires_info/?ms=" + manuscriptId,
      dataSrc: (data) => data.data,
    },
    processing: false,
    serverSide: true,
    lengthMenu: [
      [10, 25, 50, 100, -1],
      [10, 25, 50, 100, "All"],
    ],
    pagingType: "full_numbers",
    pageLength: 25,
    bAutoWidth: false,
    columns: [
      {
        data: "graph_img",
        name: "graph_img",
        title: "image",
        render: renderImg,
        width: "20%",
      },
      { data: "type_of_the_quire", title: "quire type", width: "15%" },
      { data: "sequence_of_the_quire", title: "sequence in MS", width: "10%" },
      { data: "where_in_ms_from", title: "where in MS (from)", visible: false },
      { data: "where_in_ms_to", title: "where in MS (to)", visible: false },
      {
        data: "where",
        title: "where in MS",
        render: (data, type, row) => {
          //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
          //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);
          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;
          //if(fromIndex)
          fromText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_from}')">${row.where_in_ms_from}</a></b>`;
          //if(toIndex)
          toText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_to}')">${row.where_in_ms_to}</a></b>`;
          return row.where_in_ms_from === row.where_in_ms_to ||
            row.where_in_ms_to === "-"
            ? fromText
            : `${fromText} - ${toText}`;
        },
        width: "15%",
        orderable: false,
      },
      { data: "comment", title: "comment", width: "30%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/quires/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change quire"
             onclick="window.openDataTablePopup(this.href, window.quires_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/quires/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete quire"
             onclick="window.openDataTablePopup(this.href, window.quires_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
          </a>
        `
            : data,
      },
    ],
    order: [
      { data: "sequence_of_the_quire", order: "asc" },
      { data: "where_in_ms_from", order: "asc" },
    ],
    initComplete: () =>
      displayUniqueAuthorsAndContributors(quires_table, "#quires"),
  });
}

//Decoration----------------------------------------------------------------

/*
var decoration_table;

function init_decoration_table() {
    var decoration_groupColumn = 2;
    decoration_table = $('#decoration').DataTable({
        "ajax": {
            "url": pageRoot + '/decoration_info/?ms=' + manuscriptId,
            "dataSrc": function (data) {
                return data.data;
            }
        },
        "columns": [
            { "data": "id", "title": "id"  , "visible": false },
            { "data": "decoration_type", "title": "Decoration type"  , "visible": false },
            { "data": "decoration_subtype", "title": "Decoration subtype" },
            { "data": "size_characteristic", "title": "Size characteristic", "visible": false },
            { "data": "size_height_min", "title": "Size - height min", "visible": false },
            { "data": "size_height_max", "title": "Size - height max", "visible": false },
            { "data": "size_width_min", "title": "Size - width min", "visible": false },
            { "data": "size_width_max", "title": "Size - width max", "visible": false },
            { "data": "size", "title": "Size",
                "render": function(data, type, row, meta) {
                    let size_characteristic = row.size_characteristic;
                    let width='';
                    let height='';
                    if (row.size_width_min != '-' && row.size_width_max != '-' && row.size_width_min != row.size_width_max)
                        width = row.size_width_min + " mm - " + row.size_width_max + " mm";
                    else if (row.size_width_min != '-' && row.size_width_max != '-' ) // min == max
                        width = row.size_width_min + " mm ";
                    else if (row.size_width_min != '-')
                        width = row.size_width_min  + " mm"
                    else if (row.size_width_max != '-')
                        width = row.size_width_max + " mm"

                    if (row.size_height_min != '-' && row.size_height_max != '-' && row.size_height_min != row.size_height_max)
                        height = row.size_height_min + " mm - " + row.size_height_max + " mm";
                    else if (row.size_height_min != '-' && row.size_height_max != '-' ) // min == max
                        height = row.size_height_min + " mm ";
                    else if (row.size_height_min != '-')
                        height = row.size_height_min  + " mm"
                    else if (row.size_height_max != '-')
                        height = row.size_height_max + " mm"

                    let dimensions = [width,height].join(" x ");
                    if(dimensions<4)
                        dimensions = '';
                    
                    return size_characteristic.toLowerCase()+' '+dimensions;
            }},
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
                }
            },
            { "data": "content", "title": "content", "visible": false },
            { "data": "calendar", "title": "calendar", "visible": false },
            { "data": "rite_name_standarized", "title": "rite_name_standarized", "visible": false },
            {
                "data": "decorated_content",
                "title": "Decorated content",
                "render": function (data, type, row, meta) {
                    //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
                    //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);

                    let content = row.content;
                    let calendar = row.calendar;
                    let rite_name_standarized = row.rite_name_standarized;

                    if(content.length<2)
                        content = '';
                    if(calendar.length<2)
                        calendar = '';
                    if(rite_name_standarized.length<2)
                        rite_name_standarized = '';



                    return content+' '+calendar+' '+rite_name_standarized;
                }
            },

            { "data": "location_on_the_page", "title": "Location on the page" },
            { "data": "original_or_added", "title": "Original or added", "visible": false },
            { "data": "monochrome_or_colour", "title": "Monochrome or colour", "visible": false },
            //{ "data": "characteristic", "title": "Decoration characteristic" },
            { 
                "data": "decoration_subjects", 
                "title": "Subjects",
                "render": function(data, type, row) {
                    return Array.isArray(data) ? data.join(", ") : data;
                }
            },
            { 
                "data": "decoration_colours", 
                "title": "Colours",
                "render": function(data, type, row) {
                    return Array.isArray(data) ? data.join(", ") : data;
                }
                , "visible": false
            },
            { 
                "data": "decoration_characteristics", 
                "title": "Characteristics",
                "render": function(data, type, row) {
                    return Array.isArray(data) ? data.join(", ") : data;
                }
            },
            {
                "data": "colour",
                "title": "Colour",
                "render": function (data, type, row, meta) {

                    let monochrome_or_colour = row.monochrome_or_colour;
                    let colours_list = row.decoration_colours;

                    let html_text = '';

                    if(monochrome_or_colour=='C')
                        html_text = '<b>colour </b>'
                    else if (monochrome_or_colour=='C')
                        html_text = '<b>monochrome </b>'

                    for(var c=0; c<colours_list.length; ++c)
                    {
                        var color_box = '<div style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em;  margin-left: 1em; text-align: middle; background-color: '+colours_list[c]+';"></div>'
                        html_text+=color_box
                        html_text+="<span>"+colours_list[c]+"<span>"
                    }

                    return html_text;
                }
            },

            { "data": "technique", "title": "Technique" },
            { "data": "ornamented_text", "title": "Ornamented text" },
            { "data": "date_of_the_addition", "title": "Addition Date" },
            //{ "data": "comments", "title": "Comments" },
            { "data": "authors", "title": "Authors", "visible": false },
            { "data": "data_contributor", "title": "Data contributor", "visible": false },
            { "data": "entry_date", "title": "Entry date", "visible": false },

        ],
        "order": [
            [decoration_groupColumn, 'asc'],
            { "data": "where_in_ms_from", "order": "asc" }      // Then sort by the "manuscript" column in descending order
        ],
        "createdRow": function (row, data, dataIndex) {
            if (data.original_or_added == "ORIGINAL") {
                $(row).addClass('medieval-row');
            } else if (data.original_or_added == "ADDED") {
                $(row).addClass('non-medieval-row');
            }
        },
        "initComplete": function() {
            displayDebate(decoration_table,"#decoration");
            displayComments(decoration_table,"#decoration");
            displaOriginalAddedLegend(decoration_table,"#decoration");
            displayEntryDate(decoration_table,"#decoration");
            displayUniqueAuthorsAndContributors(decoration_table,"#decoration");
        },
        "drawCallback": function (settings) {
            var api = this.api();
            var rows = api.rows({ page: 'current' }).nodes();
            var last = null;

            api.column(decoration_groupColumn, { page: 'current' })
                .data()
                .each(function (group, i) {
                    if (last !== group) {
                        $(rows)
                            .eq(i)
                            .before(
                                '<tr class="table_group"><td colspan="12">' +
                                group +
                                '</td></tr>'
                            );

                        last = group;
                    }
                });
        }
    });
}
*/
//TODO Dla pozostałych tabel
var initials_table;
var decoration_tables_initials = {
  table: null,
  tableSelector: "#initials",
  typeQuery: "initials",
  ornamentedTextVisible: true,
  displaySubsections: true,
};

var decoration_tables_miniatures = {
  table: null,
  tableSelector: "#miniatures",
  typeQuery: "miniatures",
  ornamentedTextVisible: false,
  displaySubsections: false,
};

var decoration_tables_borders_others = {
  table: null,
  tableSelector: "#borders_others",
  typeQuery: "Borders / Others",
  ornamentedTextVisible: false,
  displaySubsections: true,
};

function init_initials_table() {
  init_decoration_table(decoration_tables_initials);
}

function init_borders_others_table() {
  init_decoration_table(decoration_tables_borders_others);
}

function init_miniatures_table() {
  init_decoration_table(decoration_tables_miniatures);
}

function init_decoration_table(table_info) {
  var decoration_groupColumn = 2;
  table_info.table = $(table_info.tableSelector).DataTable({
    ajax: {
      url:
        pageRoot +
        "/decoration_info/?ms=" +
        manuscriptId +
        "&decoration_type=" +
        table_info.typeQuery,
      dataSrc: function (data) {
        return data.data;
      },
    },
    bAutoWidth: false,
    columns: [
      { data: "id", title: "id", visible: false },
      { data: "decoration_type", title: "decoration type", visible: false },
      {
        data: "decoration_subtype",
        title: "decoration subtype",
        visible: false,
      },
      {
        data: "ornamented_text",
        title: "ornamented text",
        width: "15%",
        visible: table_info.ornamentedTextVisible,
      },
      { data: "content", title: "content", visible: false },
      { data: "calendar", title: "calendar", visible: false },
      {
        data: "rite_name_standarized",
        title: "rite_name_standarized",
        visible: false,
      },
      {
        data: "decorated_content",
        title: "decorated content",
        render: function (data, type, row, meta) {
          //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
          //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);

          let content = row.content;
          let calendar = row.calendar;
          let rite_name_standarized = row.rite_name_standarized;

          if (content.length < 2) content = "";
          if (calendar.length < 2) calendar = "";
          if (rite_name_standarized.length < 2) rite_name_standarized = "";

          return content + " " + calendar + " " + rite_name_standarized;
        },
      },
      { data: "where_in_ms_from", title: "where in MS (from)", visible: false },
      { data: "where_in_ms_to", title: "where in MS (to)", visible: false },
      {
        data: "where",
        title: "where in MS",
        render: function (data, type, row, meta) {
          //let fromIndex = findCanvasIndexByLabel(row.where_in_ms_from);
          //let toIndex = findCanvasIndexByLabel(row.where_in_ms_to);

          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;

          //if(fromIndex)
          fromText =
            "<b><a  onclick=\"goToCanvasByLabel('" +
            row.where_in_ms_from +
            "')\">" +
            row.where_in_ms_from +
            "</a></b>";

          //if(toIndex)
          toText =
            "<b><a  onclick=\"goToCanvasByLabel('" +
            row.where_in_ms_to +
            "')\">" +
            row.where_in_ms_to +
            "</a></b>";

          if (
            row.where_in_ms_from == row.where_in_ms_to ||
            row.where_in_ms_to == "-"
          )
            return fromText;
          return fromText + " - " + toText;
        },
        width: "10%",
        orderable: false,
      },
      {
        data: "location_on_the_page",
        title: "location on the page",
        width: "10%",
      },
      {
        data: "size_characteristic",
        title: "size characteristic",
        visible: false,
      },
      { data: "size_height_min", title: "size - height min", visible: false },
      { data: "size_height_max", title: "size - height max", visible: false },
      { data: "size_width_min", title: "size - width min", visible: false },
      { data: "size_width_max", title: "size - width max", visible: false },
      {
        data: "size",
        title: "size",
        render: function (data, type, row, meta) {
          let size_characteristic = row.size_characteristic;
          if (!size_characteristic || size_characteristic == "-")
            size_characteristic = "";

          let width = "";
          let height = "";
          if (
            row.size_width_min != "-" &&
            row.size_width_max != "-" &&
            row.size_width_min != row.size_width_max
          )
            width = row.size_width_min + " - " + row.size_width_max + " mm";
          else if (row.size_width_min != "-" && row.size_width_max != "-")
            // min == max
            width = row.size_width_min + " mm ";
          else if (row.size_width_min != "-")
            width = row.size_width_min + " mm";
          else if (row.size_width_max != "-")
            width = row.size_width_max + " mm";

          if (
            row.size_height_min != "-" &&
            row.size_height_max != "-" &&
            row.size_height_min != row.size_height_max
          )
            height = row.size_height_min + " - " + row.size_height_max + " mm";
          else if (row.size_height_min != "-" && row.size_height_max != "-")
            // min == max
            height = row.size_height_min + " mm ";
          else if (row.size_height_min != "-")
            height = row.size_height_min + " mm";
          else if (row.size_height_max != "-")
            height = row.size_height_max + " mm";

          let dimensions = [height, width].join("<br /> x <br />");
          if (width == "" && height != "") dimensions = height + " height";
          else if (height == "" && width != "") dimensions = width + " width";
          else if (dimensions.length < 16) dimensions = "";

          return size_characteristic.toLowerCase() + "<br />" + dimensions;
        },
        className: "text-center",
        width: "15%",
      },
      { data: "original_or_added", title: "original or added", visible: false },
      {
        data: "monochrome_or_colour",
        title: "monochrome or colour",
        visible: false,
      },
      /*{ "data": "characteristic", "title": "Decoration characteristic" },*/
      {
        data: "decoration_subjects",
        title: "subjects",
        render: function (data, type, row) {
          return Array.isArray(data) ? data.join("; ") : data;
        },
        width: "10%",
      },
      {
        data: "decoration_colours",
        title: "colours",
        render: function (data, type, row) {
          return Array.isArray(data) ? data.join(", ") : data;
        },
        visible: false,
      },
      {
        data: "decoration_characteristics",
        title: "characteristics",
        render: function (data, type, row) {
          return Array.isArray(data) ? data.join(", ") : data;
        },
        width: "15%",
      },
      {
        data: "colour",
        title: "colour",
        render: function (data, type, row, meta) {
          let monochrome_or_colour = row.monochrome_or_colour;
          let colours_list = row.decoration_colours;

          let html_text = "";

          if (monochrome_or_colour == "C") html_text = "<b>multicolored</b>";
          else if (monochrome_or_colour == "M")
            html_text = "<b>monochromatic</b>";
          else if (monochrome_or_colour == "B") html_text = "<b>bicolored</b>";

          for (var c = 0; c < colours_list.length; ++c) {
            var color_box =
              '<br /><div style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em;  margin-left: 1em; text-align: middle; background-color: ' +
              colours_list[c] +
              ';"></div>';
            html_text += color_box;
            html_text += "<span>" + colours_list[c] + "<span>";
          }

          return html_text;
        },
        width: "10%",
      },

      { data: "technique", title: "technique", width: "15%" },
      { data: "date_of_the_addition", title: "addition date" },

      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/decoration/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change decoration"
             onclick="window.openDataTablePopup(this.href, ${table_info.tableSelector.replace(
               "#",
               "decoration_tables_"
             )}.table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/decoration/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete decoration"
             onclick="window.openDataTablePopup(this.href, ${table_info.tableSelector.replace(
               "#",
               "decoration_tables_"
             )}.table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
          </a>
        `
            : data,
      },
      //{ "data": "comments", "title": "Comments" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      { data: "entry_date", title: "entry date", visible: false },
    ],
    order: [
      [decoration_groupColumn, "asc"],
      { data: "where_in_ms_from", order: "asc" }, // Then sort by the "manuscript" column in descending order
    ],
    createdRow: function (row, data, dataIndex) {
      if (data.original_or_added == "ORIGINAL") {
        $(row).addClass("medieval-row");
      } else if (data.original_or_added == "ADDED") {
        $(row).addClass("non-medieval-row");
      }
    },
    initComplete: function (settings, json) {
      displayDebate(table_info.table, table_info.tableSelector);
      displayComments(table_info.table, table_info.tableSelector);
      displaOriginalAddedLegend(table_info.table, table_info.tableSelector);
      displayEntryDate(table_info.table, table_info.tableSelector);
      displayUniqueAuthorsAndContributors(
        table_info.table,
        table_info.tableSelector
      );

      // Get column information from DataTable settings
      var columns = settings.aoColumns;

      // Column names to check for null values
      var columnsToCheck = [
        "decorated_content",
        "location_on_the_page",
        "decoration_subjects",
        "technique",
        "date_of_the_addition",
      ];

      // Get the DataTable instance
      var table = this;

      // Iterate over columns
      columns.forEach(function (column, columnIndex) {
        // Check if the column name matches the ones to be checked
        if (columnsToCheck.includes(column.data)) {
          var isVisible = json.data.some(function (row) {
            return !(
              row[column.data] == "None" ||
              row[column.data] == null ||
              row[column.data] == "" ||
              row[column.data] == "-"
            );
          });

          // Set column visibility based on null values
          settings.oInstance.api().column(columnIndex).visible(isVisible);
        }
      });
    },
    drawCallback: function (settings) {
      var api = this.api();
      var rows = api.rows({ page: "current" }).nodes();
      var last = null;

      if (table_info.displaySubsections) {
        api
          .column(decoration_groupColumn, { page: "current" })
          .data()
          .each(function (group, i) {
            if (last !== group) {
              $(rows)
                .eq(i)
                .before(
                  '<tr class="table_group"><td colspan="12">' +
                    group +
                    "</td></tr>"
                );

              last = group;
            }
          });
      }
    },
  });
}
//init_miniatures_table
//init_borders_others_table
/*
var origins_table;

function init_origins_table() {
    origins_table = $('#origins').DataTable({
        "ajax": {
            "url": pageRoot + '/origins_info/?ms=' + manuscriptId,
            "dataSrc": function (data) {
                return data.data;
            }
        },
        "bAutoWidth": false, 
        "columns": [
            { "data": "id", "title": "id"  , "visible": false },
            { "data": "origins_date", "title": "Origins date", "width": "10%" },
            { "data": "origins_place", "title": "Origins place", "width": "30%"  },
            { "data": "origins_comment", "title": "Origins comment", "width": "60%"  },
            { "data": "provenance_comments", "title": "Provenance comments", "visible": false },
            { "data": "authors", "title": "Authors", "visible": false },
            { "data": "data_contributor", "title": "Data contributor", "visible": false }
        ],
        "initComplete": function() {
            displayDebate(origins_table,"#origins");
            displayUniqueAuthorsAndContributors(origins_table,"#origins");
        }
    });
}

*/

//Condition----------------------------------------------------------------
/*
var condition_table = $('#condition').DataTable({
    "ajax": {
        "url": '/condition_info/?ms=' + manuscriptId,
        "dataSrc": function (data) {
            return data.data;
        }
    },
    "columns": [
        { "data": "damage", "title": "Damage" },
        { "data": "parchment_shrinkage", "title": "Parchment shrinkage" },
        { "data": "illegible_text", "title": "illegible_text" },
        { "data": "ink_corrosion", "title": "Ink corrosion" },
        { "data": "copper_corrosion", "title": "Copper corrosion" },
        { "data": "powdering_or_cracking_paint_layer", "title": "Powdering or cracking paint layer" },
        { "data": "conservation", "title": "Conservation" },
        { "data": "conservation_date", "title": "Conservation date" },
        { "data": "comments", "title": "Comments" },
        { "data": "authors", "title": "Authors", "visible": false },
        { "data": "data_contributor", "title": "Data contributor", "visible": false }
    ],
    "initComplete": function() {
        displayUniqueAuthorsAndContributors(condition_table,"#condition");
    }
});
*/

//Origins----------------------------------------------------------------
var origins_table;

function init_origins_table() {
  origins_table = $("#origins").DataTable({
    ajax: {
      url: pageRoot + "/origins_info/?ms=" + manuscriptId,
      dataSrc: function (data) {
        return data.data;
      },
    },
    bAutoWidth: false,
    columns: [
      { data: "id", title: "id", visible: false },
      { data: "origins_date", title: "origins date", width: "10%" },
      { data: "origins_place", title: "origins place", width: "30%" },
      { data: "origins_comment", title: "origins comment", width: "50%" },
      {
        data: "provenance_comments",
        title: "provenance comments",
        visible: false,
      },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: function (data, type) {
          if (type === "display") {
            return `
              <a href="/admin/indexerapp/origins/${data}/change/?_to_field=id&_popup=1"
                 class="edit_widget related-widget-wrapper-link change-related"
                 data-popup="yes"
                 title="Change origin"
                 onclick="window.openDataTablePopup(this.href, window.origins_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
              </a>
              <a href="/admin/indexerapp/origins/${data}/delete/?_to_field=id&_popup=1"
                 class="delete_widget related-widget-wrapper-link delete-related"
                 data-popup="yes"
                 title="Delete origin"
                 onclick="window.openDataTablePopup(this.href, window.origins_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
              </a>
            `;
          }
          return data;
        },
      },
    ],
    initComplete: function () {
      displayDebate(origins_table, "#origins");
      displayUniqueAuthorsAndContributors(origins_table, "#origins");
    },
  });
}

//Binding----------------------------------------------------------------
/*
var music_table = $('#binding').DataTable({
    "ajax": {
        "url": '/binding_info/?ms=' + manuscriptId,
        "dataSrc": function (data) {
            return data.data;
        }
    },
    "columns": [
        { "data": "max_height", "title": "Height (max)" },
        { "data": "max_width", "title": "Width (max)" },
        { "data": "block_max", "title": "Block (max)" },
        { "data": "date", "title": "Date" },
        { "data": "place_of_origin", "title": "Place of origin" },
        { "data": "type_of_binding", "title": "Type of binding" },
        { "data": "style_of_binding", "title": "Style of binding" },
        { "data": "decoration_comment", "title": "Decoration comment" },
        { "data": "general_comments", "title": "General comments" },
        { "data": "entry_date", "title": "Entry date" },
        { "data": "authors", "title": "Authors" },
        { "data": "decoration", "title": "Decoration" },
        { "data": "material", "title": "Material" }
    ]
});
*/

//Binding Materials----------------------------------------------------------------
var binding_materials_table;
function init_binding_materials_table() {
  binding_materials_table = $("#binding_materials").DataTable({
    ajax: {
      url: pageRoot + "/binding_materials_info/?ms=" + manuscriptId,
      dataSrc: function (data) {
        return data.data;
      },
    },
    columns: [{ data: "material", title: "material" }],
  });
}

// Hands----------------------------------------------------------------
var main_hands;
function init_main_hands() {
  main_hands = $("#main_hands").DataTable({
    ajax: {
      url: pageRoot + "/hands_info/",
      type: "GET",
      data: (d) => ({ is_main_text: true, ms: manuscriptId }),
      dataSrc: (data) => {
        const processedData = [];
        for (const c in data.data) {
          processedData[c] = {};
          for (const f in data.data[c]) {
            processedData[c][f] = getPrintableValues(f, data.data[c][f]).value;
          }
        }
        return processedData;
      },
    },
    processing: false,
    serverSide: false,
    lengthMenu: [
      [10, 25, 50, 100, -1],
      [10, 25, 50, 100, "All"],
    ],
    pagingType: "full_numbers",
    pageLength: 25,
    bAutoWidth: false,
    columns: [
      { data: "hand", title: "hand", width: "15%" },
      { data: "script_name", title: "script name", width: "15%" },
      { data: "sequence_in_ms", title: "sequence in ms", width: "15%" },
      { data: "where_in_ms_from", title: "where in MS (from)", visible: false },
      { data: "where_in_ms_to", title: "where in MS (to)", visible: false },
      {
        data: "is_range_interrupted",
        title: "range interrupted",
        visible: false,
      },
      {
        data: "where",
        title: "where in MS",
        render: (data, type, row) => {
          if (
            row.is_range_interrupted === "Yes" ||
            row.is_range_interrupted === "yes"
          )
            return "";
          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;
          fromText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_from}')">${row.where_in_ms_from}</a></b>`;
          toText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_to}')">${row.where_in_ms_to}</a></b>`;
          return row.where_in_ms_from === row.where_in_ms_to ||
            row.where_in_ms_to === "-"
            ? fromText
            : `${fromText} - ${toText}`;
        },
        width: "15%",
        orderable: false,
      },
      { data: "is_medieval", title: "is medieval?", visible: false },
      {
        data: "is_main_text",
        name: "is_main_text",
        title: "is main text?",
        visible: false,
      },
      { data: "comment", title: "comment", width: "30%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/manuscripthands/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change hand"
             onclick="window.openDataTablePopup(this.href, window.main_hands); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/manuscripthands/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete hand"
             onclick="window.openDataTablePopup(this.href, window.main_hands); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
          </a>
        `
            : data,
      },
    ],
    order: [
      { data: "sequence_in_ms", order: "asc" },
      { data: "where_in_ms_from", order: "asc" },
    ],
    createdRow: (row, data) => {
      $(row).addClass(
        data.is_medieval === true ||
          data.is_medieval === "true" ||
          data.is_medieval === "yes" ||
          data.is_medieval === "Yes"
          ? "medieval-row"
          : "non-medieval-row"
      );
    },
    initComplete: () => {
      displayDebate(main_hands, "#main_hands");
      displayUniqueAuthorsAndContributors(main_hands, "#main_hands");
      displayScriptsLegend(main_hands, "#main_hands");
    },
  });
}

var additions_hands;
function init_additions_hands() {
  additions_hands = $("#additions_hands").DataTable({
    ajax: {
      url: pageRoot + "/hands_info/",
      type: "GET",
      data: (d) => ({ is_main_text: false, ms: manuscriptId }),
      dataSrc: (data) => {
        const processedData = [];
        for (const c in data.data) {
          processedData[c] = {};
          for (const f in data.data[c]) {
            processedData[c][f] = getPrintableValues(f, data.data[c][f]).value;
          }
        }
        return processedData;
      },
    },
    processing: false,
    serverSide: true,
    lengthMenu: [
      [10, 25, 50, 100, -1],
      [10, 25, 50, 100, "All"],
    ],
    pagingType: "full_numbers",
    pageLength: 25,
    bAutoWidth: false,
    columns: [
      { data: "hand", title: "hand", width: "15%" },
      { data: "script_name", title: "script name", width: "15%" },
      { data: "sequence_in_ms", title: "sequence in ms", width: "15%" },
      { data: "where_in_ms_from", title: "where in MS (from)", visible: false },
      { data: "where_in_ms_to", title: "where in MS (to)", visible: false },
      {
        data: "is_range_interrupted",
        title: "range interrupted",
        visible: false,
      },
      {
        data: "where",
        title: "where in MS",
        render: (data, type, row) => {
          if (
            row.is_range_interrupted === "Yes" ||
            row.is_range_interrupted === "yes"
          )
            return "";
          let fromText = row.where_in_ms_from;
          let toText = row.where_in_ms_to;
          fromText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_from}')">${row.where_in_ms_from}</a></b>`;
          toText = `<b><a onclick="goToCanvasByLabel('${row.where_in_ms_to}')">${row.where_in_ms_to}</a></b>`;
          return row.where_in_ms_from === row.where_in_ms_to ||
            row.where_in_ms_to === "-"
            ? fromText
            : `${fromText} - ${toText}`;
        },
        width: "15%",
        orderable: false,
      },
      { data: "is_medieval", title: "is medieval?", visible: false },
      {
        data: "is_main_text",
        name: "is_main_text",
        title: "is main text?",
        visible: false,
      },
      { data: "comment", title: "comment", width: "30%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/manuscripthands/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change hand"
             onclick="window.openDataTablePopup(this.href, window.additions_hands); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/manuscripthands/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete hand"
             onclick="window.openDataTablePopup(this.href, window.additions_hands); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Edit" width="20" height="20">
          </a>
        `
            : data,
      },
    ],
    order: [
      { data: "sequence_in_ms", order: "asc" },
      { data: "where_in_ms_from", order: "asc" },
    ],
    createdRow: (row, data) => {
      $(row).addClass(
        data.is_medieval === true ||
          data.is_medieval === "true" ||
          data.is_medieval === "yes" ||
          data.is_medieval === "Yes"
          ? "medieval-row"
          : "non-medieval-row"
      );
    },
    initComplete: () => {
      displayDebate(additions_hands, "#additions_hands");
      displayUniqueAuthorsAndContributors(additions_hands, "#additions_hands");
      displayScriptsLegend(additions_hands, "#additions_hands");
    },
  });
}

// Watermarks----------------------------------------------------------------
var watermarks_table;
function init_watermarks_table() {
  watermarks_table = $("#watermarks").DataTable({
    ajax: {
      url: pageRoot + "/watermarks_info/?ms=" + manuscriptId,
      dataSrc: (data) => data.data,
    },
    bAutoWidth: false,
    columns: [
      { data: "name", title: "name", width: "20%" },
      {
        data: "watermark_img",
        name: "watermark_img",
        title: "image",
        render: renderImg,
        width: "20%",
      },
      { data: "where_in_manuscript", title: "where in MS", width: "10%" },
      { data: "external_id", title: "external id", width: "10%" },
      { data: "comment", title: "comment", width: "30%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: (data, type) =>
          type === "display"
            ? `
          <a href="/admin/indexerapp/manuscriptwatermarks/${data}/change/?_to_field=id&_popup=1"
             class="edit_widget related-widget-wrapper-link change-related"
             data-popup="yes"
             title="Change watermark"
             onclick="window.openDataTablePopup(this.href, window.watermarks_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
          </a>
          <a href="/admin/indexerapp/manuscriptwatermarks/${data}/delete/?_to_field=id&_popup=1"
             class="delete_widget related-widget-wrapper-link delete-related"
             data-popup="yes"
             title="Delete watermark"
             onclick="window.openDataTablePopup(this.href, window.watermarks_table); return false;">
            <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
          </a>
        `
            : data,
      },
    ],
    order: [{ data: "where_in_manuscript", order: "asc" }],
    initComplete: () =>
      displayUniqueAuthorsAndContributors(watermarks_table, "#watermarks"),
  });
}

//Provenance----------------------------------------------------------------
var provenance_table;

function init_provenance_table() {
  provenance_table = $("#provenance").DataTable({
    ajax: {
      url: pageRoot + "/provenance_info/?ms=" + manuscriptId,
      dataSrc: function (data) {
        return data.data;
      },
    },
    bAutoWidth: false,
    columns: [
      { data: "id", title: "id", visible: false },
      { data: "date_from", title: "date_from", visible: false },
      { data: "date_to", title: "date_to", visible: false },
      {
        data: "date",
        title: "date",
        render: function (data, type, row, meta) {
          if (row.date_from == row.date_to || row.date_to == "-")
            return row.date_from;
          return row.date_from + " - " + row.date_to;
        },
        width: "10%",
      },
      { data: "place", title: "place", width: "30%" },
      { data: "timeline_sequence", title: "timeline_sequence", visible: false },
      { data: "comment", title: "comment", width: "50%" },
      { data: "authors", title: "authors", visible: false },
      { data: "data_contributor", title: "data contributor", visible: false },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: function (data, type) {
          if (type === "display") {
            return `
              <a href="/admin/indexerapp/provenance/${data}/change/?_to_field=id&_popup=1"
                 class="edit_widget related-widget-wrapper-link change-related"
                 data-popup="yes"
                 title="Change provenance"
                 onclick="window.openDataTablePopup(this.href, window.provenance_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
              </a>
              <a href="/admin/indexerapp/provenance/${data}/delete/?_to_field=id&_popup=1"
                 class="delete_widget related-widget-wrapper-link delete-related"
                 data-popup="yes"
                 title="Delete provenance"
                 onclick="window.openDataTablePopup(this.href, window.provenance_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
              </a>
            `;
          }
          return data;
        },
      },
    ],
    order: [
      { data: "timeline_sequence", order: "asc" }, // Sort by the "manuscript_name" column in ascending order
    ],
    initComplete: function () {
      displayDebate(provenance_table, "#provenance");
      displayUniqueAuthorsAndContributors(provenance_table, "#provenance");
    },
  });
}

//Bibliography----------------------------------------------------------------
//Bibliography----------------------------------------------------------------
var bibliography_table;

function init_bibliography_table() {
  bibliography_table = $("#bibliography").DataTable({
    ajax: {
      url: pageRoot + "/bibliography_info/?ms=" + manuscriptId,
      dataSrc: function (data) {
        return data.data;
      },
    },
    processing: false,
    serverSide: true,
    lengthMenu: [
      [10, 25, 50, 100, -1],
      [10, 25, 50, 100, "All"],
    ],
    pagingType: "full_numbers",
    pageLength: 10,
    bAutoWidth: false,
    columns: [
      { data: "title", title: "title", width: "60%" },
      { data: "author", title: "author", width: "20%" },
      { data: "year", title: "year", width: "10%" },
      {
        data: "id",
        title: "Actions",
        visible: DISPLAY_EDIT_OPTIONS,
        orderable: false,
        width: "10%",
        render: function (data, type) {
          if (type === "display") {
            return `
              <a href="/admin/indexerapp/manuscriptbibliography/${data}/change/?_to_field=id&_popup=1"
                 class="edit_widget related-widget-wrapper-link change-related"
                 data-popup="yes"
                 title="Change bibliography"
                 onclick="window.openDataTablePopup(this.href, window.bibliography_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-changelink.svg" alt="Edit" width="20" height="20">
              </a>
              <a href="/admin/indexerapp/manuscriptbibliography/${data}/delete/?_to_field=id&_popup=1"
                 class="delete_widget related-widget-wrapper-link delete-related"
                 data-popup="yes"
                 title="Delete bibliography"
                 onclick="window.openDataTablePopup(this.href, window.bibliography_table); return false;">
                <img src="${pageRoot}/static/admin/img/icon-deletelink.svg" alt="Delete" width="20" height="20">
              </a>
            `;
          }
          return data;
        },
      },
    ],
  });
}

function displayDebate(dataTable, divToAppend) {
  var all_data = dataTable.ajax.json();
  var debates = all_data.debate;

  if (debates.length < 1) return 0;

  console.log(all_data);

  var uniqueValuesDiv = $('<div class="printIt">');
  var title = $('<h4 class="mt-6">Different Opinions:</h4>');
  uniqueValuesDiv.append(title);
  uniqueValuesDiv.append("<hr />");

  var list = $("<ul>");

  /////////////////////////////////////////
  var table = dataTable.table();

  for (d in debates) {
    var debate = debates[d];

    var id_to_find = debate.instance_id;
    var column_to_find = debate.field_name;

    if (column_to_find == "date_from" || column_to_find == "date_to")
      column_to_find = "date";
    if (
      column_to_find == "where_in_ms_from" ||
      column_to_find == "where_in_ms_to"
    )
      column_to_find = "where";
    if (column_to_find == "size_height" || column_to_find == "size_width")
      column_to_find = "size";

    // Get the column index of the column named `column_to_find`
    var columnIndex = table
      .settings()
      .init()
      .columns.findIndex((col) => col.data === column_to_find);

    // Find the row that has id == id_to_find
    var row = table
      .rows()
      .indexes()
      .filter(function (value, index) {
        return table.row(value).data().id == id_to_find;
      });

    if (row.length > 0) {
      // Get the cell in the row and column specified

      var cell = table.cell(row[0], columnIndex).node();
      var cellData = $(cell).text();

      // Append the desired string to the cell data
      $(cell).html(
        cellData +
          ' <a class="debate-link" href="#debate_' +
          debate.id +
          '" title="' +
          debate.text +
          '">*</a>'
      );

      // Redraw the table to reflect the changes (if necessary)
    }

    //Debate list below
    var list_item = $(
      "<li>" +
        '<div id="debate_' +
        debate.id +
        '">According to: <b>' +
        debate.bibliography +
        "</b>" +
        '  <span style="display: block;">' +
        "      <u>" +
        debate.field_name +
        "</u>" +
        "      is: <b>" +
        debate.text +
        "</b>" +
        "  </span>" +
        "</li><hr />"
    );
    list.append(list_item);
  }
  //////////////////////////////////////////
  /*
    <div>
    <h4 class="printIt" >Different Opinions:</h4>
    <ul>
        <template x-for="(comment) in (await getCodicologyInfo()).debate">
            <div class="printIt" >
                <li>
                    According to:
                    <div x-bind:id="'#debate-'+comment.id"><b x-text="comment.bibliography "></b>,
                    <span style="display: block;">
                        <u x-text="comment.field_name"></u>
                        is: <b  x-text="comment.text "></b>
                    </span>
                </li>
                <!--<a class="debate-link" x-bind:href="'#debate-'+comment.id" x-bind:title="comment.text">*</a>-->
            </div>
        </template>

    </ul>
</div>
*/

  table.draw(false);

  uniqueValuesDiv.append(list);
  $(divToAppend).after(uniqueValuesDiv);
}

function displayComments(dataTable, divToAppend) {
  var all_data = dataTable.ajax.json();
  var data = all_data.data;

  var uniqueValuesDiv = $('<div class="printIt">');
  var title = $('<h4 class="mt-6">Descriptive Details:</h4>');
  uniqueValuesDiv.append(title);
  uniqueValuesDiv.append("<hr />");

  var list = $('<ol class="decoration_comment">');

  /////////////////////////////////////////
  var table = dataTable.table();
  var last_subtype = "";

  table.rows().every(function () {
    var rowData = this.data();
    var authors = "";
    var subtypeText = "";

    if (rowData.decoration_subtype != last_subtype) {
      last_subtype = rowData.decoration_subtype;
      subtypeText = rowData.decoration_subtype + ": ";
    }

    if (rowData.comments.length > 1) {
      if (subtypeText.length > 1) {
        var list_item = $("<li><h4>" + subtypeText + "</h4></li>");
        list.append(list_item);
      }
      var list_item = $(
        '<li class="decoration_comment">' +
          '<div id="decoration_comment_' +
          rowData.id +
          '">' +
          '  <span style="display: block;">' +
          "      <b>" +
          rowData.ornamented_text +
          " </b>" +
          rowData.comments +
          "  </span>" +
          "</li><hr />"
      );
      list.append(list_item);
    }
  });

  table.draw(false);

  uniqueValuesDiv.append(list);
  $(divToAppend).after(uniqueValuesDiv);
}

function displayUniqueAuthorsAndContributors(dataTable, divToAppend) {
  var table = dataTable.table();

  var uniqueAuthors = [];
  var uniqueContributors = [];

  table.rows().every(function () {
    var rowData = this.data();
    var authors = "";
    if (Array.isArray(rowData.authors)) {
      authors = rowData.authors.join(", ");
    }

    if (!uniqueAuthors.includes(authors)) {
      uniqueAuthors.push(authors);
    }
    if (!uniqueContributors.includes(rowData.data_contributor)) {
      uniqueContributors.push(rowData.data_contributor);
    }
  });

  // Render unique values in a div below the table
  var uniqueValuesDiv = $("<div>");
  var authorsString = uniqueAuthors.join(", ");
  var contributorsString = uniqueContributors.join(", ");

  var combinedParagraph =
    '<p class="printIt"><strong>Authors: </strong>' +
    authorsString +
    ". <strong>Data Contributors</strong>: " +
    contributorsString +
    "</p>";
  uniqueValuesDiv.append(combinedParagraph);

  $(divToAppend).after(uniqueValuesDiv);
}

function displayEntryDate(dataTable, divToAppend) {
  var table = dataTable.table();
  var uniqueDates = [];

  table.rows().every(function () {
    var rowData = this.data();
    var date = rowData.entry_date;

    if (!date) return;

    if (!uniqueDates.includes(date)) {
      uniqueDates.push(date);
    }
  });

  // Sort dates (they are in yyyy-mm-dd format, so sorting as text works fine)
  uniqueDates.sort();

  var displayString = "";
  if (uniqueDates.length >= 2) {
    // Get first and last entry if there are 2 or more dates
    var minDate = uniqueDates[0];
    var maxDate = uniqueDates[uniqueDates.length - 1];
    displayString = minDate + " - " + maxDate;
  } else if (uniqueDates.length === 1) {
    // If there's only one date, display that single date
    displayString = uniqueDates[0];
  }

  // Render the result in a div below the table
  var uniqueValuesDiv = $("<div>");
  var combinedParagraph =
    '<p class="printIt"><strong>Entry date:</strong> ' + displayString + "</p>";
  uniqueValuesDiv.append(combinedParagraph);

  $(divToAppend).after(uniqueValuesDiv);
}

function displayScriptsLegend(dataTable, divToAppend) {
  var table = dataTable.table();

  // Render unique values in a div below the table
  var mainDiv = $(
    '<div class="printIt" style="margin-top:0.5em;">' +
      '<div class="medieval-row" style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em;  margin-left: 1em; text-align: middle"></div>' +
      "<i>Medieval</i>" +
      '<div style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em; margin-left: 1em; text-align: middle" class="non-medieval-row"></div>' +
      "<i>Modern</i></div>"
  );

  $(divToAppend).after(mainDiv);
}

function displaOriginalAddedLegend(dataTable, divToAppend) {
  var table = dataTable.table();

  // Render unique values in a div below the table
  var mainDiv = $(
    '<div class="printIt" style="margin-top:0.5em;">' +
      '<div class="medieval-row" style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em;  margin-left: 1em; text-align: middle"></div>' +
      "<i>Original</i>" +
      '<div style="border: 1px solid black; width: 1.1em; height:1.1em; display: inline-block; margin-right:0.5em; margin-left: 1em; text-align: middle" class="non-medieval-row"></div>' +
      "<i>Added</i></div>"
  );

  $(divToAppend).after(mainDiv);
}

function displayTraditionLegend(dataTable, divToAppend) {
  const genreId = $("#genreSelect").val();
  if (!genreId) {
    const allTraditions = Object.keys(traditionColors);
    let html = '<div class="printIt" style="margin-top:0.5em;">';
    allTraditions.forEach((trad) => {
      const tradColor = traditionColors[trad];
      const displayText =
        trad === "Unattributed"
          ? "Unattributed"
          : trad === "Multiple"
          ? "Multiple traditions"
          : trad;
      html += `<div style="display: inline-block; margin-right:0.5em; margin-left:1em; text-align:middle;">
                        <span class="dot" style="background-color: ${tradColor};" title="${displayText}"></span>
                        <i>${displayText}</i>
                     </div>`;
    });
    html += "</div>";

    $(divToAppend).next(".printIt").remove();
    $(divToAppend).after(html);
    return;
  }

  function fetchTraditions(page = 1, accumulatedResults = []) {
    $.ajax({
      url: `${pageRoot}/traditions-autocomplete/?genre=${genreId}&page=${page}`,
      dataType: "json",
      xhrFields: {
        withCredentials: true,
      },
      success: function (response) {
        const results = response.results || [];
        accumulatedResults = accumulatedResults.concat(results);

        if (response.pagination && response.pagination.next) {
          fetchTraditions(page + 1, accumulatedResults);
        } else {
          traditionMap = { Unattributed: "Unattributed" };
          accumulatedResults.forEach((trad) => {
            traditionMap[trad.id] = trad.text;
            if (!traditionColors[trad.text]) {
              traditionColors[trad.text] =
                colorPalette[colorIndex % colorPalette.length];
              colorIndex++;
            }
          });

          const allTraditions = Object.keys(traditionColors);
          let html = '<div class="printIt" style="margin-top:0.5em;">';
          allTraditions.forEach((trad) => {
            const tradColor = traditionColors[trad];
            const displayText =
              trad === "Unattributed"
                ? "Unattributed"
                : trad === "Multiple"
                ? "Multiple traditions"
                : trad;
            html += `<div style="display: inline-block; margin-right:0.5em; margin-left:1em; text-align:middle;">
                                    <span class="dot" style="background-color: ${tradColor};" title="${displayText}"></span>
                                    <i>${displayText}</i>
                                 </div>`;
          });
          html += "</div>";

          $(divToAppend).next(".printIt").remove();
          $(divToAppend).after(html);
        }
      },
      error: function () {
        const allTraditions = Object.keys(traditionColors);
        let html = '<div class="printIt" style="margin-top:0.5em;">';
        allTraditions.forEach((trad) => {
          const tradColor = traditionColors[trad];
          const displayText =
            trad === "Unattributed"
              ? "Unattributed"
              : trad === "Multiple"
              ? "Multiple traditions"
              : trad;
          html += `<div style="display: inline-block; margin-right:0.5em; margin-left:1em; text-align:middle;">
                                <span class="dot" style="background-color: ${tradColor};" title="${displayText}"></span>
                                <i>${displayText}</i>
                             </div>`;
        });
        html += "</div>";

        $(divToAppend).next(".printIt").remove();
        $(divToAppend).after(html);
      },
    });
  }

  fetchTraditions();
}

function printDiv(divId, title) {
  let mywindow = window.open(
    "",
    "PRINT",
    "height=700,width=1200,top=100,left=100"
  );

  mywindow.document.body.innerHTML =
    '<html><head><title>${title}</title><link rel="stylesheet" href="/static/css/printed.css" /></head><body>Loading data... Please be patient...</body></html>';

  let bibliography_promise = getBibliographyPrintableInfo();

  //Open all:
  toggles = $(".toggle");
  for (t in toggles) {
    if (toggles[t].getAttribute && !toggles[t].getAttribute("opened"))
      $(toggles[t]).click();
  }
  //mywindow.document.write(document.getElementById(divId).innerHTML);
  inside_elements = $(".printIt");

  $("#quires").DataTable().page.len(-1).draw();
  $("#main_hands").DataTable().page.len(-1).draw();
  $("#additions_hands").DataTable().page.len(-1).draw();
  $("#layouts").DataTable().page.len(-1).draw();
  $("#bibliography").DataTable().page.len(-1).draw();

  $("#content").DataTable().page.len(-1).draw();
  $("#content").on("draw.dt", async function () {
    //console.log( 'Content table redrawn' );
    mywindow.document.body.innerHTML = "";
    mywindow.document.write(`<html><head><title>${title}</title>`);
    mywindow.document.write(
      '<link rel="stylesheet" href="/static/css/printed.css" /></head><body >'
    );

    for (e in inside_elements) {
      if (inside_elements[e].outerHTML)
        mywindow.document.write(inside_elements[e].outerHTML);
    }

    let bibliography_data = await bibliography_promise;
    mywindow.document.write("<h2>Bibliography</h2>");
    mywindow.document.write(bibliography_data.data);

    mywindow.document.write("</body></html>");

    mywindow.document.close(); // necessary for IE >= 10
    mywindow.focus(); // necessary for IE >= 10*/

    //Close all:
    toggles = $(".toggle");
    for (t in toggles) {
      if (toggles[t].getAttribute && toggles[t].getAttribute("opened"))
        $(toggles[t]).click();
    }

    mywindow.print();
  });

  //mywindow.close();

  return true;
}

let isResizing = false;

function handleResizerMouseMove(e) {
  if (isResizing) {
    const leftColumn = document.getElementById("leftColumn");
    const rightColumn = document.getElementById("rightColumn");
    const resizer = document.getElementById("resizer");

    // How far the mouse has been moved
    const dx = e.clientX - res_mouse_x;

    const newLeftWidth =
      ((leftWidth + dx) * 100) /
      resizer.parentNode.getBoundingClientRect().width;
    if (newLeftWidth < 1) newLeftWidth = 1;

    const containerWidth = leftColumn.offsetWidth + rightColumn.offsetWidth;

    leftColumn.style.width = `${newLeftWidth}%`;
    rightColumn.style.width = `${99 - newLeftWidth}%`;

    // Adjust the position of the resizer
    const resizerPosition = (newLeftWidth / 100) * containerWidth;
    //resizer.style.left = `${resizerPosition}px`;
    resizer.style.left = `${newLeftWidth + 1}%`;
    // $(".mirador1").css('width', `calc(${newLeftWidth}% - .5%)`);
  }
}

function resizeMaxRight() {
  const leftColumn = document.getElementById("leftColumn");
  const rightColumn = document.getElementById("rightColumn");
  const resizer = document.getElementById("resizer");

  newLeftWidth = 1;

  const containerWidth = leftColumn.offsetWidth + rightColumn.offsetWidth;

  leftColumn.style.width = `${newLeftWidth}%`;
  rightColumn.style.width = `${99 - newLeftWidth}%`;

  const resizerPosition = (newLeftWidth / 100) * containerWidth;
  resizer.style.left = `${newLeftWidth + 1}%`;
}

function submitSugestionsForm() {
  const name = document.getElementById("name").value;
  const email = document.getElementById("email").value;
  const message = document.getElementById("message").value;
  const ms_signature = document.getElementById("ms_signature").value;
  const captcha = document.getElementById("captcha").value;
  const captchaKey = document.getElementById("captchaImage").dataset.key;

  fetch("/improve_our_data/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: JSON.stringify({
      name,
      email,
      message,
      ms_signature,
      captcha,
      captcha_key: captchaKey,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.message) {
        alert(data.message);

        if (data.success) {
          document.getElementById("message").value = "";
          document.getElementById("captcha").value = "";
        }
        loadCaptcha();
      }
    })
    .catch(() => {
      document.getElementById("error").textContent =
        "Error submitting form. Please try again.";
    });
}

function loadCaptcha() {
  fetch("/improve_our_data/", {
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken"),
    },
  })
    .then((response) => response.json())
    .then((data) => {
      document.getElementById("captchaImage").src = data.captcha_image;
      document.getElementById("captchaImage").dataset.key = data.captcha_key;
    });
}

async function initSugestionsForm() {
  loadCaptcha();

  document
    .getElementById("refreshCaptcha")
    .addEventListener("click", loadCaptcha);

  document
    .getElementById("contactForm")
    .addEventListener("submit", function (event) {
      event.preventDefault();
      submitSugestionsForm();
    });

  document.getElementById("ms_signature").value = (
    await getMSInfo()
  ).manuscript.name;
}

manuscript_init = function () {
  //RESIZER:
  const leftColumn = document.getElementById("leftColumn");
  const rightColumn = document.getElementById("rightColumn");
  const resizer = document.getElementById("resizer");

  // Event listener for mouse down on the resizer
  resizer.addEventListener("mousedown", function (e) {
    isResizing = true;
    res_mouse_x = e.clientX;
    leftWidth = leftColumn.getBoundingClientRect().width;

    document.addEventListener("mousemove", handleResizerMouseMove);
    document.addEventListener("mouseup", function () {
      isResizing = false;
      document.removeEventListener("mousemove", handleResizerMouseMove);
    });
  });

  //Tooltips:
  /*
    $('a').hover(function(e){
        title = $(this).attr('alt');
        $(this).append('<span>'+title+'</span>')
    },
    function(e){
        $('span', this).remove();
    });
    */

  //Tooltips for debate:
  /*
    document.querySelectorAll('a').forEach(function(element) {
        element.addEventListener('mouseover', function(event) {
            var title = this.getAttribute('alt');
            var span = document.createElement('span');
            span.textContent = title;
            this.appendChild(span);
        });

        element.addEventListener('mouseout', function(event) {
            var span = this.querySelector('span');
            if (span) {
                this.removeChild(span);
            }
        });
    });*/

  // Query the element
  /*
    const resizer = document.getElementById('dragMe');
    const leftSide = resizer.previousElementSibling;
    const rightSide = resizer.nextElementSibling;

    // The current position of mouse
    let x = 0;
    let y = 0;
    let leftWidth = 0;

    // Handle the mousedown event
    // that's triggered when user drags the resizer
    const mouseDownHandler = function (e) {
        // Get the current mouse position
        x = e.clientX;
        y = e.clientY;
        leftWidth = leftSide.getBoundingClientRect().width;

        // Attach the listeners to document
        document.addEventListener('mousemove', mouseMoveHandler);
        document.addEventListener('mouseup', mouseUpHandler);
    };

    const mouseMoveHandler = function (e) {
        // How far the mouse has been moved
        const dx = e.clientX - x;
        const dy = e.clientY - y;

        const newLeftWidth = ((leftWidth + dx) * 100) / resizer.parentNode.getBoundingClientRect().width;
        leftSide.style.width = newLeftWidth + '%';

        resizer.style.cursor = 'col-resize';
        document.body.style.cursor = 'col-resize';

        leftSide.style.userSelect = 'none';
        leftSide.style.pointerEvents = 'none';

        rightSide.style.userSelect = 'none';
        rightSide.style.pointerEvents = 'none';
    };

    const mouseUpHandler = function () {
        resizer.style.removeProperty('cursor');
        document.body.style.removeProperty('cursor');

        leftSide.style.removeProperty('user-select');
        leftSide.style.removeProperty('pointer-events');

        rightSide.style.removeProperty('user-select');
        rightSide.style.removeProperty('pointer-events');

        // Remove the handlers of mousemove and mouseup
        document.removeEventListener('mousemove', mouseMoveHandler);
        document.removeEventListener('mouseup', mouseUpHandler);
    };

    // Attach the handler
    resizer.addEventListener('mousedown', mouseDownHandler);

    */

  $("#genreSelect").select2();

  $("#identifyTraditionsBtn").on("click", function (e) {
    e.preventDefault();
    IDENTIFY_TRADITIONS = true;
    init_content_table(true);
  });

  //For the popup window (add comment):
  const links = document.querySelectorAll('a[data-popup="yes"]');

  links.forEach((link) => {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      const url = this.getAttribute("href");
      const popupWindow = window.open(url, "_blank", "width=700,height=800");
      if (popupWindow) {
        popupWindow.focus();
      } else {
        alert("Please allow pop-ups for this site to open the link.");
      }
    });
  });

  //Replaces _ with " " in field names.
  const fields = document.querySelectorAll("div.field-name");

  fields.forEach((field) => {
    field.textContent = field.textContent.replace(/_/g, " ");
  });

  (async () => {
    const ms_info = await getMSInfo();
    iiif_manifest_url = ms_info.manuscript.iiif_manifest_url;
    manifests = {};
    manifests[iiif_manifest_url] = { provider: "external" };

    //If left column is not needed
    if (
      (!iiif_manifest_url || iiif_manifest_url == "-") &&
      (!ms_info.manuscript.image || ms_info.manuscript.image == "-") &&
      (!ms_info.manuscript.pdf_url || ms_info.manuscript.pdf_url == "-")
    )
      resizeMaxRight();

    mirador_config = {
      id: "my-mirador",
      manifests: manifests,
      /*catalog: [
                {
                    manifestID: iiif_manifest_url
                },
            ],*/
      windows: [
        {
          loadedManifest: iiif_manifest_url,
          canvasIndex: 1,
          thumbnailNavigationPosition: "far-bottom",
        },
      ],
    };

    var miradorInstance = Mirador.viewer(mirador_config);
    window.miradorInstance = miradorInstance;

    window.allCanvasesWithLabels = [];
    function getAllCanvasesWithLabels() {
      if (window.allCanvasesWithLabels.length > 0)
        return window.allCanvasesWithLabels;

      const state = miradorInstance.store.getState();
      const windowId = Object.keys(state.windows)[0]; // Pobierz pierwszy identyfikator okna
      const manifestId = state.windows[windowId].manifestId;

      // Sprawdź, czy manifest jest już załadowany
      if (state.manifests[manifestId]) {
        const manifest = state.manifests[manifestId].json;

        // Sprawdź, czy manifest zawiera elementy
        if (manifest.items && manifest.items.length > 0) {
          const canvases = manifest.items;
          const canvasList = [];

          for (let i = 0; i < canvases.length; i++) {
            const canvas = canvases[i];
            const label = canvas.label;
            canvasList.push({
              index: i,
              id: canvas.id,
              label: label[Object.keys(label)[0]][0],
            });
          }

          window.allCanvasesWithLabels = canvasList;

          return canvasList;
        } else {
          console.error("Manifest does not contain items");
          return [];
        }
      } else {
        console.error("Manifest not loaded yet");
        return [];
      }
    }

    // Przykład użycia
    const canvasList = getAllCanvasesWithLabels();
    console.log(canvasList);

    window.getAllCanvasesWithLabels = getAllCanvasesWithLabels;

    // Funkcja do znalezienia indeksu kanwy na podstawie etykiety
    function findCanvasIndexByLabel(label) {
      const canvases = getAllCanvasesWithLabels();

      for (let i = 0; i < canvases.length; i++) {
        if (canvases[i].label === label) {
          return canvases[i].id;
        }
      }
      return null;
    }
    window.findCanvasIndexByLabel = findCanvasIndexByLabel;

    function goToCanvasById(canvasId) {
      const state = miradorInstance.store.getState();
      const windowId = Object.keys(state.windows)[0]; // Pobierz pierwszy identyfikator okna

      var action = Mirador.actions.setCanvas(windowId, canvasId);
      miradorInstance.store.dispatch(action);
    }

    window.goToCanvasById = goToCanvasById;

    // Funkcja do przełączania się na kanwę na podstawie etykiety
    function goToCanvasByLabel(label) {
      const index = findCanvasIndexByLabel(label);
      if (index !== null) {
        goToCanvasById(index);
      } else {
        console.error(`Canvas with label "${label}" not found`);
      }
    }
    window.goToCanvasByLabel = goToCanvasByLabel;

    // Przykład użyciaj
    // goToCanvasById('my-mirador', 'your-canvas-id'); // Zamień 'your-canvas-id' na właściwy identyfikator kanwy
  })();

  /*var mirador = Mirador({
        id: "mirador",
        data: [
            { manifestUri: iiif_manifest_url, location: "Repository" }
        ]
        });*/

  $("#btnPrint").on("click", function () {
    printDiv("rightColumn", "Liturgica Poloniae");
  });

  initSugestionsForm();
};

async function map_init() {
  //Provenance:
  var southWest = L.latLng(-89.98155760646617, -180),
    northEast = L.latLng(89.99346179538875, 180);
  var bounds = L.latLngBounds(southWest, northEast);

  var osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution:
      '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  });
  map = L.map("map", {
    center: bounds.getCenter(),
    zoom: 2,
    layers: [osm],
    maxBounds: bounds,
    maxBoundsViscosity: 1.0,
  }); //.setView([51.505, -0.09], 5);

  var markers = (await getProvenanceInfo()).markers;

  /*
    map.setMaxBounds(bounds);
    map.on('drag', function() {
        map.panInsideBounds(bounds, { animate: false });
    });
    */
  /*
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);
    */

  allMarkers = [];

  for (m in markers) {
    //var marker = L.marker([markers[m].lat , markers[m].lon ]).addTo(map);

    if (
      !markers[m].lat ||
      !markers[m].lon ||
      markers[m].lat < 0.001 ||
      markers[m].lon < 0.001
    )
      continue;

    var marker = new L.Marker(new L.LatLng(markers[m].lat, markers[m].lon), {
      icon: new L.NumberedDivIcon({ number: Number(m) + 1 }),
      autoPanOnFocus: false,
    });
    marker.addTo(map);

    marker.bindPopup("<b>" + markers[m].name + "</b>", {
      autoPan: false,
    });

    allMarkers.push(marker);

    //Add arrow
    let next_m = parseInt(m) + 1;
    if (next_m < markers.length) {
      if (
        markers[next_m].lat < 0.01 ||
        markers[next_m].lon < 0.01 ||
        !markers[next_m].lat ||
        !markers[next_m].lon
      )
        continue;

      var myVector = L.polyline(
        [
          new L.LatLng(markers[m].lat, markers[m].lon),
          new L.LatLng(markers[next_m].lat, markers[next_m].lon),
        ],
        { color: "darkblue" }
      ).arrowheads({
        fill: true,
        frequency: "endonly",
        //frequency: '100px',
        size: "10px",
        color: "darkblue",
      });
      myVector.addTo(map);
    }
  }

  if (allMarkers.length > 0) {
    var group = new L.featureGroup(allMarkers);
    map_bounds = group.getBounds();
    map.fitBounds(map_bounds, { padding: [50, 50] });

    //map_refresh();
  }
}

var map_refreshed = false;

async function map_refresh() {
  if (map_refreshed) return;

  map.invalidateSize();
  map.fitBounds(map_bounds, { padding: [50, 50] });
  //map.redraw();

  map_refreshed = true;
}
