'use strict';

function Ctrl($scope, $http) {
    $http.get("status").success(function (data) {
        $scope.status = data;
    });
}
