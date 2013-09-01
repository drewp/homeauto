'use strict';


function Ctrl($scope, $http, $timeout) {
    $scope.refresh = function () {
        $http.get("status").success(function (data) {
            $scope.status = data;
        });
    }
    $scope.refresh();
    $scope.setLed = function (value) {
        $http.put("led", value).success(function () {
            $scope.refresh();
        });
    };
    $scope.temporaryUnlock = function () {
        var seconds = 3;
        $http.put("strike/temporaryUnlock", {seconds: seconds}).success(function () {
            $scope.refresh();
            $timeout($scope.refresh, (seconds + .1) * 1000);
        });
    };
    $scope.beep = function () {
        $http.put("speaker/beep").success(function () {
            $scope.speakerStatus = "sent at " + new Date();
        });
    }
}
