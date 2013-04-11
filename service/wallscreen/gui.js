var reloadData;
$(function () {
    
    setTimeout(function () {
        window.resizeTo(702,480);
    }, 10000);
    
    var model = {
        requestedF: ko.observable(),
        tasks: ko.observableArray([]),
        events: ko.observableArray([]),
        isToday: function (ev) {
            var today = moment().format("YYYY-MM-DD");
            return ev.date == today;
        }
    };
    reloadData = function() {
        $.getJSON("content", function (data) {
            model.tasks(data.tasks);
            model.events(data.events);
        });
    }
    setInterval(reloadData, 30*60*1000);
    reloadData();

    function onMessage(d) {
        if (d.tempF) {
            model.requestedF(d.tempF);
        }
    }
    reconnectingWebSocket("ws://bang.bigasterisk.com:9102/live", onMessage);

    ko.applyBindings(model);

    if (navigator.userAgent == "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:18.0) Gecko/18.0 Firefox/18.0") {
        $(".rot").removeClass("rot");
    }

    function updateClock() {
        var now = moment();
        var s = (new Date()).toLocaleTimeString();
        $("#clock").html(
            "<div>"+now.format("dddd")+"</div>"+
                "<div>"+now.format("MMM Do")+"</div>"+
                "<div>"+now.format("HH:mm")+"</div>"
        )
    }
    setInterval(updateClock, 20000)
    updateClock();
});
