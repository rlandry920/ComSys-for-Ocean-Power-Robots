var currLocation = { lat: 37.2284, lng: -80.4234 };
var currDirection = 0;
var markerShown = false;
var moving = "stop";
var speed = 50;
var refreshTime = 1000 // Every second
var liveControl = false;

var map, currLocationMarker, goToMarker;

$(document).ready(function () {
    var pressedKey = -1;
    //Initialize everything
    addMessage("Log:", "b")
    initMap();
    checkLiveControl();
    //Get corrent num users
    sendOpenWindow();
    sendGetNumUsers();

    //Call refersh function periodically
    var refreshInterval = setInterval(refresh, refreshTime);

    //H264 PLAYER BELOW FROM https://www.codeinsideout.com/blog/pi/stream-picamera-h264/
    // player
    window.player = new Player({
        useWorker: true,
        webgl: "auto",
        size: { width: 300, height: 240 },
    });
    var playerElement = document.getElementById("viewer");
    playerElement.appendChild(window.player.canvas);

    // Camera Websocket
    var wsCameraUri =
        window.location.protocol.replace(/http/, "ws") +
        "//" +
        window.location.hostname +
        ":9000";
    var wsCamera = new WebSocket(wsCameraUri);
    wsCamera.binaryType = "arraybuffer";
    wsCamera.onopen = function (e) {
        console.log("Camera Client connected");
        wsCamera.onmessage = function (msg) {
            // decode stream
            console.log("Camera Client Received message");
            window.player.decode(new Uint8Array(msg.data));
        };
    };
    wsCamera.onclose = function (e) {
        console.log("Camera Client disconnected");
    };

    // Data Websocket
    var wsDataUri =
        window.location.protocol.replace(/http/, "ws") +
        "//" +
        window.location.hostname +
        ":8000";
    var wsData = new WebSocket(wsDataUri);
    wsData.binaryType = "arraybuffer";
    wsData.onopen = function (e) {
        console.log("Data Client connected");
        //Handle all messages
        wsData.onmessage = function (msg) {
            var data = JSON.parse(msg.data);
            var type = data["type"];
            switch (type) {
                case "state":
                    updateState(data["state"])
                    break;
                case "voltage":
                    updateBattery(data["voltage"])
                    break;
                case "gps":
                    currLocation.lat = Math.round(data["lat"] * 10000) / 10000
                    currLocation.lng = Math.round(data["long"] * 10000) / 10000
                    currDirection = Math.round(data["compass"] * 100) / 100
                    break;
                case "message":
                    addMessage(data["message"], "r")
                    breakl
                case "num-users":
                    console.log('Num users: ' + data["num-users"])
                    $("#num_users_text").text("Active Users: " + data["num-users"])
                    break;
                default:
                    console.log("Received invalid message");
            }
        };
    };
    wsData.onclose = function (e) {
        console.log("Data Client disconnected");
    };

    //Decrease the number of users when window is closed
    window.onbeforeunload = function () {
        navigator.sendBeacon("{{ url_for("closeWindow") }}");
    };

    //Request live control
    $("#live_control").click(function () {
        liveControl = !liveControl
        var data = [
            {
                "enable": liveControl
            }
        ];
        $.ajax({
            type: 'POST',
            url: "{{ url_for("reqLiveControl") }}",
            data: JSON.stringify(data),
            contentType: "application/json",
            dataType: "text",
            error: function (XMLHttpRequest, textStatus, errorThrown) {
                addMessage("Live control" + " failed: " + XMLHttpRequest.status + " " + errorThrown, 'r');
            }
        });
        checkLiveControl();
    });

    //Send coordinates for autonomous navigation
    $("#move").click(function () {
        var lat_dir = document.querySelector('input[name="latitude_dir"]:checked').value[0];
        var long_dir = document.querySelector('input[name="longitude_dir"]:checked').value[0];
        sendGoToCommand($("#lat").val(), $("#long").val(), lat_dir, long_dir)
        addMessage("Coordinates sent", "s")
        $("#lat").val("")
        $("#long").val("")
    });

    //Movement controls

    $("#left").mousedown(function () {
        if (moving != "turnLeft") {
            sendMoveCommand("turnLeft")
            moving = "turnLeft";
            addMessage("Turn left command sent", "s")
        } else {
            sendMoveCommand("stop")
            moving = "stop";
            addMessage("Stop command sent", "s")
        }
    });

    $("#right").mousedown(function () {
        if (moving != "turnRight") {
            sendMoveCommand("turnRight")
            moving = "turnRight";
            addMessage("Turn right command sent", "s")
        } else {
            sendMoveCommand("stop")
            moving = "stop";
            addMessage("Stop command sent", "s")
        }
    });

    $("#forward").mousedown(function () {
        if (moving != "moveForward") {
            sendMoveCommand("moveForward")
            moving = "moveForward";
            addMessage("Move forward command sent", "s")
        } else {
            sendMoveCommand("stop")
            moving = "stop";
            addMessage("Stop command sent", "s")
        }
    });

    $("#backward").mousedown(function () {
        if (moving != "moveBackward") {
            sendMoveCommand("moveBackward")
            moving = "moveBackward"
            addMessage("Move backward command sent", "s")
        } else {
            sendMoveCommand("stop")
            moving = "stop";
            addMessage("Stop command sent", "s")
        }
    });

    $(document).keydown(function (event) {
        if (pressedKey == -1) {
            var key = event.keyCode;

            if (key == 39) {
                sendMoveCommand("turnRight")
                moving = "turnRight";
                addMessage("Turn right command sent", "s")
                pressedKey = 39
            }
            else if (key == 37) {
                sendMoveCommand("turnLeft")
                moving = "turnLeft";
                addMessage("Turn left command sent", "s")
                pressedKey = 37
            }
            else if (key == 38) {
                sendMoveCommand("moveForward")
                moving = "moveForward";
                addMessage("Move forward command sent", "s")
                pressedKey = 37
            }
            else if (key == 40) {
                sendMoveCommand("moveBackward")
                moving = "moveBackward";
                addMessage("Move backward command sent", "s")
                pressedKey = 37
            }
        }
        event.preventDefault();
    });

    $(document).keyup(function (event) {
        var key = event.keyCode;

        if (key == 39 || key == 37 || key == 38 || key == 40) {
            sendMoveCommand("stop")
            moving = "stop"
            addMessage("Stop command sent", "s")
            pressedKey = -1
        }

        event.preventDefault();
    });

    $("#delete_marker").hide();

    $("#delete_marker").mousedown(function () {
        deleteMarker();
    });

    //Speed slider
    document.getElementById("speed").oninput = function () {
        updateSpeed(this.value);
    }

    //Place markers for coordinates
    google.maps.event.addListener(map, 'click', function (event) {
        placeMarker(event.latLng);
    });
});

