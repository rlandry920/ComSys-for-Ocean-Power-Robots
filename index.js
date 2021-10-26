$(document).ready(function () {
    addMesssage("Log:", "b")
    $("#move").click(function () {
        var lat_dir = document.querySelector('input[name="latitude_dir"]:checked').value[0];
        var long_dir = document.querySelector('input[name="longitude_dir"]:checked').value[0];

        var data = [
            {
                "lat_py": $("#lat").val() + lat_dir,
                "long_py": $("#long").val() + long_dir
            }
        ];
        $.ajax({
            type: 'POST',
            url: "http://127.0.0.1:5000/move",
            data: JSON.stringify(data),
            contentType: "application/json",
            dataType: "text",
            success: function (response) {
                addMesssage(response, "r")
            }

        });
        addMesssage("Move command sent", "s")
    });

    function addMesssage(messageString, messageType) {
        if (messageType == "r") {
            var $p = $('<p style="color:red;"></p>');
        }
        else if (messageType == "b") {
            var $p = $('<p style="color:black;"></p>');
        }
        else {
            var $p = $('<p style="color:blue;"></p>');
        }
        $p.text(messageString)
        $("#message-box").append($p)
        $("#message-box").scrollTop($("#message-box")[0].scrollHeight);
    }
});
