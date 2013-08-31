'use strict';


function Ctrl($scope, $http) {
    function refresh() {
        $http.get("status").success(function (data) {
            $scope.status = data;
        });
    }
    refresh();
    $scope.setLed = function (value) {
        $http.put("led", value).succeed(function () {
            refresh();
        });
    };
    $scope.temporaryUnlock = function () {
        var seconds = 3;
        $http.put("strike/temporaryUnlock", {seconds: seconds}).succeed(function () {
            refresh();
            setTimeout(function () { refresh(); }, (seconds + .1) * 1000);
        });
    };
    $scope.beep = function () {
        $http.put("speaker/beep").succeed(function () {
            $scope.speakerStatus = "sent at " + new Date();
        });
    }
}
