(function () {
    function abbreviateTrig(trig) {
        // prefixes, abbreviations, make everything into links, etc
        return trig;
    }
    
    var model = {
        current: ko.observable("...")
    };
    model.refreshGraph = function() {
        $.ajax({
            url: "graph",
            success: function(data) {
                model.current(abbreviateTrig(data));
            }
        });
    };
    model.refreshGraph();
    ko.applyBindings(model);   
})();
