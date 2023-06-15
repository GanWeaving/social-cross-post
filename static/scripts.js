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
            input.size = 20
            input.name = 'new_name_' + i; // New filename input field
            input.placeholder = 'New filename for ' + files[i].name; // Placeholder text
            div.appendChild(input);

            var altInput = document.createElement('input');
            altInput.type = 'text';
            altInput.name = 'alt_text_' + i;
            altInput.placeholder = 'Alt text for ' + files[i].name;
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
