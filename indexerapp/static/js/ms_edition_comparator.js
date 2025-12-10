
async function getAndShowSimilarMSbyEditionIndex(id,name)
{
    $('#results').empty();
    $('#results').append('<h3>Loading...</h3>');


    var info = (await getSimilarMSbyEditionIndex(id));
    $('#results').empty();
    $('#results').append('<div id="chart"></div>');

    var ms_content = info.ms_content;
    var similar_ms = info.similar_ms;
    //convert to array:
    similar_ms = Object.values(similar_ms);


    var ms_content_count = ms_content.length;


    similar_ms.sort((a, b) => {
        const contentSimilarityA = (a.identical_edition_index_count / ms_content_count) * 100.0;
        const contentSimilarityB = (b.identical_edition_index_count / ms_content_count) * 100.0;
        return contentSimilarityB - contentSimilarityA;
    });

    createChart(similar_ms, ms_content_count);

    var ms_content_div = $('<div class="ms_content">');
    ms_content_div.append('<h2 class="content_header">'+name+'</h2>');

    var manuscript_description = $('<table class="manuscript_description result_table">');

    var ms_content_span = '';
    for(c in ms_content)
    {
        ms_content_span += ' <span class="ms_content_span"> '+c+": "+ms_content[c]+', </span>';
    }

    manuscript_description.append('<tr><td class="firsttd">Content:</td><td>'+ms_content_span+'</td><tr>');

    ms_content_div.append(manuscript_description);
    $('#results').append(ms_content_div);

    for(ms in similar_ms)
    {
        var manuscript = similar_ms[ms];

        var manuscript_div = $('<div class="similar_ms">');

        var manuscript_name = manuscript.manuscript_name;
        var manuscript_name_el =  $('<h2 class="content_header">'+manuscript_name+'</h2>');
        manuscript_div.append(manuscript_name_el);

        var manuscript_description = $('<table class="manuscript_description">');

        var content_similarity = ( manuscript.identical_edition_index_count / ms_content_count)*100.0;
        var sequence_similarity = ( manuscript.identical_edition_index_on_same_sequence_count / ms_content_count)*100.0;
        manuscript_description.append('<tr><td class="firsttd" class="firsttd">Content similarity:</td><td>'+Math.round(content_similarity * 100) / 100+'%</td><tr>');
        manuscript_description.append('<tr><td class="firsttd">Sequence similarity:</td><td>'+Math.round(sequence_similarity * 100) / 100+'%</td><tr>');

        manuscript_description.append('<tr><td class="firsttd">Number of rubrics in the manuscript:</td><td>'+manuscript.total_edition_index_count+'</td><tr>');
        
        manuscript_description.append('<tr><td class="firsttd">How many rubrics are the same:</td><td>'+manuscript.identical_edition_index_count+'</td><tr>');
        manuscript_description.append('<tr><td class="firsttd">How many rubrics are the same (and have the same sequence):</td><td>'+manuscript.identical_edition_index_on_same_sequence_count+'</td><tr>');
        manuscript_description.append('<tr><td class="firsttd">A list of the same rubrics:</td><td>'+manuscript.identical_edition_index_list+'</td><tr>');
        manuscript_description.append('<tr><td class="firsttd">Other rubrics included in the manuscript:</td><td>'+manuscript.edition_index_list+'</td><tr>');

        manuscript_div.append(manuscript_description);

        $('#results').append(manuscript_div);
    }

}

function setTableHeight() {
    var windowHeight = $(window).height();
    var windowWidth = $(window).width();
    // console.log('height: ', windowWidth);
    if(windowWidth > 640){
        var tableHeight = windowHeight - 400;
    } else {
        var tableHeight = windowHeight - 370;
    }
    
    
    $('#results').css('height', tableHeight + 'px');
}

function createChart(data, ms_content_count) {
    // Remove the existing SVG element if it exists
    d3.select("#chart").select("svg").remove();

    // Set up dimensions and margins with a larger left margin
    const margin = { top: 20, right: 30, bottom: 40, left: 450 }, // Increased left margin
          width = 1024 - margin.left - margin.right, 
          height = 500 - margin.top - margin.bottom;

    // Create the SVG container
    const svg = d3.select("#chart").append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    // Calculate content similarity for each manuscript
    data.forEach(manuscript => {
        manuscript.content_similarity = (manuscript.identical_edition_index_count / ms_content_count) * 100.0;
    });

    // Set up the X and Y scales
    const x = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.content_similarity)])
        .range([0, width]);

    const y = d3.scaleBand()
        .domain(data.map(d => d.manuscript_name))
        .range([0, height])
        .padding(0.1);

    // Add the X axis
    svg.append("g")
        .attr("transform", `translate(0,${height})`)
        .call(d3.axisBottom(x))
        .selectAll("text")
        .attr("transform", "translate(-10,0)rotate(-45)")
        .style("text-anchor", "end");

    // Add the Y axis
    svg.append("g")
        .call(d3.axisLeft(y));

    // Create bars
    svg.selectAll("rect")
        .data(data)
        .enter()
        .append("rect")
        .attr("x", x(0))
        .attr("y", d => y(d.manuscript_name))
        .attr("width", d => x(d.content_similarity))
        .attr("height", y.bandwidth())
        .attr("fill", "#997A62");
}



$(document).ready(function() {
    console.log('document ready function');
    setTimeout(function() {
        setTableHeight();
    }, 700);  // A small delay ensures elements are fully rendered
});

$(window).on('load', function() {
    console.log('window load function');
    setTableHeight();
});

// Adjust height on window resize
$(window).resize(function() {
    setTableHeight();
});


async function getSimilarMSbyEditionIndex(id) 
{
    return fetchOnce(pageRoot+`/rites_lookup/?ms=${id}`);
}

content_init = function()
{
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

        getAndShowSimilarMSbyEditionIndex(id, data.text);
    });

}