//Only show live controls sometimes
function checkLiveControl() {
    var moveCard = document.getElementById("move-card");
    var video = document.getElementById("viewer")
    if (liveControl) {
        moveCard.style.display = "block";
        video.style.display = "block"
        $("#live_control").html("Stop Live Control")
    } else {
        moveCard.style.display = "none";
        video.style.display = "none"
        $("#live_control").html("Request Live Control")
    }

}

//Refresh all data
function refresh() {
    if (moving != "stop") {
        sendMoveCommand(moving);
    }
    $('#compass_image').css({
        'transform': 'rotate(' + currDirection + 'deg)',
        '-ms-transform': 'rotate(' + currDirection + 'deg)',
        '-moz-transform': 'rotate(' + currDirection + 'deg)',
        '-webkit-transform': 'rotate(' + currDirection + 'deg)',
        '-o-transform': 'rotate(' + currDirection + 'deg)'
    });
    updateCurrentLocation();
}

//Update button texts
function updateSpeed(newSpeed) {
    $("#speed_text").text("Speed: " + newSpeed + "%")
}
function updateMoveButtonsText() {
    $("#right").html(moving == "turnRight" ? "Stop" : "Turn Right");
    $("#left").html(moving == "turnLeft" ? "Stop" : "Turn Left");
    $("#forward").html(moving == "moveForward" ? "Stop" : "Forward");
    $("#backward").html(moving == "moveBackward" ? "Stop" : "Backward");
}

