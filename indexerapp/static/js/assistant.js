// Modified assistant.js with DEBUG, progress, scroll, and time display

function assistant_init() {
    console.log('assistant');
    setTableHeight();
}

function setTableHeight() {
    var windowHeight = $(window).height();
    var windowWidth = $(window).width();
    if (windowWidth > 640) {
        var tableHeight = windowHeight - 500;
    } else {
        var tableHeight = windowHeight - 470;
    }
    $('#assistant_content').css('height', tableHeight + 'px');
}

$(window).resize(function() {
    setTableHeight();
});

const DEBUG = false; // Set to false for production

var pollInterval;
var isUnfolded = false;

function toggleConversation() {
    var convContent = document.getElementById('convContent');
    var toggleBtn = document.getElementById('toggleConv');
    if (isUnfolded) {
        convContent.style.display = 'none';
        toggleBtn.innerText = '(Unfold)';
        isUnfolded = false;
    } else {
        convContent.style.display = 'block';
        toggleBtn.innerText = '(Fold)';
        isUnfolded = true;
    }
}

function askQuestion() {
    setTableHeight();
    var questionInput = document.getElementById('question');
    var question = questionInput.value.trim();

    if (question === '') {
        alert('Please enter a question.');
        return;
    }

    var loader = document.getElementById('loader');
    var answerDiv = document.getElementById('answer');
    var errorDiv = document.getElementById('error');
    var convDiv = document.getElementById('conversation');
    var convContent = document.getElementById('convContent');

    loader.style.display = 'block';
    answerDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    convDiv.style.display = 'none';
    convContent.innerHTML = '';

    $.ajax({
        type: 'GET',
        url: pageRoot + '/assistant/start/?project_id=' + projectId + '&q=' + encodeURIComponent(question),
        success: function(data) {
            if (data.query_id) {
                startPolling(data.query_id);
            } else {
                loader.style.display = 'none';
                alert('Error starting query.');
            }
        },
        error: function() {
            loader.style.display = 'none';
            alert('Error fetching data. Check if you are logged in! Only logged users are allowed to use AI assistant. You should have OpenAI API Key set in you user preferences');
        },
        xhrFields: {
            withCredentials: true
        }
    });
}

function startPolling(queryId) {
    var loader = document.getElementById('loader');
    loader.innerHTML = 'Analyzing query...';
    pollInterval = setInterval(function() {
        $.ajax({
            type: 'GET',
            url: pageRoot + '/assistant/status/' + queryId + '/',
            success: function(data) {
                console.log('Status data:', data);  // Debug log
                try {
                    updateUI(data);
                } catch (e) {
                    console.error('Error in updateUI:', e);
                }
                if (data.status === 'completed' || data.status === 'error') {
                    clearInterval(pollInterval);
                    loader.style.display = 'none';
                }
            },
            error: function() {
                clearInterval(pollInterval);
                loader.style.display = 'none';
                alert('Error polling status.');
            },
            xhrFields: {
                withCredentials: true
            }
        });
    }, 1000);
}

function updateProgress(step) {
    const progressMessages = [
        'Analyzing query...',
        'Gathering database information.',
        'Analyzing results...',
        'Querying the database...',
        'Analyzing results...',
        'Querying the database...',
        'Final database query - attempt 1'
    ];
    var loader = document.getElementById('loader');
    loader.innerHTML = progressMessages[step % progressMessages.length] || 'Processing...';
    loader.style.display = 'block';
}

