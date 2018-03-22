$(document).ready(function() {
    $(".toggle > *").hide();
    $(".toggle .header").show();
    $(".toggle .header").click(function() {
        $(this).parent().children().not(".header").toggle(200);
        $(this).parent().children(".header").toggleClass("open");
    })
});

// readthedocs fix
// Readthedocs sets a wrapper around all tables, with a display attribute.
// This display attribute does not work with the collapse function, so that we need to
// correct this. Additionally we also need to set our needs-table on display:block, because it is no longer a
// direct child of div.toggle and our script only manipulates direct children.
$(window).on('load', function() {
    $(".toggle > .wy-table-responsive").hide();
    $(".wy-table-responsive > table").show();
});