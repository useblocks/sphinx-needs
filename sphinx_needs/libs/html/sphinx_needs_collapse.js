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
    $("table.need span.needs.needs_collapse").each(function() {
        var id = $(this).attr("id");
        var parts = id.split("__");
        var rows = parts.slice(2);

        var table = $(this).closest('table');
        var need_table = table[0];

        if (parts[1] == "show") {
            var visible_icon = document.querySelector(`#${need_table.parentNode.id} table span.needs.visible`);
            visible_icon.classList.toggle("collapse_is_hidden");
        } else {
            var collapse_icon = document.querySelector(`#${need_table.parentNode.id} table span.needs.collapsed`);
            collapse_icon.classList.toggle("collapse_is_hidden");
            for (var row in rows) {
                var collapse_row = document.querySelector(`#${need_table.parentNode.id} table tr.${rows[row]}`);
                collapse_row.classList.toggle("collapse_is_hidden");
            }
        }
        // Func to execute when collapse buttons get clicked ()
        $(this).find("span.needs.collapsed, span.needs.visible").click(function() {
            var table = $(this).closest('table');
            var need_table = table[0];
            for (var row in rows) {
                var collapse_row = document.querySelector(`#${need_table.parentNode.id} table tr.${rows[row]}`);
                collapse_row.classList.toggle("collapse_is_hidden");
            }
            var collapse_icon = document.querySelector(`#${need_table.parentNode.id} table span.needs.collapsed`);
            var visible_icon = document.querySelector(`#${need_table.parentNode.id} table span.needs.visible`);

            collapse_icon.classList.toggle("collapse_is_hidden");
            visible_icon.classList.toggle("collapse_is_hidden");
        })
    });
});

$(document).ready(function() {
    $('a.no_link').click(function (e) {
        e.preventDefault();
    });
});