//Remove marker from map
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

//Put marker on map and get coordinates
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

//Update number of users when window is open
function sendOpenWindow() {
    console.log("SENDING OPEN WINDOW")
    $.ajax({
        type: 'POST',
        url: "{{ url_for("openWindow") }}",
        contentType: "application/json",
        dataType: "text",
        success: function () {
            sendGetNumUsers();
        }
    });
}

//Get number of active users
function sendGetNumUsers() {
    $.ajax({
        type: 'POST',
        url: "{{ url_for("getNumUsers") }}",
        contentType: "application/json",
        dataType: "text",
        success: function (response) {
            $("#num_users_text").text("Active Users: " + parseInt(response))
        }

    });
}

//Send coordinates for autonomous navigation
function sendGoToCommand(lat, long, lat_dir, long_dir) {
    if (lat_dir == 'S') {
        lat = '-' + lat
    }
    if (long_dir == 'W') {
        long = '-' + long
    }
    var data = [
        {
            "lat_py": lat,
            "long_py": long
        }
    ];
    $.ajax({
        type: 'POST',
        url: "{{ url_for("goToCoordinates") }}",
        data: JSON.stringify(data),
        contentType: "application/json",
        dataType: "text",
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            addMessage("Go to coordinates failed: " + XMLHttpRequest.status + " " + errorThrown, 'r');
            moving = "stop"
        }

    });
}

function sendMoveCommand(command) {
    var data = [
        {
            "command": command,
            "speed": document.getElementById("speed").value / 100.0
        }
    ];
    $.ajax({
        type: 'POST',
        url: "{{ url_for("move") }}",
        data: JSON.stringify(data),
        contentType: "application/json",
        dataType: "text",
        success: function () {
            updateMoveButtonsText();
        },
        error: function (XMLHttpRequest, textStatus, errorThrown) {
            addMessage(command + " failed: " + XMLHttpRequest.status + " " + errorThrown, 'r');
            moving = "stop"
        }
    });
}

//Add message to log
function addMessage(messageString, messageType) {
    if (messageType == "r") {
        var $p = $('<p style="color:red; line-height:100%;"></p>');
    }
    else if (messageType == "b") {
        var $p = $('<p style="color:black; line-height:100%;"></p>');
    }
    else {
        var $p = $('<p style="color:blue; line-height:100%;"></p>');
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
    const image = "{{ url_for('static',filename = 'boat_marker.png') }}"

    // The current location marker
    currLocationMarker = new google.maps.Marker({
        position: currLocation,
        map: map,
        icon: image
    });

    // The destination marker
    goToMarker = new google.maps.Marker({
        position: currLocation,
        map: map,
        visible: false,
    });

    updateCurrentLocation();
}

//Update data

function updateBoatMarker() {
    currLocationMarker.setPosition(currLocation)
    if (!goToMarker.visible)
        if (map.getZoom() > 16) {
            map.setZoom(16);
        }
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
    $("#curr_dir").text("Current bearing: " + currDirection.toString() + " degrees")

    updateBoatMarker();
}

function updateBattery(voltage) {
    var roundedVoltage = Math.round(voltage * 100) / 100
    $("#curr_voltage").text("Current voltage: " + roundedVoltage.toString() + "V")

    var percentage = (Math.round((62.5 * voltage) - 1487.5) * 100) / 100
    if (percentage > 100) {
        percentage = 100;
    }
    else if (percentage < 0) {
        percentage = 0;
    }
    var batteryLevel = jQuery('.battery .battery-level');
    batteryLevel.css('width', percentage + '%');
    batteryLevel.text(percentage + '%');
    if (percentage > 50) {
        batteryLevel.css('background-color', '#66CD00')
    } else if (percentage >= 25) {
        batteryLevel.css('background-color', '#FCD116')
    } else {
        batteryLevel.css('background-color', '#FF3333')
    }
}

function updateState(state) {
    $("#curr_state").text("Current state: " + state)
}