var currLocation = { lat: 37.2284, lng: -80.4234 };
var moveToLocation = { lat: 37.2284, lng: -80.4234 };
var markerShown = false;

var map, currLocationMarker, goToMarker;
var images = ["reindeer1.PNG", "reindeer2.PNG", "reindeer3.PNG", "reindeer4.PNG", "reindeer5.PNG", "reindeer6.PNG", "reindeer7.PNG", "reindeer8.PNG", "reindeer9.PNG"];
var i = 0;
var renew = setInterval(function () {
    if (images.length == i) {
        i = 0;
    }
    else {
        document.getElementById("robot_image").src = images[i];
        i++;

    }
}, 1000);

$(document).ready(function () {
    var pressedKey = -1;
    addMesssage("Log:", "b")
    initMap();
    $("#move").click(function () {
        var lat_dir = document.querySelector('input[name="latitude_dir"]:checked').value[0];
        var long_dir = document.querySelector('input[name="longitude_dir"]:checked').value[0];
        sendGoToCommand($("#lat").val(), $("#long").val(), lat_dir, long_dir)
        addMesssage("Coordinates sent", "s")
        if (!isNaN($("#lat").val()) && $("#lat").val() != "") {
            currLocation.lat = parseFloat($("#lat").val());
            if (lat_dir == "S") {
                currLocation.lat = -currLocation.lat
            }
        }
        if (!isNaN($("#long").val()) && $("#long").val() != "") {
            currLocation.lng = parseFloat($("#long").val());
            if (long_dir == "W") {
                currLocation.lng = -currLocation.lng
            }
        }
        $("#lat").val("")
        $("#long").val("")
    });

    $("#left").mousedown(function () {
        sendMoveCommand("turnLeft")
        addMesssage("Turn left command sent", "s")
    });

    $("#right").mousedown(function () {
        sendMoveCommand("turnRight")

        addMesssage("Turn right command sent", "s")
    });

    $("#forward").mousedown(function () {
        sendMoveCommand("moveForward")
        addMesssage("Move forward command sent", "s")
    });

    $("#backward").mousedown(function () {
        sendMoveCommand("moveBackward")
        addMesssage("Move backward command sent", "s")
    });

    $(document).keydown(function (event) {
        if (pressedKey == -1) {
            var key = event.keyCode;

            if (key == 39) {
                sendMoveCommand("turnRight")
                addMesssage("Turn right command sent", "s")
                pressedKey = 39
            }
            else if (key == 37) {
                sendMoveCommand("turnLeft")
                addMesssage("Turn left command sent", "s")
                pressedKey = 37
            }
            else if (key == 38) {
                sendMoveCommand("moveForward")
                addMesssage("Move forward command sent", "s")
                pressedKey = 37
            }
            else if (key == 40) {
                sendMoveCommand("moveBackward")
                addMesssage("Move backward command sent", "s")
                pressedKey = 37
            }
        }
        event.preventDefault();
    });

    $(document).keyup(function (event) {
        var key = event.keyCode;

        if (key == 39) {
            sendMoveCommand("stopTurnRight")
            addMesssage("Stop turning right command sent", "s")
            pressedKey = -1
        }
        else if (key == 37) {
            sendMoveCommand("stopTurnLeft")
            addMesssage("Stop turning left command sent", "s")
            pressedKey = -1
        }
        else if (key == 38) {
            sendMoveCommand("stopMoveForward")
            addMesssage("Stop moving forward command sent", "s")
            pressedKey = -1
        }
        else if (key == 40) {
            sendMoveCommand("stopMoveBackward")
            addMesssage("Stop moving backward command sent", "s")
            pressedKey = -1
        }
        event.preventDefault();
    });


    $("#refresh_map").mousedown(function () {
        updateBoatMarker();
    });

    $("#delete_marker").hide();

    $("#delete_marker").mousedown(function () {
        deleteMarker();
    });

    google.maps.event.addListener(map, 'click', function (event) {
        placeMarker(event.latLng);
    });
});

function deleteMarker() {
    goToMarker.setVisible(false);
    var bounds = new google.maps.LatLngBounds();
    bounds.extend(currLocation);
    map.fitBounds(bounds);
    if (map.getZoom() > 15) {
        map.setZoom(15);
    }
    $("#lat").val("")
    $("#long").val("")
    $("#delete_marker").hide();
}

function placeMarker(location) {

    goToMarker.setPosition(location)

    var goToLat = goToMarker.getPosition().lat().toFixed(6)
    if (goToLat < 0) {
        goToLat = -goToLat
        $('input:radio[name=latitude_dir]')[1].checked = true;
    } else {
        $('input:radio[name=latitude_dir]')[0].checked = true;
    }
    $("#lat").val(goToLat.toString())

    var goToLong = goToMarker.getPosition().lng().toFixed(6)
    if (goToLong < 0) {
        goToLong = -goToLong
        $('input:radio[name=longitude_dir]')[1].checked = true;
    }
    else {
        $('input:radio[name=longitude_dir]')[0].checked = true;

    }
    $("#long").val(goToLong.toString())

    $("#delete_marker").show();
    goToMarker.setVisible(true);

    var bounds = new google.maps.LatLngBounds();
    bounds.extend(location);
    bounds.extend(currLocation);
    if (map.getZoom() > 15) {
        map.setZoom(15);
    }
    map.fitBounds(bounds);
}

function sendGoToCommand(lat, long, lat_dir, long_dir) {
    var data = [
        {
            "lat_py": lat + lat_dir,
            "long_py": long + long_dir
        }
    ];
    $.ajax({
        type: 'POST',
        url: "http://192.168.43.226:5000/goToCoordinates",
        data: JSON.stringify(data),
        contentType: "application/json",
        dataType: "text",
        success: function (response) {
            addMesssage(response, "r")
        }

    });
}

function sendMoveCommand(command) {
    $.ajax({
        type: 'POST',
        url: "http://10.0.0.243:5000/" + command,
        contentType: "application/json",
        dataType: "text",
        success: function (response) {
            addMesssage(response, "r")
        }
    });
}

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

// Initialize and add the map
function initMap() {
    // The location of Virginia Tech
    map = new google.maps.Map(document.getElementById("map"), {
        zoom: 15,
        center: currLocation,
        streetViewControl: false,
    });
    const image = "boat_marker.png"
    // The marker, positioned at Uluru
    currLocationMarker = new google.maps.Marker({
        position: currLocation,
        map: map,
        icon: image
    });

    // The marker, positioned at Uluru
    goToMarker = new google.maps.Marker({
        position: moveToLocation,
        map: map,
        visible: false,
    });

    updateCurrentLocation()
}

function updateBoatMarker() {
    currLocationMarker.setPosition(currLocation)
    deleteMarker();
    var bounds = new google.maps.LatLngBounds();
    bounds.extend(goToMarker.position);
    bounds.extend(currLocationMarker.position);
    map.fitBounds(bounds);
    if (map.getZoom() > 15) {
        map.setZoom(15);
    }

    updateCurrentLocation()
}

function updateCurrentLocation() {
    if (currLocation.lat < 0) {
        $("#curr_lat").text("Current latitude: " + currLocation.lat.toString().substring(1) + " S")
    } else {
        $("#curr_lat").text("Current latitude: " + currLocation.lat.toString() + " N")
    }
    if (currLocation.lng < 0) {
        $("#curr_long").text("Current longitude: " + currLocation.lng.toString().substring(1) + " W")
    } else {
        $("#curr_long").text("Current longitude: " + currLocation.lng.toString() + " E")
    }
}
