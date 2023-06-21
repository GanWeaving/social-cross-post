window.onload = function() {
    document.getElementById('files').onchange = function(){
        var fileList = document.getElementById('fileList');
        fileList.innerHTML = '';
        var files = document.getElementById('files').files;
        for (var i = 0; i < files.length; i++) {
            var div = document.createElement('div');
            div.className = 'file-row';

            var img = document.createElement('img');
            img.classList.add('thumbnail');
            img.file = files[i]
            div.appendChild(img);

            var text = document.createTextNode(files[i].name);
            div.appendChild(text);

            var input = document.createElement('input');
            input.type = 'text';
            input.name = 'new_name_' + i; // New filename input field
            input.placeholder = 'New filename for ' + files[i].name; // Placeholder text
            input.style.width = '25%';  // Set width to 50% of the parent width
            div.appendChild(input);
            

            var altInput = document.createElement('textarea');
            altInput.name = 'alt_text_' + i;
            //altInput.placeholder = 'Alt text for ' + files[i].name;
            altInput.placeholder = 'enter alt text here' 
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