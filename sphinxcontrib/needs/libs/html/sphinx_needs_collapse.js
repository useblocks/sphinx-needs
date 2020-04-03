$(document).ready(function() {
    window.setTimeout(function() {
            $(".toggle > *").hide();
                $(".toggle .header").show();
                $(".toggle .header").click(function() {
                    $(this).parent().children().not(".header").not(".wy-table-responsive").toggle(200);
                    $(this).parent().children('.wy-table-responsive').children().toggle(200);
                    $(this).parent().children(".header").toggleClass("open");
                })
          }, 10);
});
//
// // readthedocs fix
// // Readthedocs sets a wrapper around all tables, with a display attribute.
// // This display attribute does not work with the collapse function, so that we need to
// // correct this. Additionally we also need to set our needs-table on display:block, because it is no longer a
// // direct child of div.toggle and our script only manipulates direct children.
// $(window).on('load', function() {
//     $(".toggle > .wy-table-responsive").hide();
//     $(".wy-table-responsive > table").show();
// });

$(document).ready(function() {
    $("table.need span.collapse").each(function() {
        var id = $(this).attr("id");
        var parts = id.split("__");
        var rows = parts.slice(2);
        if (parts[1] == "show") {
            $(this).find("span.needs.visible").toggle(0);
        } else {
            $(this).find("span.needs.collapsed").toggle(0);
            var table = $(this).closest('table');
            for (var row in rows) {
                table.find("tr."+rows[row]).slideToggle(0);
            }
        }
        // Func to execute when collapse buttons get clicked ()
        $(this).find("span.needs.collapsed, span.needs.visible").click(function() {
            var table = $(this).closest('table');
            for (var row in rows) {
                table.find("tr."+rows[row]).slideToggle(0);
            }
            table.find("span.collapse span.needs.collapsed").toggle(0);
            table.find("span.collapse span.needs.visible").toggle(0);
        })
    });

});

$(document).ready(function() {
    $('a.no_link').click(function (e) {
        e.preventDefault();
    });
});
