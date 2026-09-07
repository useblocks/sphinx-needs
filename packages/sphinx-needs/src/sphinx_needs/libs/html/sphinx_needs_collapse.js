// This JS function ensures the metadata of a need table is hidden or shown when a document is loaded
// and it also ensures that when a user clicks on the collapse button, the metadata is hidden or shown.

const HIDE_CLASS = "collapse_is_hidden";

$(document).ready(function() {
    $("table.need span.needs.needs_collapse").each(function() {
        var id = $(this).attr("id");
        var parts = id.split("__");
        var rows = parts.slice(2);

        var table = $(this).closest('table');
        var need_table_id = table.closest("div[id^=SNCB-]").attr("id");

        // initialise the correct collapse state
        if (parts[1] == "show") {
            var visible_icon = document.querySelector(`#${need_table_id} table span.needs.visible`);
            visible_icon.classList.add(HIDE_CLASS);
            var collapse_icon = document.querySelector(`#${need_table_id} table span.needs.collapsed`);
            collapse_icon.classList.remove(HIDE_CLASS);
            for (var row in rows) {
                var collapse_row = document.querySelector(`#${need_table_id} table tr.${rows[row]}`);
                collapse_row.classList.remove(HIDE_CLASS);
            }
        } else {
            var visible_icon = document.querySelector(`#${need_table_id} table span.needs.visible`);
            visible_icon.classList.remove(HIDE_CLASS);
            var collapse_icon = document.querySelector(`#${need_table_id} table span.needs.collapsed`);
            collapse_icon.classList.add(HIDE_CLASS);
            for (var row in rows) {
                var collapse_row = document.querySelector(`#${need_table_id} table tr.${rows[row]}`);
                collapse_row.classList.add(HIDE_CLASS);
            }
        }

        // Func to execute when collapse buttons get clicked ()
        $(this).find("span.needs.collapsed, span.needs.visible").click(function() {
            var table = $(this).closest('table');
            var need_table_id = table.closest("div[id^=SNCB-]").attr("id");
            for (var row in rows) {
                var collapse_row = document.querySelector(`#${need_table_id} table tr.${rows[row]}`);
                collapse_row.classList.toggle(HIDE_CLASS);
            }
            var collapse_icon = document.querySelector(`#${need_table_id} table span.needs.collapsed`);
            var visible_icon = document.querySelector(`#${need_table_id} table span.needs.visible`);

            collapse_icon.classList.toggle(HIDE_CLASS);
            visible_icon.classList.toggle(HIDE_CLASS);
        })
    });
});

$(document).ready(function() {
    $('a.no_link').click(function (e) {
        e.preventDefault();
    });
});



