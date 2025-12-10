
ms_edition_graph_init = function()
{
    /*
    const urlParams = new URLSearchParams(queryString);
    let left = urlParams.get('left');
    let right = urlParams.get('right');
    */

   function setTableHeight() {
        var windowHeight = $(window).height();
        var windowWidth = $(window).width();
        // console.log('height: ', windowWidth);
        if(windowWidth > 640){
            var tableHeight = windowHeight - 400;
        } else {
            var tableHeight = windowHeight - 370;
        }
        
        
        $('#chart').css('height', tableHeight + 'px');
    }
    setTableHeight();

    // Adjust height on window resize
    $(window).resize(function() {
        setTableHeight();
    });

 


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

    $('#ms_select').on('select2:select', function (e) {
        mss = $('#ms_select').select2('data').map(item => item.id).join(';');
        console.log(mss);

        fetchDataAndDrawChart(mss);
    });

    $('#ms_select').on('select2:unselect', function (e) {
        mss = $('#ms_select').select2('data').map(item => item.id).join(';');
        console.log(mss);
        fetchDataAndDrawChart(mss);
    });


    function fetchDataAndDrawChart(mss)
    {

        fetch(pageRoot+"/compare_edition_json/?mss="+mss)
            .then(response => response.json())
            .then(data => createChart(data));
    }

    function getWidth() {
        return Math.max(
          document.body.scrollWidth,
          document.documentElement.scrollWidth,
          document.body.offsetWidth,
          document.documentElement.offsetWidth,
          document.documentElement.clientWidth
        );
      }
      
      function getHeight() {
        return Math.max(
          document.body.scrollHeight,
          document.documentElement.scrollHeight,
          document.body.offsetHeight,
          document.documentElement.offsetHeight,
          document.documentElement.clientHeight
        );
      }

    

    function createChart(data) 
    {
        let chartHeight = $('#chart').height();
        const margin = { top: 20, right: 30, bottom: 40, left: 250 },
        width = getWidth() - margin.left - margin.right - 50,
        height = chartHeight - margin.top - margin.bottom;
    
        $("#chart").empty();
    
        const svg = d3.select("#chart").append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);
    
        const x = d3.scaleLinear().range([0, width]);
        const y = d3.scalePoint().range([0, height]).padding(0.2);
    
        const editionIndexes = [...new Set(data.map(d => d.edition_index))];
        y.domain(data.map(d => d.Table));
        x.domain(d3.extent(data, d => d.rubric_sequence));
    
        const color = d3.scaleOrdinal(d3.schemeCategory10).domain(editionIndexes);
    
        const line = d3.line()
                        .x(d => x(d.rubric_sequence))
                        .y(d => y(d.Table));
    
        svg.append("g").attr("class", "x axis")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x));
    
        svg.append("g").attr("class", "y axis")
            .call(d3.axisLeft(y));
    
        const tooltip = d3.select("body").append("div")
            .attr("class", "tooltip")
            .style("opacity", 0);
    
        // Funkcja do obsługi kliknięć na liniach
        function handleClickOnLine(values, edition_index) {
            if (selectedLine) {
                selectedLine.classed("selected-line", false);
                selectedCircles.classed("selected-circle", false);
            }
    
            // Zaznacz linię i przenieś na wierzch
            selectedLine = d3.select(this).classed("selected-line", true).raise();
    
            // Zaznacz kropki powiązane z tą linią
            selectedCircles = svg.selectAll('circle')
                .filter(d => d.edition_index === edition_index)
                .classed("selected-circle", true)
                .raise();
        }
    
        // Przechowuj zaznaczone linie i kropki
        let selectedLine;
        let selectedCircles;
    
        editionIndexes.forEach(edition_index => {
            const values = data.filter(d => d.edition_index === edition_index);
            
            svg.append("path")
                .datum(values)
                .attr("fill", "none")
                .attr("stroke", color(edition_index))
                .attr("stroke-width", 3)  // Ustaw grubość linii na 3
                .attr("d", line)
                .attr("class", "data-line")
                .on("mouseover", function(event) {
                    tooltip.transition()
                        .duration(200)
                        .style("opacity", .9);
                    tooltip.html(`Edition: ${edition_index}<br>${values[0].rubric_name_standarized}`)
                        .style("left", `${event.pageX + 5}px`)
                        .style("top", `${event.pageY - 28}px`);
                })
                .on("mouseout", function() {
                    tooltip.transition()
                        .duration(500)
                        .style("opacity", 0);
                })
                .on("click", function() { handleClickOnLine.call(this, values, edition_index); });  // Obsługa kliknięcia
    
            const midpointIndex = Math.floor(values.length / 2);
            const midpoint = values[midpointIndex];
    
            /*
            svg.append("text")
                .attr("class", "line-label")
                .attr("x", x(midpoint.rubric_sequence))
                .attr("y", y(midpoint.Table) + 10)
                .attr("transform", `rotate(90, ${x(midpoint.rubric_sequence)}, ${y(midpoint.Table) + 10})`)
                .text(edition_index);
            */
            svg.selectAll("dot")
                .data(values)
                .enter().append("circle")
                .attr("r", 7)  // Ustaw promień kropki na 7
                .attr("cx", d => x(d.rubric_sequence))
                .attr("cy", d => y(d.Table))
                .attr("fill", color(edition_index))
                .on("mouseover", function(event, d) {
                    tooltip.transition()
                        .duration(200)
                        .style("opacity", .9);
                    tooltip.html(`Edition: ${d.edition_index}<br>Rubric: ${d.rubric_sequence}<br>${d.rubric_name_standarized}`)
                        .style("left", `${event.pageX + 5}px`)
                        .style("top", `${event.pageY - 28}px`);
                })
                .on("mouseout", function() {
                    tooltip.transition()
                        .duration(500)
                        .style("opacity", 0);
                })
                .on("click", function(event, d) { handleClickOnLine.call(this, values, edition_index); });  // Obsługa kliknięcia
    
        });
    
        // Funkcjonalność zoomu na osi X
        function handleZoom(e) {
            // Rescale the x-axis based on zoom level
            const new_x = e.transform.rescaleX(x);
        
            // Update the x-axis, but keep the y-axis untouched
            svg.select(".x.axis").call(d3.axisBottom(new_x));
        
            // Update only the x position of circles, no scaling for size or y-axis
            svg.selectAll('circle')
                .attr('cx', d => new_x(d.rubric_sequence));  // Update x position only
        

            // Update the paths (lines) with the new x-scale, ensure proper data binding
            svg.selectAll('path.data-line')  // Select paths associated with data lines
                .attr('d', d => line
                    .x(d => new_x(d.rubric_sequence))  // Update the x position using new_x
                    .y(d => y(d.Table))(d));  // Keep the y position the same
        }
        
        
        
        let zoom = d3.zoom()
        .on('zoom', handleZoom);
        
        d3.select('svg')
        .call(zoom);
    }
    
}
