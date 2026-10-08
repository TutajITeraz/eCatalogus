user_init = function()
{
    console.log('assistant');
    fetchAiApiKey();

    function setTableHeight() {
        var windowHeight = $(window).height();
        var windowWidth = $(window).width();
        // console.log('height: ', windowWidth);
        if(windowWidth > 640){
            var tableHeight = windowHeight - 250;
        } else {
            var tableHeight = windowHeight - 220;
        }
        
        
        $('#user').css('height', tableHeight + 'px');
    }
    setTableHeight();

    // Adjust height on window resize
    $(window).resize(function() {
        setTableHeight();
    });

}



function fetchAiApiKey() {
    var xhr = new XMLHttpRequest();
    xhr.withCredentials = true;
    xhr.open('GET', pageRoot + '/get_api_key/', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));

    xhr.onload = function() {
        var response = JSON.parse(xhr.responseText);
        if (response.success) {
            document.getElementById('ai_api_key').value = response.api_key;
        } else {
            console.error(response.error);
        }
    };
    xhr.send();
}

function saveAiApiKey() {
    var apiKey = document.getElementById('ai_api_key').value;
    var xhr = new XMLHttpRequest();
    xhr.withCredentials = true;
    xhr.open('POST', pageRoot + '/set_api_key/', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));

    xhr.onload = function() {
        var response = JSON.parse(xhr.responseText);
        if (response.success) {
            alert('API key saved successfully!');
        } else {
            console.error(response.error);
        }
    };
    xhr.send('api_key=' + encodeURIComponent(apiKey));
}


function changePassword() {
    var newPassword = document.getElementById('new_password').value;
    var confirmNewPassword = document.getElementById('confirm_new_password').value;
    var errorElement = document.getElementById('error');
    errorElement.textContent = '';

    if (newPassword !== confirmNewPassword) {
        errorElement.textContent = 'New passwords do not match.';
        return;
    }

    var passwordRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{10,}$/;
    if (!passwordRegex.test(newPassword)) {
        errorElement.textContent = 'Password must be at least 10 characters long, contain both uppercase and lowercase letters, and at least one number.';
        return;
    }

    var xhr = new XMLHttpRequest();
    xhr.withCredentials = true;
    xhr.open('POST', pageRoot + '/ajax_change_password/', true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));

    xhr.onload = function() {
        var response = JSON.parse(xhr.responseText);
        if (response.success) {
            window.location.href = '/';
        } else {
            errorElement.textContent = response.error;
        }
    };
    xhr.send('new_password=' + newPassword);
}

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Instances name the CSRF cookie '<instance>_csrftoken', so 'csrftoken' matches either form.
            var eq = cookie.indexOf('=');
            var cookieName = cookie.substring(0, eq);
            if (cookieName === name || (name === 'csrftoken' && cookieName.endsWith('_csrftoken'))) {
                cookieValue = decodeURIComponent(cookie.substring(eq + 1));
                break;
            }
        }
    }
    return cookieValue;
}