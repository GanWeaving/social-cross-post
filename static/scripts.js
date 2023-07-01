window.onload = function() {
    document.getElementById('files').onchange = function(){
        var fileList = document.getElementById('fileList');
        fileList.innerHTML = '';
        var files = document.getElementById('files').files;

        if (files.length > 0) {
            for (var i = 0; i < files.length; i++) {
                var div = document.createElement('div');
                div.className = 'file-row';

                var img = document.createElement('img');
                img.classList.add('thumbnail');
                img.file = files[i];
                div.appendChild(img);

                var label = document.createElement('label');   // Create a new 'label' HTML element
                label.textContent = "Order position: ";        // Set its text content
                div.appendChild(label);                        // Append it to the div
                
                var dropdown = document.createElement('select');
                dropdown.name = 'new_name_' + i;
                
                for (var j = 1; j <= files.length; j++) {
                    var option = document.createElement('option');
                    option.value = j;
                    option.text = j;
                    if (j === (i+1)) { // Select the current index
                        option.selected = true;
                    }
                    dropdown.appendChild(option);
                }
                
                // Append dropdown after the label
                div.appendChild(dropdown);

                // Hidden input to store the original extension
                var extInput = document.createElement('input');
                extInput.type = 'hidden';
                extInput.name = 'original_ext_' + i;
                // Get the extension from the original filename
                extInput.value = files[i].name.split('.').pop();
                div.appendChild(extInput);

                div.appendChild(dropdown);

                var altInput = document.createElement('textarea');
                altInput.name = 'alt_text_' + i;
                altInput.placeholder = 'enter alt text here';
                altInput.style.resize = "none";
                altInput.style.overflow = "hidden";
                altInput.style.width = "100%";
                altInput.onkeyup = function() {
                    this.style.height = "auto";
                    this.style.height = (this.scrollHeight) + "px";
                };
                div.appendChild(altInput);

                fileList.appendChild(div);

                // Read the image file as a data URL and display it
                var reader = new FileReader();
                reader.onload = (function(aImg) {
                    return function(e) {
                        aImg.src = e.target.result;
                    };
                })(img);
                reader.readAsDataURL(files[i]);
            }
        }
    }
}

function disableSubmitButton() {
    var submitButton = document.getElementById('submitButton');
    submitButton.disabled = true;
    submitButton.value = 'Submitting...';
}

function updateCharacterCount() {
    var textarea = document.getElementById('text');
    var hashtagField = document.getElementById('txt_hashtags');
    var hashtagCheckbox = document.getElementById('hashtagCheckbox');
    var characterCount = textarea.value.length;
    if (hashtagCheckbox.checked) {
        characterCount += hashtagField.value.length;
    }
    var counter = document.getElementById('characterCount');
    counter.textContent = characterCount;

    // Check if the character count exceeds the limit
    if (characterCount > 240) {
        // Display a warning
        document.getElementById('warningMessage').style.display = 'block';
    } else {
        // Hide the warning
        document.getElementById('warningMessage').style.display = 'none';
    }
}

function validateFileNames(event) {
    var dropdowns = document.querySelectorAll("select[name^='new_name_']");
    var values = new Set();
    var hasDuplicate = false;

    dropdowns.forEach(function (dropdown) {
        var value = dropdown.value;
        if (values.has(value)) {
            hasDuplicate = true;
        } else {
            values.add(value);
        }
    });

    if (hasDuplicate) {
        var errorMessage = document.getElementById("errorMessage");
        errorMessage.style.display = "block";
        errorMessage.innerText = 'Order positions must be unique!';
        event.preventDefault();  // stop form submission
    }
}


function validateCheckboxes(event) {
    let checkboxes = document.querySelectorAll("input[type='checkbox']:not(#hashtagCheckbox)");
    let isChecked = Array.from(checkboxes).some(checkbox => checkbox.checked);
    let errorMessage = document.getElementById("errorMessage");

    if (!isChecked) {
        errorMessage.style.display = "block";
        errorMessage.innerText = 'You need to select at least one site';
        event.preventDefault();  // stop form submission
    } else {
        errorMessage.style.display = "none";
        disableSubmitButton();  // Button is disabled only if the validation has passed
    }
}


function hideErrorMessage() {
    let errorMessage = document.getElementById("errorMessage");
    errorMessage.style.display = "none";
}