function updateUI(data) {
    var convDiv = document.getElementById('conversation');
    var convContent = document.getElementById('convContent');
    var answerDiv = document.getElementById('answer');
    var errorDiv = document.getElementById('error');
    var toggleBtn = document.getElementById('toggleConv');
    var loader = document.getElementById('loader');

    if (data.messages && data.messages.length > 0) {
        if (DEBUG) {
            convDiv.style.display = 'block';
            var convHtml = '';
            data.messages.forEach(function(msg) {
                convHtml += '<div><strong>' + msg.role + ':</strong> <pre>' + escapeHtml(msg.content) + '</pre></div>';
            });
            convContent.innerHTML = convHtml;
            convContent.scrollTop = convContent.scrollHeight;  // Scroll to bottom
            if (data.status === 'completed') {
                convContent.style.display = 'none';
                toggleBtn.innerText = '(Unfold)';
                isUnfolded = false;
            } else {
                convContent.style.display = 'block';
                toggleBtn.innerText = '(Fold)';
                isUnfolded = true;
            }
        } else {
            convDiv.style.display = 'none';
            if (data.status !== 'completed' && data.status !== 'error') {
                updateProgress(data.messages.length);
            } else {
                loader.style.display = 'none';
            }
        }
    }

    if (data.error) {
        errorDiv.innerHTML = '<h2>Error:</h2><p>' + escapeHtml(data.error) + '</p>';
    }

    if (data.status === 'completed' && data.result) {
        var resultHtml = '<h2>Answer:</h2>';
        data.result.forEach(function(res, index) {
            if (res.comment) {
                resultHtml += '<p>' + escapeHtml(res.comment.replace('--', '')) + '</p>';
            }
            if (res.result && res.result.columns && res.result.rows) {
                // Filter out empty columns if more than 5 columns
                var columns = res.result.columns;
                var rows = res.result.rows;
                var numColumns = columns.length;
                var filteredColumns = [];
                var columnIndices = [];

                if (numColumns > 5) {
                    for (var colIndex = 0; colIndex < numColumns; colIndex++) {
                        var isEmpty = true;
                        for (var rowIndex = 0; rowIndex < rows.length; rowIndex++) {
                            var cell = rows[rowIndex][colIndex];
                            if (cell !== null && cell !== undefined && cell.toString().trim() !== '') {
                                isEmpty = false;
                                break;
                            }
                        }
                        if (!isEmpty) {
                            filteredColumns.push(columns[colIndex]);
                            columnIndices.push(colIndex);
                        }
                    }
                } else {
                    filteredColumns = columns;
                    columnIndices = columns.map((_, idx) => idx);
                }

                resultHtml += '<table id="dataTable' + index + '"><thead><tr>';
                filteredColumns.forEach(function(col) {
                    resultHtml += '<th>' + escapeHtml(col) + '</th>';
                });
                resultHtml += '</tr></thead><tbody>';
                res.result.rows.forEach(function(row) {
                    resultHtml += '<tr>';
                    columnIndices.forEach(function(colIndex) {
                        var cell = row[colIndex];
                        resultHtml += '<td>' + escapeHtml(cell !== null ? cell.toString() : 'NULL') + '</td>';
                    });
                    resultHtml += '</tr>';
                });
                resultHtml += '</tbody></table><br>';
            } else if (res.result && res.result.affected_rows !== undefined) {
                resultHtml += '<p>Affected rows: ' + res.result.affected_rows + '</p>';
            }
        });
        if (data.execution_time) {
            resultHtml += '<p>Query took ' + data.execution_time.toFixed(2) + ' seconds.</p>';
        }
        answerDiv.innerHTML = resultHtml;
        data.result.forEach(function(res, index) {
            if (res.result && res.result.columns) {
                try {
                    $('#dataTable' + index).DataTable();
                } catch (e) {
                    console.error('DataTable init error:', e);
                }
            }
        });
    } else if (data.status === 'completed') {
        var noDataHtml = '<h2>Answer:</h2><p>No data available</p>';
        if (data.execution_time) {
            noDataHtml += '<p>Query took ' + data.execution_time.toFixed(2) + ' seconds.</p>';
        }
        answerDiv.innerHTML = noDataHtml;
    }
}

function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) {
        return 'NULL';
    }
    return unsafe.toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}