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
    }
                                        
}
